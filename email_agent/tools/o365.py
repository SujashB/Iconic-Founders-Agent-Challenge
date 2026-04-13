"""Thin wrapper around the langchain-community Office365 toolkit.

Returns None for the toolkit and individual tools when O365 credentials or a
cached OAuth token are not available, so callers can degrade to fixture mode.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from email_agent.config import CONFIG

log = logging.getLogger("email_agent.o365")


@lru_cache(maxsize=1)
def get_account() -> Any | None:
    """Return an authenticated O365.Account, or None if unavailable."""
    if not CONFIG.has_o365_creds:
        log.info("o365: MS_CLIENT_ID/SECRET/TENANT not set; running offline")
        return None
    try:
        from O365 import Account, FileSystemTokenBackend
    except ImportError:
        log.warning("o365: O365 library not installed")
        return None
    try:
        token_backend = FileSystemTokenBackend(
            token_path=str(CONFIG.o365_token_path.parent),
            token_filename=CONFIG.o365_token_path.name,
        )
        account = Account(
            credentials=(CONFIG.ms_client_id, CONFIG.ms_client_secret),
            tenant_id=CONFIG.ms_tenant_id,
            token_backend=token_backend,
        )
        if not account.is_authenticated:
            log.warning("o365: account not authenticated; run outlook_auth.py first")
            return None
        return account
    except Exception as exc:  # noqa: BLE001
        log.warning("o365: account init failed: %s", exc)
        return None


@lru_cache(maxsize=1)
def get_toolkit() -> Any | None:
    """Return the langchain-community O365Toolkit, or None if no auth."""
    account = get_account()
    if account is None:
        return None
    try:
        from langchain_community.agent_toolkits import O365Toolkit

        return O365Toolkit(account=account)
    except Exception as exc:  # noqa: BLE001
        log.warning("o365: toolkit init failed: %s", exc)
        return None


def get_tool(name: str) -> Any | None:
    toolkit = get_toolkit()
    if toolkit is None:
        return None
    for tool in toolkit.get_tools():
        if tool.name == name:
            return tool
    return None
