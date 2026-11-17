"""MCP action implementations for ProjectOps."""

import asyncio
from collections.abc import Mapping

from neo4j import AsyncDriver, AsyncGraphDatabase

from config.settings import Settings, settings
from projectops_mcp.schemas import ACTION_TOOL_SCHEMAS

_ASSIGNMENT_VALIDATION_QUERY = """
OPTIONAL MATCH (project:Project {id: $project_id})
OPTIONAL MATCH (work_item:WorkItem {id: $work_item_id})
OPTIONAL MATCH (work_item)-[:BELONGS_TO]->(member_project:Project {id: $project_id})
OPTIONAL MATCH (assignee:Person {id: $assignee_id})
RETURN project IS NOT NULL AS project_exists,
       work_item IS NOT NULL AS work_item_exists,
       member_project IS NOT NULL AS work_item_belongs,
       assignee IS NOT NULL AS assignee_exists
"""

_ASSIGNMENT_UPDATE_QUERY = """
MATCH (work_item:WorkItem {id: $work_item_id})-[:BELONGS_TO]->(:Project {id: $project_id})
MATCH (assignee:Person {id: $assignee_id})
SET work_item.assignee_id = $assignee_id
WITH work_item, assignee
OPTIONAL MATCH (work_item)-[existing_assignee:ASSIGNED_TO]->(:Person)
DELETE existing_assignee
WITH work_item, assignee
MERGE (work_item)-[:ASSIGNED_TO]->(assignee)
RETURN work_item.id AS work_item_id
"""

_STATUS_VALIDATION_QUERY = """
OPTIONAL MATCH (project:Project {id: $project_id})
OPTIONAL MATCH (work_item:WorkItem {id: $work_item_id})
OPTIONAL MATCH (work_item)-[:BELONGS_TO]->(member_project:Project {id: $project_id})
RETURN project IS NOT NULL AS project_exists,
       work_item IS NOT NULL AS work_item_exists,
       member_project IS NOT NULL AS work_item_belongs
"""

_STATUS_UPDATE_QUERY = """
MATCH (work_item:WorkItem {id: $work_item_id})-[:BELONGS_TO]->(:Project {id: $project_id})
SET work_item.status = $status
RETURN work_item.id AS work_item_id
"""


def _validate_assign_arguments(arguments: Mapping[str, object]) -> dict[str, object] | None:
    if not isinstance(arguments, Mapping):
        return {
            "status": "failure",
            "work_item_id": "",
            "message": "Assignment arguments must be an object.",
        }

    input_schema = ACTION_TOOL_SCHEMAS["assign_work_item"]["input_schema"]
    properties = input_schema["properties"]
    required = input_schema["required"]

    if not isinstance(properties, dict) or not isinstance(required, list):
        return {
            "status": "failure",
            "work_item_id": "",
            "message": "Invalid assignment schema configuration.",
        }

    allowed_properties = set(properties)
    if set(arguments) - allowed_properties:
        return {
            "status": "failure",
            "work_item_id": arguments.get("work_item_id")
            if isinstance(arguments.get("work_item_id"), str)
            else "",
            "message": "Assignment arguments contain unexpected properties.",
        }

    for name in required:
        if name not in arguments:
            return {
                "status": "failure",
                "work_item_id": arguments.get("work_item_id")
                if isinstance(arguments.get("work_item_id"), str)
                else "",
                "message": f"Missing required assignment argument: {name}.",
            }

    for name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            return {
                "status": "failure",
                "work_item_id": arguments.get("work_item_id")
                if isinstance(arguments.get("work_item_id"), str)
                else "",
                "message": "Invalid assignment schema configuration.",
            }

        value = arguments[name]
        if property_schema.get("type") == "string" and not isinstance(value, str):
            return {
                "status": "failure",
                "work_item_id": arguments.get("work_item_id")
                if isinstance(arguments.get("work_item_id"), str)
                else "",
                "message": f"Assignment argument '{name}' must be a string.",
            }

    return None


