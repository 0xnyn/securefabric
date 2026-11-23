"""The OpenAPI document: stable operation ids, one error shape, write-only secrets."""

from typing import Any

from securefabric_api.openapi import build_schema


def _operations(schema: dict[str, Any]) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for path, item in schema["paths"].items():
        for method, op in item.items():
            out[op["operationId"]] = (method, path)
    return out


def test_operation_ids_are_unique_and_tag_prefixed() -> None:
    schema = build_schema()
    ops = _operations(schema)
    count = sum(len(i) for i in schema["paths"].values())
    assert len(ops) == count, "duplicate operationId"
    assert all(":" in op for op in ops)
    for expected in (
        "organizations:create_organization",
        "connections:create_connection",
        "connections:list_connections",
        "api_keys:create_api_key",
        "connectors:list_connectors",
        "jobs:get_job",
        "account:get_me",
    ):
        assert expected in ops


def test_every_v1_path_is_versioned_and_errors_are_problem_json() -> None:
    schema = build_schema()
    for path, item in schema["paths"].items():
        assert path.startswith(("/v1/", "/health/")), path
        for op in item.values():
            for status, resp in op.get("responses", {}).items():
                if status.startswith(("4", "5")) and status != "503":
                    assert "Problem" in str(resp), (path, status)


def test_no_response_schema_carries_credentials() -> None:
    schema = build_schema()
    for name, comp in schema["components"]["schemas"].items():
        if name.endswith(("In", "Patch")) or "Body" in name or name in ("ConnectIn", "SessionIn"):
            continue
        for prop in comp.get("properties", {}):
            assert prop not in (
                "credentials",
                "secrets",
                "client_secret",
                "private_key",
                "webhook_secret",
            ), (name, prop)


def test_every_response_field_is_typed() -> None:
    # A catch-all serializer once erased every field's type (the TS client got `unknown`).
    schemas = build_schema()["components"]["schemas"]
    untyped = sorted(
        f"{name}.{field}"
        for name, schema in schemas.items()
        for field, prop in (schema.get("properties") or {}).items()
        if not ({"type", "$ref", "anyOf", "allOf", "oneOf", "items", "enum", "const"} & prop.keys())
    )
    assert untyped == ["PassthroughOut.body"]  # vendor JSON, deliberately open
    key = schemas["ApiKeyOut"]["properties"]["created_at"]
    assert key == {"type": "string", "format": "date-time", "title": "Created At"}
