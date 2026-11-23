"""Platform-wide configuration (docs/plan/09-operations-security-quality.md, section 5).

Unprefixed variables shared by every role: region, public URLs, vault, signing
keys, object storage, WorkOS and the platform GitHub App bootstrap. Secrets stay
``SecretStr`` so they never print.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True
    )

    region: str = Field(default="us", pattern=r"^[a-z0-9]{2,8}$")
    public_api_url: str = "http://localhost:8000"
    public_dash_url: str = "http://localhost:3000"

    # Vault (part 3, section 5)
    vault_key_provider: str = "local"
    vault_master_key: SecretStr | None = None
    # The KEK's public half (base64). The API needs only this; when unset in local
    # development it is derived from the master key (part 3, section 5).
    vault_kek_public_key: str | None = None
    ingress_key: SecretStr | None = None
    # STORE-09: "1:<base64 key>,2:<...>"; when set, stored vendor payloads are encrypted.
    payload_keys: SecretStr | None = None
    api_key_pepper: SecretStr | None = None
    cursor_signing_key: SecretStr | None = None

    # Object storage (raw page archive)
    blob_endpoint: str | None = None
    blob_bucket: str = "securefabric-raw"
    blob_access_key: SecretStr | None = None
    blob_secret_key: SecretStr | None = None
    blob_region: str = "us-east-1"

    # WorkOS (dashboard sign-in)
    workos_client_id: str | None = None
    workos_api_key: SecretStr | None = None
    workos_api_url: str = "https://api.workos.com"

    # Platform GitHub Apps (bootstrapped into control.vendor_app on first start)
    github_app_base_url: str = "https://github.com"
    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_app_client_id: str | None = None
    github_app_client_secret: SecretStr | None = None
    github_app_webhook_secret: SecretStr | None = None
    github_app_private_key_path: Path | None = None
    github_app_rw_id: str | None = None
    github_app_rw_slug: str | None = None
    github_app_rw_client_id: str | None = None
    github_app_rw_client_secret: SecretStr | None = None
    github_app_rw_webhook_secret: SecretStr | None = None
    github_app_rw_private_key_path: Path | None = None

    # Enrichment
    nvd_api_key: SecretStr | None = None

    # Egress policy: allow private addresses (local SANDBOX, tests). Never in prod.
    egress_allow_private: bool = False


@lru_cache
def get_platform_settings() -> PlatformSettings:
    return PlatformSettings()
