import pytest

from securefabric_core import NotFoundError
from securefabric_domain import get_catalog, provider_or_404
from securefabric_domain.models import ALL_KEY_SCOPES, Workspace
from securefabric_domain.service import (
    full_counts,
    key_preview,
    mask_value,
    masked_credentials,
    slugify,
    unique_key,
)
from securefabric_domain.status import worst


def test_catalog_is_the_dash_export() -> None:
    catalog = get_catalog()
    assert len(catalog.providers) > 50
    tenable = provider_or_404("tenable")
    assert "vulnerabilities" in tenable.models
    assert set(tenable.models) <= set(catalog.models)


def test_unknown_provider_is_404() -> None:
    with pytest.raises(NotFoundError):
        provider_or_404("not-a-vendor")


def test_secrets_are_masked_but_ids_are_kept() -> None:
    masked = masked_credentials("tenable", {"access_key": "AK123", "secret_key": "s3cr3t-9876"})
    assert masked == {"access_key": "AK123", "secret_key": "••••••••••••9876"}
    assert mask_value("abc") == "••••"


@pytest.mark.parametrize(
    ("name", "slug"),
    [("Staging", "staging"), ("  EU Prod 2 ", "eu-prod-2"), ("QA/Test!", "qatest")],
)
def test_slugify(name: str, slug: str) -> None:
    assert slugify(name) == slug


def test_unique_key_suffixes() -> None:
    assert unique_key("wiz", set()) == "wiz"
    assert unique_key("wiz", {"wiz", "wiz-2"}) == "wiz-3"


def test_key_preview_hides_the_middle() -> None:
    assert key_preview("sk_test_abcdefghijklmnop") == "sk_test…mnop"


def test_counts_are_deterministic_per_connection() -> None:
    a = full_counts("conn_1", ["vulnerabilities", "devices"])
    assert a == full_counts("conn_1", ["vulnerabilities", "devices"])
    assert 800 <= a["vulnerabilities"] <= 14_000


def test_status_rollup_takes_the_worst() -> None:
    assert worst([]) == "ok"
    assert worst(["ok", "degraded"]) == "degraded"
    assert worst(["degraded", "down", "ok"]) == "down"


def test_schema_is_camel_case() -> None:
    schema = Workspace.model_json_schema(mode="serialization")
    assert "seededAt" in schema["properties"]
    assert len(ALL_KEY_SCOPES) == len(set(ALL_KEY_SCOPES))
