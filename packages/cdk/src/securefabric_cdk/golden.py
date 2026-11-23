"""Golden output (CDK-05): ``normalize`` over each fixture equals a committed snapshot.

A mapping change shows up as a diff in review. Regenerate with
``SF_UPDATE_GOLDEN=1 pytest packages/connectors``.
"""

import json
import os
from pathlib import Path
from typing import Any

from securefabric_cdk.connector import Stream
from securefabric_cdk.types import NormalizeContext, RawItem, Skip, Tombstone


def normalize_all(
    stream: Stream, items: list[RawItem], nctx: NormalizeContext
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in items:
        result = stream.normalize(raw, nctx)
        if isinstance(result, Skip):
            out.append({"skip": result.reason})
        elif isinstance(result, Tombstone):
            out.append({"tombstone": result.natural_key, "object": result.object})
        else:
            out.append(result.model_dump(mode="json", exclude={"vendor_data"}))
    return out


def assert_golden(path: Path, output: list[dict[str, Any]]) -> None:
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if os.environ.get("SF_UPDATE_GOLDEN") or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        if not os.environ.get("SF_UPDATE_GOLDEN"):
            raise AssertionError(f"golden file {path} did not exist; created it, review and commit")
        return
    expected = path.read_text(encoding="utf-8")
    if expected != rendered:
        raise AssertionError(
            f"normalised output differs from {path}; rerun with SF_UPDATE_GOLDEN=1 and review the diff"
        )
