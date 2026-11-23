"""The provider catalog the dash shows, as the backend sees it.

``catalog.json`` is generated from ``apps/dash/src/lib/catalog.ts`` (the source of
truth for provider content) and checked for drift in CI, so the API validates
providers, models and credential fields against exactly what the UI offers.
"""

import json
from functools import cache
from importlib.resources import files

from pydantic import BaseModel, ConfigDict

from securefabric_core import NotFoundError
from securefabric_domain.models import ModelKey


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)


class CredentialField(_Model):
    key: str
    secret: bool
    options: list[str] | None = None


class WriteAction(_Model):
    endpoint: str
    name: str
    scope: str


class Provider(_Model):
    slug: str
    name: str
    status: str
    models: list[ModelKey]
    fields: list[CredentialField]
    write_actions: list[WriteAction]

    model_config = ConfigDict(frozen=True, populate_by_name=True, alias_generator=None)


class Catalog(_Model):
    models: list[ModelKey]
    providers: dict[str, Provider]


@cache
def get_catalog() -> Catalog:
    raw = json.loads(files("securefabric_domain").joinpath("catalog.json").read_text())
    providers = {
        p["slug"]: Provider(
            slug=p["slug"],
            name=p["name"],
            status=p["status"],
            models=p["models"],
            fields=[CredentialField(**f) for f in p["fields"]],
            write_actions=[WriteAction(**a) for a in p["writeActions"]],
        )
        for p in raw["providers"]
    }
    return Catalog(models=raw["models"], providers=providers)


def provider_or_404(slug: str) -> Provider:
    provider = get_catalog().providers.get(slug)
    if provider is None:
        raise NotFoundError("Unknown provider", provider=slug)
    return provider
