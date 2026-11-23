"""The audit log endpoints are for signed-in people and take only known filters."""


async def test_audit_log_needs_a_session(api) -> None:
    for path in ("/v1/audit_events", "/v1/audit_events/facets"):
        r = await api.get(path)
        assert r.status_code == 403, r.text
        assert r.json()["code"] == "session_required"


async def test_audit_log_rejects_unknown_filters(api) -> None:
    r = await api.get("/v1/audit_events", params={"actor": "x"})
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "unknown_parameter"
