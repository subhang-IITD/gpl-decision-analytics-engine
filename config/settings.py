"""Central configuration for the GPL Decision Analytics Engine.

All settings are sourced from environment variables (12-factor style) so the
exact same codebase runs locally (SQLite, no keys) and on GPL's AWS
environment (RDS Postgres, real API keys) with only env changes.

Nothing here ever hardcodes a secret. Missing keys degrade gracefully to the
local data layer rather than crashing -- see ingestion adapters.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "_data"
DATA_DIR.mkdir(exist_ok=True)


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _default_db_url() -> str:
    """Pick the database when DATABASE_URL is unset.

    Priority: the local working DB if present, else the bundled read-only demo DB
    (real PropEquity market data, no GPL-internal records) so a fresh checkout --
    e.g. on Streamlit Community Cloud -- boots with data and zero setup.
    """
    if (url := os.getenv("DATABASE_URL")):
        return url
    working = DATA_DIR / "gpl.db"
    if working.exists():
        return f"sqlite:///{working}"
    demo = DATA_DIR / "demo.db"
    if demo.exists():
        return f"sqlite:///{demo}"
    return f"sqlite:///{working}"


@dataclass(frozen=True)
class DatabaseConfig:
    # If DATABASE_URL is set (e.g. postgresql+psycopg://user:pass@rds-host/db)
    # it is used verbatim. Otherwise we fall back to a local SQLite file so the
    # project is runnable with zero infrastructure.
    url: str = field(default_factory=lambda: _default_db_url())

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")


@dataclass(frozen=True)
class LLMConfig:
    # provider: "ollama" (self-hosted, brief-preferred), "anthropic", or "regex"
    provider: str = field(default_factory=lambda: os.getenv("GPL_LLM_PROVIDER", "regex"))
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"))


@dataclass(frozen=True)
class ApiKeysConfig:
    propequity_api_key: str | None = field(default_factory=lambda: os.getenv("PROPEQUITY_API_KEY"))
    propequity_base_url: str = field(default_factory=lambda: os.getenv("PROPEQUITY_BASE_URL", "https://api.propequity.in/v1"))
    google_maps_api_key: str | None = field(default_factory=lambda: os.getenv("GOOGLE_MAPS_API_KEY"))
    salesforce_token: str | None = field(default_factory=lambda: os.getenv("SALESFORCE_TOKEN"))
    salesforce_instance_url: str | None = field(default_factory=lambda: os.getenv("SALESFORCE_INSTANCE_URL"))


@dataclass(frozen=True)
class AlertingConfig:
    sendgrid_api_key: str | None = field(default_factory=lambda: os.getenv("SENDGRID_API_KEY"))
    sendgrid_from: str = field(default_factory=lambda: os.getenv("SENDGRID_FROM", "alerts@gpl-engine.local"))
    whatsapp_provider: str = field(default_factory=lambda: os.getenv("WHATSAPP_PROVIDER", "interakt"))
    whatsapp_api_key: str | None = field(default_factory=lambda: os.getenv("WHATSAPP_API_KEY"))
    admin_email: str = field(default_factory=lambda: os.getenv("GPL_ADMIN_EMAIL", "admin@gpl-engine.local"))


@dataclass(frozen=True)
class ScraperConfig:
    # When live scraping is disabled or a site blocks us, ingestion reads from
    # the seeded warehouse instead, so the app is always demonstrable.
    live_scraping_enabled: bool = field(default_factory=lambda: _get_bool("GPL_LIVE_SCRAPING", False))
    request_timeout_s: float = field(default_factory=lambda: _get_float("GPL_SCRAPER_TIMEOUT", 30.0))
    user_agent: str = field(
        default_factory=lambda: os.getenv(
            "GPL_SCRAPER_UA",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        )
    )
    default_radius_km: float = field(default_factory=lambda: _get_float("GPL_DEFAULT_RADIUS_KM", 3.0))


@dataclass(frozen=True)
class Settings:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    keys: ApiKeysConfig = field(default_factory=ApiKeysConfig)
    alerting: AlertingConfig = field(default_factory=AlertingConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    api_base_url: str = field(default_factory=lambda: os.getenv("GPL_API_URL", "http://localhost:8000"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
