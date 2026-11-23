"""The OpenAPI document is a contract: the TypeScript client is generated from it."""

from typing import Any

from securefabric_api.openapi import build_schema


def _operations(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {op["operationId"]: op for path in schema["paths"].values() for op in path.values()}


def test_operation_ids_are_stable_tag_and_name() -> None:
    assert set(_operations(build_schema())) == {
        "health:live",
        "health:ready",
        "tenants:provision_tenant",
        "tasks:get_task",
        "tasks:cancel_task",
        "workspace:get_workspace",
        "workspace:reset_workspace",
        "environments:create_environment",
        "environments:update_environment",
        "environments:delete_environment",
        "environments:rotate_webhook_secret",
        "keys:create_api_key",
        "keys:update_api_key",
        "keys:roll_api_key",
        "keys:revoke_api_key",
        "webhooks:add_webhook",
        "webhooks:update_webhook",
        "webhooks:remove_webhook",
        "webhooks:deliver_webhook",
        "variables:set_variable",
        "variables:remove_variable",
        "integrations:enable_integration",
        "integrations:update_integration",
        "integrations:delete_integration",
        "connections:create_connection",
        "connections:trigger_sync",
        "connections:update_connection",
        "connections:update_credentials",
        "connections:simulate_health",
        "connections:delete_connection",
        "connect:create_connect_session",
        "operations:record_operation",
        "members:invite_member",
        "members:set_member_role",
        "members:remove_member",
        "status:get_status",
    }


def test_errors_use_the_envelope_schema() -> None:
    ops = _operations(build_schema())
    for op_id in ("tenants:provision_tenant", "tasks:get_task", "tasks:cancel_task"):
        for code in ("404", "422", "500"):
            content = ops[op_id]["responses"][code]["content"]["application/json"]
            assert content["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}


def test_response_defaults_are_required_but_request_defaults_are_not() -> None:
    schemas = build_schema()["components"]["schemas"]
    # Always sent, so required for the client...
    assert "status" in schemas["Liveness"]["required"]
    assert {"result", "failure"} <= set(schemas["TaskStatus"]["required"])
    # ...while callers may omit defaulted request fields.
    assert set(schemas["ProvisionTenantParams"]["required"]) == {"tenant_id", "admin_email"}


def test_control_plane_speaks_camel_case() -> None:
    schemas = build_schema()["components"]["schemas"]
    assert {"apiKeys", "webhookSecret", "isProduction"} <= set(schemas["Environment"]["required"])
    # Request bodies are camelCase too, and defaulted fields stay optional.
    assert schemas["ConnectionCreate"]["required"] == ["integrationId", "customer"]
    assert "409" in _operations(build_schema())["connections:trigger_sync"]["responses"]


def test_schema_is_deterministic() -> None:
    assert build_schema() == build_schema()
