"""Centralized application configuration via Pydantic Settings.

All environment variables for the Agentcys Platform are defined here.
Values are loaded from a .env file (if present) and overridden by real
environment variables at runtime.

Sections:
    App         — Environment, CORS, request limits
    GCP         — Project IDs, bucket names, Cloud Tasks
    Auth        — HMAC signing secret for service-to-service auth
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_ENVS = {"local", "dev", "test", "prod"}


def _parse_origin_values(value: object) -> list[str]:
    """Accept JSON arrays, comma-separated strings, or plain iterables."""
    if value is None:
        return []

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return [p.strip() for p in raw.split(",") if p.strip()]

        if isinstance(parsed, str):
            return [parsed]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]

        msg = "CORS_ALLOWED_ORIGINS must be a JSON array or comma-separated string"
        raise ValueError(msg)

    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]

    return [str(value).strip()]


def _normalize_origins(origins: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for origin in origins:
        cleaned = origin.strip().rstrip("/")
        if not cleaned or cleaned in seen:
            continue
        normalized.append(cleaned)
        seen.add(cleaned)
    return normalized


class Settings(BaseSettings):
    """Platform settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────
    APP_ENV: str = "dev"
    APP_PORT: int = 8080
    DEBUG: bool = False

    # CORS — comma-separated list; no wildcards when credentials are involved
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Maximum request body size in bytes (default 1 MiB)
    REQUEST_MAX_BODY_BYTES: int = 1_048_576

    # ── GCP ──────────────────────────────────────────────────────────────
    GCP_PROJECT_ID: str  # Our GCP project that hosts the platform
    SECRET_MANAGER_PROJECT: str  # Project hosting Secret Manager secrets

    # GCS bucket in our project that mirrors customer Terraform state
    STATE_MIRROR_BUCKET: str

    # GCS bucket hosting versioned Terraform module tarballs
    BLUEPRINT_BUCKET: str

    # Cloud Tasks queue used to dispatch worker jobs
    CLOUD_TASKS_QUEUE: str
    CLOUD_TASKS_LOCATION: str = "us-central1"
    DEPLOYMENT_TASK_TARGET_URL: str = "https://worker.invalid/tasks/deployments"

    # ── Auth ─────────────────────────────────────────────────────────────
    HMAC_SIGNING_SECRET: str  # HMAC-SHA256 secret for API ↔ Worker auth

    # ── Validators ───────────────────────────────────────────────────────

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def _validate_app_env(cls, v: str) -> str:
        normalized = str(v or "").strip().lower()
        if normalized not in _VALID_ENVS:
            print(  # noqa: T201
                f"[FATAL] APP_ENV='{v}' is not a valid environment. "
                f"Must be one of: {sorted(_VALID_ENVS)}",
                file=sys.stderr,
            )
            sys.exit(1)
        return normalized

    def get_cors_origins(self) -> list[str]:
        """Return the parsed and normalised CORS origin list."""
        return _normalize_origins(_parse_origin_values(self.CORS_ALLOWED_ORIGINS))

    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance.

    In tests, call ``get_settings.cache_clear()`` before patching env vars.
    """
    return Settings()
