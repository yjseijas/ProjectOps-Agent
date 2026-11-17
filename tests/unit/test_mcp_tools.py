from __future__ import annotations

import asyncio
from typing import Any

import pytest

from config.settings import Settings
from projectops_mcp.tools import assign_work_item, update_work_item_status


class _RecordResult:
    def __init__(self, record: dict[str, object] | None) -> None:
        self._record = record

    async def single(self) -> dict[str, object] | None:
        return self._record


class _Transaction:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def run(self, query: str, **parameters: object) -> _RecordResult:
        self.calls.append((query, parameters))
        if "RETURN project IS NOT NULL" in query:
            if self.state.get("validation_none"):
                return _RecordResult(None)
            if "SET work_item.status" not in query:
                if "assignee_exists" in self.state:
                    return _RecordResult(
                        {
                            "project_exists": self.state["project_exists"],
                            "work_item_exists": self.state["work_item_exists"],
                            "work_item_belongs": self.state["work_item_belongs"],
                            "assignee_exists": self.state["assignee_exists"],
                        }
                    )
                return _RecordResult(
                    {
                        "project_exists": self.state["project_exists"],
                        "work_item_exists": self.state["work_item_exists"],
                        "work_item_belongs": self.state["work_item_belongs"],
                    }
                )
        if "SET work_item.status" in query:
            if self.state.get("update_none"):
                return _RecordResult(None)
            if self.state.get("update_mismatch"):
                return _RecordResult({"work_item_id": "PBI-999"})
            return _RecordResult({"work_item_id": parameters["work_item_id"]})
        if "SET work_item.assignee_id" in query:
            if self.state.get("update_none"):
                return _RecordResult(None)
            if self.state.get("update_mismatch"):
                return _RecordResult({"work_item_id": "PBI-999"})
            return _RecordResult({"work_item_id": parameters["work_item_id"]})
        if self.state.get("update_none"):
            return _RecordResult(None)
        return _RecordResult({"work_item_id": parameters["work_item_id"]})


class _Session:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state
        self.transaction = _Transaction(state)
        self.closed = False
        self.database: str | None = None
        self.write_calls = 0

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.state.get("exit_cancelled"):
            raise asyncio.CancelledError()
        if self.state.get("exit_error"):
            raise RuntimeError("raw session cleanup credentials")
        self.closed = True

    async def execute_write(self, callback: Any) -> bool:
        self.write_calls += 1
        if self.state.get("execute_error"):
            raise RuntimeError("raw database credentials and details")
        if self.state.get("execute_cancelled"):
            raise asyncio.CancelledError()
        if self.state.get("execute_false"):
            return False
        return await callback(self.transaction)


class _Driver:
    def __init__(self, state: dict[str, object] | None = None) -> None:
        self.state = state or {
            "project_exists": True,
            "work_item_exists": True,
            "work_item_belongs": True,
            "assignee_exists": True,
        }
        self.sessions: list[_Session] = []
        self.closed = False

    def session(self, *, database: str) -> _Session:
        if self.state.get("session_error"):
            raise RuntimeError("raw session secret and database details")
        session = _Session(self.state)
        session.database = database
        self.sessions.append(session)
        return session

    async def close(self) -> None:
        if self.state.get("close_error"):
            raise RuntimeError("raw cleanup credentials")
        self.closed = True


def _valid_arguments() -> dict[str, object]:
    return {
        "project_id": "atlas",
        "work_item_id": "PBI-102",
        "assignee_id": "alice",
    }


def _valid_status_arguments() -> dict[str, object]:
    return {
        "project_id": "atlas",
        "work_item_id": "PBI-102",
        "status": "In Progress",
    }