def _validate_status_arguments(arguments: Mapping[str, object]) -> dict[str, object] | None:
    if not isinstance(arguments, Mapping):
        return {
            "status": "failure",
            "work_item_id": "",
            "message": "Status update arguments must be an object.",
        }

    input_schema = ACTION_TOOL_SCHEMAS["update_work_item_status"]["input_schema"]
    properties = input_schema["properties"]
    required = input_schema["required"]

    if not isinstance(properties, dict) or not isinstance(required, list):
        return {
            "status": "failure",
            "work_item_id": "",
            "message": "Invalid status update schema configuration.",
        }

    allowed_properties = set(properties)
    if set(arguments) - allowed_properties:
        work_item_id = arguments.get("work_item_id")
        return {
            "status": "failure",
            "work_item_id": work_item_id if isinstance(work_item_id, str) else "",
            "message": "Status update arguments contain unexpected properties.",
        }

    for name in required:
        if name not in arguments:
            work_item_id = arguments.get("work_item_id")
            return {
                "status": "failure",
                "work_item_id": work_item_id if isinstance(work_item_id, str) else "",
                "message": f"Missing required status update argument: {name}.",
            }

    for name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            work_item_id = arguments.get("work_item_id")
            return {
                "status": "failure",
                "work_item_id": work_item_id if isinstance(work_item_id, str) else "",
                "message": "Invalid status update schema configuration.",
            }

        value = arguments[name]
        if property_schema.get("type") == "string" and not isinstance(value, str):
            work_item_id = arguments.get("work_item_id")
            return {
                "status": "failure",
                "work_item_id": work_item_id if isinstance(work_item_id, str) else "",
                "message": f"Status update argument '{name}' must be a string.",
            }

    status_schema = properties["status"]
    if not isinstance(status_schema, dict):
        work_item_id = arguments["work_item_id"]
        return {
            "status": "failure",
            "work_item_id": work_item_id if isinstance(work_item_id, str) else "",
            "message": "Invalid status update schema configuration.",
        }

    allowed_statuses = status_schema.get("enum")
    if not isinstance(allowed_statuses, list):
        work_item_id = arguments["work_item_id"]
        return {
            "status": "failure",
            "work_item_id": work_item_id,
            "message": "Invalid status update schema configuration.",
        }

    if arguments["status"] not in allowed_statuses:
        work_item_id = arguments["work_item_id"]
        return {
            "status": "failure",
            "work_item_id": work_item_id,
            "message": "Invalid work-item status.",
        }

    return None


def _create_driver(configuration: Settings) -> AsyncDriver:
    password = configuration.neo4j_password
    if password is None or not password.get_secret_value():
        raise ValueError("Neo4j password must be configured")
    if not configuration.neo4j_uri.strip():
        raise ValueError("Neo4j URI must not be empty")
    if not configuration.neo4j_username.strip():
        raise ValueError("Neo4j username must not be empty")
    if not configuration.neo4j_database.strip():
        raise ValueError("Neo4j database must not be empty")

    return AsyncGraphDatabase.driver(
        configuration.neo4j_uri,
        auth=(configuration.neo4j_username, password.get_secret_value()),
    )


async def assign_work_item(
    arguments: Mapping[str, object],
    *,
    configuration: Settings = settings,
    driver: AsyncDriver | None = None,
) -> dict[str, object]:
    """Assign an existing Atlas work item to an existing person."""
    if not isinstance(arguments, Mapping):
        return {
            "status": "failure",
            "work_item_id": "",
            "message": "Assignment arguments must be an object.",
        }

    supplied_work_item_id = arguments.get("work_item_id")
    valid_supplied_work_item_id = (
        supplied_work_item_id if isinstance(supplied_work_item_id, str) else ""
    )

    validation_error = _validate_assign_arguments(arguments)
    if validation_error is not None:
        return _failure_result(validation_error, valid_supplied_work_item_id)

    project_id = arguments["project_id"]
    work_item_id = arguments["work_item_id"]
    assignee_id = arguments["assignee_id"]

    own_driver = driver is None
    neo4j_driver: AsyncDriver | None = driver
    if neo4j_driver is None:
        try:
            neo4j_driver = _create_driver(configuration)
        except Exception:
            return _failure_result(
                {
                    "status": "failure",
                    "message": "Unable to initialize the assignment service.",
                },
                work_item_id,
            )

    result: dict[str, object]
    try:
        try:
            async with neo4j_driver.session(database=configuration.neo4j_database) as session:

                async def validate_and_assign(transaction: object) -> bool:
                    validation_result = await transaction.run(  # type: ignore[attr-defined]
                        _ASSIGNMENT_VALIDATION_QUERY,
                        project_id=project_id,
                        work_item_id=work_item_id,
                        assignee_id=assignee_id,
                    )
                    validation = await validation_result.single()
                    if validation is None:
                        raise AssignmentValidationError(
                            "Unable to validate the work-item assignment."
                        )

                    if not validation["project_exists"]:
                        raise AssignmentValidationError("Project not found.")
                    if not validation["work_item_exists"]:
                        raise AssignmentValidationError("Work item not found.")
                    if not validation["work_item_belongs"]:
                        raise AssignmentValidationError(
                            "Work item does not belong to the supplied project."
                        )
                    if not validation["assignee_exists"]:
                        raise AssignmentValidationError("Assignee person not found.")

                    update_result = await transaction.run(  # type: ignore[attr-defined]
                        _ASSIGNMENT_UPDATE_QUERY,
                        project_id=project_id,
                        work_item_id=work_item_id,
                        assignee_id=assignee_id,
                    )
                    updated = await update_result.single()
                    if updated is None or updated.get("work_item_id") != work_item_id:
                        raise AssignmentValidationError(
                            "Unable to persist the work-item assignment."
                        )
                    return True

                transaction_result = await session.execute_write(validate_and_assign)
                if transaction_result is not True:
                    result = _failure_result(
                        {
                            "status": "failure",
                            "message": "Unable to complete the work-item assignment.",
                        },
                        work_item_id,
                    )
                else:
                    result = {
                        "status": "success",
                        "work_item_id": work_item_id,
                        "assignee_id": assignee_id,
                        "message": "Work item assigned successfully.",
                    }
        except AssignmentValidationError as error:
            result = _failure_result(
                {"status": "failure", "message": str(error)},
                work_item_id,
            )
        except Exception:
            result = _failure_result(
                {
                    "status": "failure",
                    "message": "Unable to complete the work-item assignment.",
                },
                work_item_id,
            )
    finally:
        if own_driver:
            try:
                await neo4j_driver.close()
            except Exception:
                pass

    return result


