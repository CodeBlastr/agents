from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_TAX_SOURCE_URLS = (
    "https://syracuse.go2gov.net/faces/accounts?number=0562001300&src=SDG",
    "https://syracuse.go2gov.net/faces/accounts?number=1626103200&src=SDG",
    "https://syracuse.go2gov.net/faces/accounts?number=0716100700&src=SDG",
)

PROVIDER_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY", "LLM_MODEL"),
}


@dataclass(frozen=True)
class AppSettings:
    database_url: str
    artifacts_dir: str
    llm_provider: str
    llm_model: str
    openai_api_key: str | None
    dashboard_port: int
    notification_text_phone: str
    tax_source_urls: tuple[str, ...]


def _require_env_present(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required env variable: {name}")
    return value


def _parse_dashboard_port() -> int:
    raw = _require_env_present("DASHBOARD_PORT").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("DASHBOARD_PORT must be an integer") from exc
    if value <= 0:
        raise RuntimeError("DASHBOARD_PORT must be greater than 0")
    return value


def _validate_llm_env(provider: str) -> None:
    requirements = PROVIDER_REQUIREMENTS.get(provider)
    if requirements is None:
        supported = ", ".join(sorted(PROVIDER_REQUIREMENTS.keys()))
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER '{provider}'. Supported providers: {supported}"
        )

    for key in requirements:
        value = os.getenv(key)
        if value is None or not value.strip():
            raise RuntimeError(f"Missing required env variable: {key}")


def load_settings() -> AppSettings:
    llm_provider = _require_env_present("LLM_PROVIDER").strip().lower()
    llm_model = _require_env_present("LLM_MODEL").strip()
    dashboard_port = _parse_dashboard_port()
    notification_text_phone = _require_env_present("NOTIFICATION_TEXT_PHONE")
    _validate_llm_env(llm_provider)

    return AppSettings(
        database_url=os.getenv(
            "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/agents"
        ),
        artifacts_dir=os.getenv("ARTIFACTS_DIR", "/artifacts"),
        llm_provider=llm_provider,
        llm_model=llm_model,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        dashboard_port=dashboard_port,
        notification_text_phone=notification_text_phone,
        tax_source_urls=DEFAULT_TAX_SOURCE_URLS,
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return load_settings()