@pytest.mark.asyncio
async def test_successful_assignment() -> None:
    driver = _Driver()

    result = await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result == {
        "status": "success",
        "work_item_id": "PBI-102",
        "assignee_id": "alice",
        "message": "Work item assigned successfully.",
    }
    session = driver.sessions[0]
    assert session.database == "atlas-test"
    assert session.closed
    assert not driver.closed
    assert len(session.transaction.calls) == 2
    assert "SET work_item.assignee_id" in session.transaction.calls[1][0]
    assert "DELETE existing_assignee" in session.transaction.calls[1][0]
    assert "MERGE (work_item)-[:ASSIGNED_TO]->(assignee)" in session.transaction.calls[1][0]


@pytest.mark.asyncio
async def test_non_mapping_arguments_return_failure_without_write() -> None:
    driver = _Driver()

    result = await assign_work_item(
        ["not", "an", "object"],  # type: ignore[arg-type]
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result == {
        "status": "failure",
        "work_item_id": "",
        "message": "Assignment arguments must be an object.",
    }
    assert driver.sessions == []


@pytest.mark.asyncio
async def test_missing_work_item_id_returns_empty_string_in_schema_shape() -> None:
    driver = _Driver()

    result = await assign_work_item(
        {"project_id": "atlas", "assignee_id": "alice"},
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert set(result) == {"status", "work_item_id", "message"}
    assert result["status"] == "failure"
    assert result["work_item_id"] == ""


@pytest.mark.asyncio
async def test_invalid_work_item_id_type_returns_empty_string_in_schema_shape() -> None:
    driver = _Driver()

    result = await assign_work_item(
        {"project_id": "atlas", "work_item_id": 123, "assignee_id": "alice"},
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert set(result) == {"status", "work_item_id", "message"}
    assert result["status"] == "failure"
    assert result["work_item_id"] == ""


@pytest.mark.asyncio
async def test_missing_required_input_returns_failure_without_write() -> None:
    driver = _Driver()
    arguments = {"project_id": "atlas", "work_item_id": "PBI-102"}

    result = await assign_work_item(
        arguments,
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert result["work_item_id"] == "PBI-102"
    assert "Missing required" in str(result["message"])
    assert driver.sessions == []


@pytest.mark.asyncio
async def test_unexpected_input_property_returns_failure_without_write() -> None:
    driver = _Driver()
    arguments = _valid_arguments()
    arguments["status"] = "In Progress"

    result = await assign_work_item(
        arguments,
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "unexpected properties" in str(result["message"])
    assert driver.sessions == []


@pytest.mark.asyncio
@pytest.mark.parametrize("property_name", ["project_id", "work_item_id", "assignee_id"])
async def test_invalid_property_type_returns_failure_without_write(property_name: str) -> None:
    driver = _Driver()
    arguments = _valid_arguments()
    arguments[property_name] = 123

    result = await assign_work_item(
        arguments,
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "must be a string" in str(result["message"])
    assert driver.sessions == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected_message"),
    [
        (
            {
                "project_exists": False,
                "work_item_exists": True,
                "work_item_belongs": True,
                "assignee_exists": True,
            },
            "Project not found",
        ),
        (
            {
                "project_exists": True,
                "work_item_exists": False,
                "work_item_belongs": False,
                "assignee_exists": True,
            },
            "Work item not found",
        ),
        (
            {
                "project_exists": True,
                "work_item_exists": True,
                "work_item_belongs": False,
                "assignee_exists": True,
            },
            "does not belong",
        ),
        (
            {
                "project_exists": True,
                "work_item_exists": True,
                "work_item_belongs": True,
                "assignee_exists": False,
            },
            "Assignee person not found",
        ),
    ],
)
async def test_entity_failures_stop_before_update(
    state: dict[str, object],
    expected_message: str,
) -> None:
    driver = _Driver(state)

    result = await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert expected_message in str(result["message"])
    assert len(driver.sessions) == 1
    assert len(driver.sessions[0].transaction.calls) == 1
    assert driver.sessions[0].closed


@pytest.mark.asyncio
async def test_empty_validation_result_returns_failure_not_success() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "assignee_exists": True,
        "validation_none": True,
    }
    driver = _Driver(state)

    result = await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "Unable to validate" in str(result["message"])
    assert len(driver.sessions[0].transaction.calls) == 1
    assert driver.sessions[0].closed


@pytest.mark.asyncio
async def test_false_transaction_result_returns_failure_not_success() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "assignee_exists": True,
        "execute_false": True,
    }
    driver = _Driver(state)

    result = await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "Unable to complete" in str(result["message"])
    assert driver.sessions[0].closed


@pytest.mark.asyncio
async def test_update_query_without_record_returns_failure() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "assignee_exists": True,
        "update_none": True,
    }
    driver = _Driver(state)

    result = await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "Unable to persist" in str(result["message"])
    assert len(driver.sessions[0].transaction.calls) == 2


@pytest.mark.asyncio
async def test_transaction_exception_returns_safe_failure_for_injected_driver() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "assignee_exists": True,
        "execute_error": True,
    }
    driver = _Driver(state)

    result = await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert result["message"] == "Unable to complete the work-item assignment."
    assert "raw database" not in str(result["message"])
    assert not driver.closed


@pytest.mark.asyncio
async def test_transaction_exception_closes_created_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "assignee_exists": True,
        "execute_error": True,
    }
    driver = _Driver(state)
    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: driver,
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    result = await assign_work_item(_valid_arguments(), configuration=configuration)

    assert result["status"] == "failure"
    assert "raw database" not in str(result["message"])
    assert driver.closed