async def update_work_item_status(
    arguments: Mapping[str, object],
    *,
    configuration: Settings = settings,
    driver: AsyncDriver | None = None,
) -> dict[str, object]:
    """Update an existing Atlas work item status without changing other fields."""
    if not isinstance(arguments, Mapping):
        return {
            "status": "failure",
            "work_item_id": "",
            "message": "Status update arguments must be an object.",
        }

    supplied_work_item_id = arguments.get("work_item_id")
    valid_supplied_work_item_id = (
        supplied_work_item_id if isinstance(supplied_work_item_id, str) else ""
    )

    validation_error = _validate_status_arguments(arguments)
    if validation_error is not None:
        return _failure_result(validation_error, valid_supplied_work_item_id)

    project_id = arguments["project_id"]
    work_item_id = arguments["work_item_id"]
    status = arguments["status"]

    own_driver = driver is None
    neo4j_driver: AsyncDriver | None = driver
    if neo4j_driver is None:
        try:
            neo4j_driver = _create_driver(configuration)
        except Exception:
            return _failure_result(
                {
                    "status": "failure",
                    "message": "Unable to initialize the status update service.",
                },
                work_item_id,
            )

    result: dict[str, object]
    try:
        try:
            session_context = neo4j_driver.session(database=configuration.neo4j_database)
            session = await session_context.__aenter__()
        except Exception:
            result = _failure_result(
                {
                    "status": "failure",
                    "message": "Unable to complete the work-item status update.",
                },
                work_item_id,
            )
        else:
            try:

                async def validate_and_update(transaction: object) -> bool:
                    validation_result = await transaction.run(  # type: ignore[attr-defined]
                        _STATUS_VALIDATION_QUERY,
                        project_id=project_id,
                        work_item_id=work_item_id,
                    )
                    validation = await validation_result.single()
                    if validation is None:
                        raise AssignmentValidationError(
                            "Unable to validate the work-item status update."
                        )

                    if not validation["project_exists"]:
                        raise AssignmentValidationError("Project not found.")
                    if not validation["work_item_exists"]:
                        raise AssignmentValidationError("Work item not found.")
                    if not validation["work_item_belongs"]:
                        raise AssignmentValidationError(
                            "Work item does not belong to the supplied project."
                        )

                    update_result = await transaction.run(  # type: ignore[attr-defined]
                        _STATUS_UPDATE_QUERY,
                        project_id=project_id,
                        work_item_id=work_item_id,
                        status=status,
                    )
                    updated = await update_result.single()
                    if updated is None or updated.get("work_item_id") != work_item_id:
                        raise AssignmentValidationError(
                            "Unable to persist the work-item status update."
                        )
                    return True

                transaction_result = await session.execute_write(validate_and_update)
                if transaction_result is not True:
                    result = _failure_result(
                        {
                            "status": "failure",
                            "message": "Unable to complete the work-item status update.",
                        },
                        work_item_id,
                    )
                else:
                    result = {
                        "status": "success",
                        "work_item_id": work_item_id,
                        "new_status": status,
                        "message": "Work item status updated successfully.",
                    }
            except AssignmentValidationError as error:
                result = _failure_result(
                    {"status": "failure", "message": str(error)},
                    work_item_id,
                )
            except Exception:
                result = _failure_result(
                    {
                        "status": "failure",
                        "message": "Unable to complete the work-item status update.",
                    },
                    work_item_id,
                )
            finally:
                try:
                    await session_context.__aexit__(None, None, None)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
    finally:
        if own_driver:
            try:
                await neo4j_driver.close()
            except Exception:
                pass

    return result


class AssignmentValidationError(Exception):
    """A clear domain validation failure within an assignment transaction."""


def _failure_result(
    result: Mapping[str, object],
    work_item_id: str,
) -> dict[str, object]:
    failure: dict[str, object] = {
        "status": "failure",
        "work_item_id": work_item_id,
        "message": str(result["message"]),
    }
    return failure
