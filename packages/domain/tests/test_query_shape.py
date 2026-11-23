"""The data API's scope predicates keep the plan on an index (benchmark gate, NFR-04).

`connection_id = any($1)` once hid a single connection from the planner: it scanned
and sorted a whole 100k-row partition per page (p50 4.3 s at 50 req/s, ~100x slower
than an index walk). These checks pin the predicate shapes that let the indexes
(connection_id, updated_at, id) and (organization_id, updated_at, id) drive the order.
"""

import uuid
from types import SimpleNamespace

from securefabric_domain.data_api import Scope, _common_where


def _sql(parts) -> str:
    return " and ".join(p._obj if hasattr(p, "_obj") else str(p) for p in parts)


def _q(**kw):
    base = {"updated_since": None, "ids": None, "state": None, "change_type": None}
    return SimpleNamespace(**{**base, **kw})


def test_one_connection_is_an_equality() -> None:
    cid = uuid.uuid4()
    where, params = _common_where("f", Scope("connection", [cid], None, ["SANDBOX"]), _q(), True)
    text = _sql(where)
    assert "f.connection_id = %s" in text and "any(" not in text
    assert params[0] == cid


def test_organization_scope_leads_with_organization_id() -> None:
    org, a, b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    where, params = _common_where("f", Scope("organization", [a, b], org, ["SANDBOX"]), _q(), True)
    text = _sql(where)
    assert text.startswith("f.organization_id = %s")
    assert "f.connection_id = any(%s)" in text
    assert params[:2] == [org, [a, b]]