@pytest.mark.asyncio
async def test_session_exception_returns_safe_failure_and_closes_created_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "assignee_exists": True,
        "session_error": True,
    }
    driver = _Driver(state)
    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: driver,
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    result = await assign_work_item(_valid_arguments(), configuration=configuration)

    assert result["status"] == "failure"
    assert "raw session" not in str(result["message"])
    assert driver.closed


@pytest.mark.asyncio
async def test_driver_creation_exception_returns_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    def raise_driver_error(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("credential=secret; raw URI details")

    monkeypatch.setattr(tools_module.AsyncGraphDatabase, "driver", raise_driver_error)
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    result = await assign_work_item(_valid_arguments(), configuration=configuration)

    assert result["status"] == "failure"
    assert result["message"] == "Unable to initialize the assignment service."
    assert "credential" not in str(result["message"])
    assert "secret" not in str(result["message"])


@pytest.mark.asyncio
async def test_reassignment_updates_property_and_replaces_relationship_in_one_transaction() -> None:
    driver = _Driver()

    await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    transaction = driver.sessions[0].transaction
    update_query, parameters = transaction.calls[1]
    assert parameters == {
        "project_id": "atlas",
        "work_item_id": "PBI-102",
        "assignee_id": "alice",
    }
    assert "OPTIONAL MATCH (work_item)-[existing_assignee:ASSIGNED_TO]->(:Person)" in update_query
    assert "DELETE existing_assignee" in update_query
    assert "MERGE (work_item)-[:ASSIGNED_TO]->(assignee)" in update_query
    assert "SET work_item.assignee_id" in update_query


@pytest.mark.asyncio
async def test_status_and_project_membership_are_preserved_by_update_query() -> None:
    driver = _Driver()

    await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    update_query = driver.sessions[0].transaction.calls[1][0]
    assert "SET work_item.status" not in update_query
    assert "DELETE work_item" not in update_query
    assert "(work_item:WorkItem" in update_query
    assert "-[:BELONGS_TO]->(:Project {id: $project_id})" in update_query


@pytest.mark.asyncio
async def test_injected_driver_is_not_closed() -> None:
    driver = _Driver()

    await assign_work_item(
        _valid_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert not driver.closed


@pytest.mark.asyncio
async def test_created_driver_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import projectops_mcp.tools as tools_module

    driver = _Driver()
    monkeypatch.setattr(tools_module.AsyncGraphDatabase, "driver", lambda *_args, **_kwargs: driver)
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    await assign_work_item(_valid_arguments(), configuration=configuration)

    assert driver.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected_status"),
    [
        ({"close_error": True}, "success"),
        (
            {
                "close_error": True,
                "work_item_exists": False,
            },
            "failure",
        ),
    ],
)
async def test_internal_driver_close_exception_preserves_result(
    monkeypatch: pytest.MonkeyPatch,
    state: dict[str, object],
    expected_status: str,
) -> None:
    import projectops_mcp.tools as tools_module

    state.update(
        {
            "project_exists": True,
            "work_item_belongs": state.get("work_item_exists", True) is not False,
            "assignee_exists": True,
        }
    )
    if "work_item_exists" not in state:
        state["work_item_exists"] = True
    driver = _Driver(state)
    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: driver,
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    result = await assign_work_item(_valid_arguments(), configuration=configuration)

    assert result["status"] == expected_status
    assert "raw cleanup" not in str(result)
    assert driver.closed is False


@pytest.mark.asyncio
async def test_cancellation_exception_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "assignee_exists": True,
        "execute_cancelled": True,
    }
    driver = _Driver(state)
    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: driver,
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    with pytest.raises(asyncio.CancelledError):
        await assign_work_item(_valid_arguments(), configuration=configuration)


