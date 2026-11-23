"""Capabilities (CAT-02, CAT-03).

The manifest declares what each stream supports. ``values_emitted`` is not
written by hand: ``securefabric-cdk capabilities`` computes it from the golden
output of the fixtures into ``capabilities.json`` beside the manifest, and CI
fails if the manifest claims a value no fixture produces.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache
def connector_capabilities(connector_id: str) -> dict[str, Any]:
    import securefabric_connectors

    base = (
        Path(securefabric_connectors.__file__).parent / connector_id.lower() / "capabilities.json"
    )
    if not base.exists():
        return {}
    data: dict[str, Any] = json.loads(base.read_text(encoding="utf-8"))
    return data
