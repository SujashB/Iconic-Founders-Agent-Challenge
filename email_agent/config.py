"""Centralized config loader. Reads .env once and exposes typed knobs."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _get_int(key: str, default: int) -> int:
    raw = _get(key)
    return int(raw) if raw else default


def _get_float(key: str, default: float) -> float:
    raw = _get(key)
    return float(raw) if raw else default


def _get_bool(key: str, default: bool) -> bool:
    raw = _get(key).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def _get_list(key: str, default: list[str] | None = None) -> list[str]:
    raw = _get(key)
    if not raw:
        return list(default or [])
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Config:
    # LLM (local Ollama)
    ollama_model: str = field(default_factory=lambda: _get("OLLAMA_MODEL", "qwen3:1.7b"))
    sentiment_ollama_model: str = field(
        default_factory=lambda: _get("SENTIMENT_OLLAMA_MODEL", "deepseek-r1:1.5b")
    )
    ollama_base_url: str = field(
        default_factory=lambda: _get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    )

    # Legacy OpenRouter settings. Kept so existing .env files do not break.
    openrouter_api_key: str = field(default_factory=lambda: _get("OPENROUTER_API_KEY"))
    openrouter_model: str = field(
        default_factory=lambda: _get("OPENROUTER_MODEL", "anthropic/claude-opus-4.6-fast")
    )
    openrouter_base_url: str = field(
        default_factory=lambda: _get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    )

    # Microsoft 365
    ms_client_id: str = field(default_factory=lambda: _get("MS_CLIENT_ID"))
    ms_client_secret: str = field(default_factory=lambda: _get("MS_CLIENT_SECRET"))
    ms_tenant_id: str = field(default_factory=lambda: _get("MS_TENANT_ID"))
    o365_token_path: Path = field(default_factory=lambda: REPO_ROOT / "o365_token.txt")

    # Trigger / scanner knobs
    stale_ra_days: int = field(default_factory=lambda: _get_int("STALE_RA_DAYS", 10))
    post_meeting_lookback_hours: int = field(
        default_factory=lambda: _get_int("POST_MEETING_LOOKBACK_HOURS", 6)
    )
    ra_domain_allowlist: list[str] = field(
        default_factory=lambda: _get_list("RA_DOMAIN_ALLOWLIST")
    )

    # Beam.ai / Medallia
    beam_api_key: str = field(default_factory=lambda: _get("BEAM_API_KEY"))
    medallia_tenant: str = field(default_factory=lambda: _get("MEDALLIA_TENANT"))
    medallia_program_id: str = field(default_factory=lambda: _get("MEDALLIA_PROGRAM_ID"))
    medallia_auth_token: str = field(default_factory=lambda: _get("MEDALLIA_AUTH_TOKEN"))
    sentiment_timeout_s: float = field(
        default_factory=lambda: _get_float("SENTIMENT_TIMEOUT_S", 20.0)
    )
    sentiment_poll_interval_s: float = field(
        default_factory=lambda: _get_float("SENTIMENT_POLL_INTERVAL_S", 2.0)
    )
    medallia_delete_after_score: bool = field(
        default_factory=lambda: _get_bool("MEDALLIA_DELETE_AFTER_SCORE", True)
    )

    # Composio MCP (alternative to direct O365)
    use_composio: bool = field(default_factory=lambda: _get_bool("USE_COMPOSIO", True))
    composio_api_key: str = field(default_factory=lambda: _get("COMPOSIO_API_KEY"))
    composio_mcp_url: str = field(
        default_factory=lambda: _get(
            "COMPOSIO_MCP_URL",
            "https://backend.composio.dev/v3/mcp/192481e1-141c-47b8-9c1a-2763908f9250"
            "/mcp?user_id=pg-test-Ha3tSUoFsCRq17bfBBFH2E698ijlzQlC",
        )
    )

    # Paths
    state_dir: Path = field(default_factory=lambda: REPO_ROOT / ".agent_state")
    fixtures_dir: Path = field(default_factory=lambda: REPO_ROOT / "fixtures")
    outputs_dir: Path = field(default_factory=lambda: REPO_ROOT / "outputs")

    @property
    def has_o365_creds(self) -> bool:
        return bool(self.ms_client_id and self.ms_client_secret and self.ms_tenant_id)

    @property
    def has_composio(self) -> bool:
        return bool(self.use_composio and self.composio_mcp_url)

    @property
    def has_beam_creds(self) -> bool:
        return bool(self.beam_api_key and self.medallia_program_id)


CONFIG = Config()
CONFIG.state_dir.mkdir(exist_ok=True)
CONFIG.outputs_dir.mkdir(exist_ok=True)