@pytest.mark.asyncio
async def test_successful_status_update() -> None:
    driver = _Driver()

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result == {
        "status": "success",
        "work_item_id": "PBI-102",
        "new_status": "In Progress",
        "message": "Work item status updated successfully.",
    }
    assert set(result) == {"status", "work_item_id", "new_status", "message"}
    session = driver.sessions[0]
    assert session.database == "atlas-test"
    assert session.closed
    assert len(session.transaction.calls) == 2
    assert "SET work_item.status = $status" in session.transaction.calls[1][0]
    assert "SET work_item.assignee_id" not in session.transaction.calls[1][0]


@pytest.mark.asyncio
async def test_status_update_rejects_non_mapping_arguments() -> None:
    driver = _Driver()

    result = await update_work_item_status(
        ["not", "an", "object"],  # type: ignore[arg-type]
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert set(result) == {"status", "work_item_id", "message"}
    assert result["status"] == "failure"
    assert result["work_item_id"] == ""
    assert driver.sessions == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "work_item_id"),
    [
        ({"project_id": "atlas", "status": "In Progress"}, ""),
        ({"project_id": "atlas", "work_item_id": "PBI-102"}, "PBI-102"),
        (
            {"project_id": "atlas", "work_item_id": "PBI-102", "status": 123},
            "PBI-102",
        ),
        (
            {"project_id": "atlas", "work_item_id": "PBI-102", "status": "Unknown"},
            "PBI-102",
        ),
    ],
)
async def test_status_update_input_failures(
    arguments: dict[str, object],
    work_item_id: str,
) -> None:
    driver = _Driver()

    result = await update_work_item_status(
        arguments,
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert set(result) == {"status", "work_item_id", "message"}
    assert result["status"] == "failure"
    assert result["work_item_id"] == work_item_id
    assert isinstance(result["message"], str)
    assert driver.sessions == []


@pytest.mark.asyncio
async def test_status_update_rejects_unexpected_property() -> None:
    driver = _Driver()
    arguments = _valid_status_arguments()
    arguments["assignee_id"] = "alice"

    result = await update_work_item_status(
        arguments,
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert result["work_item_id"] == "PBI-102"
    assert driver.sessions == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected_message"),
    [
        (
            {
                "project_exists": False,
                "work_item_exists": True,
                "work_item_belongs": True,
            },
            "Project not found",
        ),
        (
            {
                "project_exists": True,
                "work_item_exists": False,
                "work_item_belongs": False,
            },
            "Work item not found",
        ),
        (
            {
                "project_exists": True,
                "work_item_exists": True,
                "work_item_belongs": False,
            },
            "does not belong",
        ),
    ],
)
async def test_status_update_entity_failures_before_update(
    state: dict[str, object],
    expected_message: str,
) -> None:
    driver = _Driver(state)

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert expected_message in str(result["message"])
    assert len(driver.sessions) == 1
    assert len(driver.sessions[0].transaction.calls) == 1
    assert driver.sessions[0].closed


@pytest.mark.asyncio
async def test_status_update_empty_validation_result_returns_failure() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "validation_none": True,
    }
    driver = _Driver(state)

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert len(driver.sessions[0].transaction.calls) == 1


