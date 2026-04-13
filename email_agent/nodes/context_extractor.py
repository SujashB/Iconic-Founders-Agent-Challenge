"""Context Extractor node.

In live mode this would call the O365 search tools to pull thread history,
meeting body, and prior messages. In fixture mode it pulls the same fields
from the trigger's raw_payload, which is shaped to mirror what the live tools
would return.
"""
from __future__ import annotations

from email_agent.state import EmailDraftState, ExtractedContext


def extract_context(state: EmailDraftState) -> dict:
    payload = state["trigger"].raw_payload
    email_type = state["email_type"]

    if email_type == "POST_MEETING":
        ctx = ExtractedContext(
            sender_name=payload.get("organizer_name", ""),
            sender_email=payload.get("organizer_email", ""),
            sender_org="",
            subject=payload.get("subject", ""),
            meeting_title=payload.get("subject", ""),
            meeting_attendees=payload.get("attendees", []),
            meeting_notes=payload.get("body", ""),
            next_steps_mentioned=payload.get("next_steps", []),
        )
    elif email_type == "OUTBOUND_FOLLOWUP":
        ctx = ExtractedContext(
            sender_name=payload.get("recipient_name", ""),
            sender_email=payload.get("recipient_email", ""),
            sender_org=payload.get("recipient_org", ""),
            subject=payload.get("subject", ""),
            thread_summary=payload.get("thread_summary", ""),
            last_message_excerpt=payload.get("last_outbound_excerpt", ""),
            days_since_last_touch=payload.get("days_since_last_touch"),
        )
    else:  # INBOUND_VAGUE
        ctx = ExtractedContext(
            sender_name=payload.get("sender_name", ""),
            sender_email=payload.get("sender_email", payload.get("sender", "")),
            sender_org=payload.get("sender_org", ""),
            subject=payload.get("subject", ""),
            last_message_excerpt=payload.get("body", ""),
            thread_summary=payload.get("thread_summary", ""),
        )

    return {"context": ctx}
