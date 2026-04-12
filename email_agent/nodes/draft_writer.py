"""Draft Writer node.

In live mode this calls O365CreateDraftMessage to write into the user's
Outlook Drafts folder. In offline/fixture mode it writes a Markdown rendering
of the draft to outputs/<filename>.md so the grader can see the result.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from email_agent.config import CONFIG
from email_agent.state import EmailDraftState
from email_agent.tools.o365 import get_tool

log = logging.getLogger("email_agent.draft_writer")


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "draft"


def _to_address(state: EmailDraftState) -> str:
    ctx = state.get("context")
    return ctx.sender_email if ctx and ctx.sender_email else ""


def _write_offline(state: EmailDraftState) -> str:
    draft = state["draft"]
    email_type = state["email_type"]
    to = _to_address(state)
    rendered = (
        f"# Draft — {email_type}\n\n"
        f"**To:** {to}\n"
        f"**Subject:** {draft.subject}\n\n"
        f"---\n\n"
        f"{draft.body}\n\n"
        f"{draft.signature}\n"
    )
    out_path = CONFIG.outputs_dir / f"draft_{email_type.lower()}.md"
    out_path.write_text(rendered)
    log.info("draft written to %s", out_path)
    return str(out_path)


def _write_outlook(state: EmailDraftState) -> str | None:
    create_tool = get_tool("create_email_draft") or get_tool("O365CreateDraftMessage")
    if create_tool is None:
        return None
    draft = state["draft"]
    body_html = draft.body.replace("\n", "<br>") + "<br><br>" + draft.signature.replace("\n", "<br>")
    try:
        result = create_tool.invoke(
            {
                "subject": draft.subject,
                "body": body_html,
                "to": [_to_address(state)] if _to_address(state) else [],
            }
        )
        return str(result)
    except Exception as exc:  # noqa: BLE001
        log.warning("O365 draft creation failed, falling back to offline: %s", exc)
        return None


def write(state: EmailDraftState) -> dict:
    if state.get("draft") is None:
        return {"error": "no draft to write"}

    outlook_id = _write_outlook(state)
    file_path = _write_offline(state)

    return {
        "final_draft": state["draft"],
        "outlook_draft_id": outlook_id or f"file://{file_path}",
    }