@pytest.mark.asyncio
async def test_status_update_empty_update_result_returns_failure() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "update_none": True,
    }
    driver = _Driver(state)

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "Unable to persist" in str(result["message"])
    assert len(driver.sessions[0].transaction.calls) == 2


@pytest.mark.asyncio
async def test_status_update_mismatched_update_result_returns_failure() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "update_mismatch": True,
    }
    driver = _Driver(state)

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "Unable to persist" in str(result["message"])


@pytest.mark.asyncio
async def test_status_update_false_transaction_result_returns_failure() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "execute_false": True,
    }
    driver = _Driver(state)

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "Unable to complete" in str(result["message"])


@pytest.mark.asyncio
async def test_status_update_transaction_exception_is_safe_and_injected_driver_remains_open() -> (
    None
):
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "execute_error": True,
    }
    driver = _Driver(state)

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "raw database" not in str(result["message"])
    assert not driver.closed


@pytest.mark.asyncio
async def test_status_update_session_exception_is_safe_and_closes_created_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "session_error": True,
    }
    driver = _Driver(state)
    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: driver,
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=configuration,
    )

    assert result["status"] == "failure"
    assert "raw session" not in str(result["message"])
    assert driver.closed


@pytest.mark.asyncio
async def test_status_update_driver_creation_failure_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("credential=secret")),
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=configuration,
    )

    assert result["status"] == "failure"
    assert "credential" not in str(result["message"])
    assert "secret" not in str(result["message"])


@pytest.mark.asyncio
async def test_status_update_internal_driver_is_closed_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "execute_error": True,
    }
    driver = _Driver(state)
    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: driver,
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=configuration,
    )

    assert result["status"] == "failure"
    assert driver.closed


@pytest.mark.asyncio
async def test_status_update_cleanup_exception_preserves_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "close_error": True,
    }
    driver = _Driver(state)
    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: driver,
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=configuration,
    )

    assert result["status"] == "success"
    assert "raw cleanup" not in str(result)


@pytest.mark.asyncio
async def test_status_update_session_exit_exception_preserves_success() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "exit_error": True,
    }
    driver = _Driver(state)

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "success"
    assert "raw session cleanup" not in str(result)


@pytest.mark.asyncio
async def test_status_update_session_exit_exception_preserves_failure() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": False,
        "work_item_belongs": False,
        "exit_error": True,
    }
    driver = _Driver(state)

    result = await update_work_item_status(
        _valid_status_arguments(),
        configuration=Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert result["status"] == "failure"
    assert "Work item not found" in str(result["message"])
    assert "raw session cleanup" not in str(result["message"])


@pytest.mark.asyncio
async def test_status_update_session_exit_cancellation_propagates() -> None:
    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "exit_cancelled": True,
    }
    driver = _Driver(state)

    with pytest.raises(asyncio.CancelledError):
        await update_work_item_status(
            _valid_status_arguments(),
            configuration=Settings(neo4j_database="atlas-test"),
            driver=driver,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_status_update_cancellation_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import projectops_mcp.tools as tools_module

    state = {
        "project_exists": True,
        "work_item_exists": True,
        "work_item_belongs": True,
        "execute_cancelled": True,
    }
    driver = _Driver(state)
    monkeypatch.setattr(
        tools_module.AsyncGraphDatabase,
        "driver",
        lambda *_args, **_kwargs: driver,
    )
    configuration = Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="test-password",
        neo4j_database="neo4j",
    )

    with pytest.raises(asyncio.CancelledError):
        await update_work_item_status(
            _valid_status_arguments(),
            configuration=configuration,
        )
