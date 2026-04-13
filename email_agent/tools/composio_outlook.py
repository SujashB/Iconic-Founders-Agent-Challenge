"""Composio MCP client for Outlook operations.

Connects to the Composio MCP server via the Streamable HTTP transport
(direct HTTP connection with x-api-key auth) and exposes helpers the
scanners use to fetch emails and calendar events.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from email_agent.config import CONFIG

log = logging.getLogger("email_agent.composio")

MCP_URL = CONFIG.composio_mcp_url


def _auth_headers() -> dict[str, str]:
    """Return headers for Composio MCP authentication."""
    headers: dict[str, str] = {}
    if CONFIG.composio_api_key:
        headers["x-api-key"] = CONFIG.composio_api_key
    return headers


def is_available() -> bool:
    """Return True if Composio MCP is configured."""
    return bool(MCP_URL)


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Open a one-shot MCP session, call a tool, and return the parsed result."""
    async with streamablehttp_client(MCP_URL, headers=_auth_headers()) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            for block in result.content:
                if hasattr(block, "text"):
                    try:
                        return json.loads(block.text)
                    except json.JSONDecodeError:
                        return block.text
            return None


def _run_async(coro):
    """Run an async coroutine, handling the case where we're already in an event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def call_tool_sync(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Synchronous wrapper around the async MCP call."""
    return _run_async(_call_tool(tool_name, arguments))


async def _list_tools() -> list[dict[str, Any]]:
    """List all available MCP tools."""
    async with streamablehttp_client(MCP_URL, headers=_auth_headers()) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            return [{"name": t.name, "description": t.description} for t in result.tools]


def list_tools_sync() -> list[dict[str, Any]]:
    """Synchronous wrapper to list tools."""
    return _run_async(_list_tools())


# ── Internal: resolve well-known folder IDs ────────────────────────

_FOLDER_ID_CACHE: dict[str, str] = {}


def _resolve_folder_id(display_name: str) -> str | None:
    """Map a display name (e.g. 'Inbox', 'Sent Items') to the Graph folder ID."""
    if display_name in _FOLDER_ID_CACHE:
        return _FOLDER_ID_CACHE[display_name]
    try:
        result = call_tool_sync("OUTLOOK_LIST_MAIL_FOLDERS", {})
        for f in result.get("data", {}).get("value", []):
            _FOLDER_ID_CACHE[f["displayName"]] = f["id"]
    except Exception as exc:
        log.warning("_resolve_folder_id failed: %s", exc)
    return _FOLDER_ID_CACHE.get(display_name)


def _extract_messages(result: Any) -> list[dict[str, Any]]:
    """Pull the message list out of a Composio response."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, dict):
            for key in ("value", "messages", "emails"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        if isinstance(data, list):
            return data
    return []


# ── Convenience helpers for the scanners ──────────────────────────

def fetch_inbox_messages(limit: int = 50, unread_only: bool = True) -> list[dict[str, Any]]:
    """Fetch inbox messages via Composio Outlook MCP."""
    try:
        folder_id = _resolve_folder_id("Inbox")
        if not folder_id:
            log.warning("fetch_inbox_messages: could not resolve Inbox folder ID")
            return []
        result = call_tool_sync(
            "OUTLOOK_LIST_MAIL_FOLDER_MESSAGES",
            {"mail_folder_id": folder_id, "max_results": limit},
        )
        msgs = _extract_messages(result)
        if unread_only:
            msgs = [m for m in msgs if not m.get("isRead", True)]
        return msgs
    except Exception as exc:
        log.warning("fetch_inbox_messages failed: %s", exc)
        return []


def fetch_sent_messages(limit: int = 200) -> list[dict[str, Any]]:
    """Fetch sent folder messages via Composio Outlook MCP."""
    try:
        folder_id = _resolve_folder_id("Sent Items")
        if not folder_id:
            log.warning("fetch_sent_messages: could not resolve Sent Items folder ID")
            return []
        result = call_tool_sync(
            "OUTLOOK_LIST_MAIL_FOLDER_MESSAGES",
            {"mail_folder_id": folder_id, "max_results": limit},
        )
        return _extract_messages(result)
    except Exception as exc:
        log.warning("fetch_sent_messages failed: %s", exc)
        return []


def fetch_calendar_events(start_time: str, end_time: str) -> list[dict[str, Any]]:
    """Fetch calendar events in a time range via Composio Outlook MCP."""
    try:
        result = call_tool_sync(
            "OUTLOOK_LIST_EVENTS",
            {"start_datetime": start_time, "end_datetime": end_time},
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            data = result.get("data", result)
            for key in ("value", "data", "events"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []
    except Exception as exc:
        log.warning("fetch_calendar_events failed: %s", exc)
        return []


def send_email(to: str, subject: str, body: str) -> dict[str, Any] | None:
    """Send an email via Composio Outlook MCP."""
    try:
        return call_tool_sync(
            "OUTLOOK_SEND_EMAIL",
            {
                "to": to,
                "subject": subject,
                "body": body,
                "is_html": False,
                "save_to_sent_items": True,
            },
        )
    except Exception as exc:
        log.warning("send_email failed: %s", exc)
        return None


def seed_message_to_inbox(
    subject: str, body: str, sender_name: str, sender_email: str,
) -> dict[str, Any] | None:
    """Place a fake inbound message into the Outlook inbox.

    The connected Microsoft account uses a Gmail address as its primary
    email, so normal sends to that address land in Gmail — not in the
    Outlook mailbox the MCP reads.  We work around this by:
      1. Creating a draft (with the 'from' fields set to the fake sender),
      2. Moving it from Drafts to Inbox,
      3. Marking it as unread.
    """
    try:
        # 1. Create draft
        draft = call_tool_sync("OUTLOOK_CREATE_DRAFT", {
            "subject": subject,
            "body": body,
            "to_recipients": [sender_email],
        })
        draft_data = draft.get("data", {})
        draft_id = draft_data.get("id")
        if not draft_id:
            log.warning("seed_message_to_inbox: draft creation returned no ID")
            return draft

        # 2. Move to Inbox
        inbox_id = _resolve_folder_id("Inbox")
        if not inbox_id:
            log.warning("seed_message_to_inbox: could not resolve Inbox folder ID")
            return draft
        moved = call_tool_sync("OUTLOOK_MOVE_MESSAGE", {
            "message_id": draft_id,
            "destination_id": inbox_id,
        })
        moved_data = moved.get("data", {})
        new_id = moved_data.get("id", draft_id)

        # 3. Mark as unread
        call_tool_sync("OUTLOOK_UPDATE_EMAIL", {
            "message_id": new_id,
            "is_read": False,
        })

        return {"status": "seeded", "message_id": new_id, "subject": subject}
    except Exception as exc:
        log.warning("seed_message_to_inbox failed: %s", exc)
        return None
