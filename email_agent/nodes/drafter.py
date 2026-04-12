"""Drafter node — produces subject + body + signature."""
from __future__ import annotations

import json
import logging

from email_agent.nodes._util import llm_json
from email_agent.prompts import (
    DRAFTER_RETRY_BLOCK,
    DRAFTER_SYSTEM,
    DRAFTER_USER_TEMPLATE,
    VOICE_GUIDE,
)
from email_agent.state import DraftOutput, EmailDraftState

log = logging.getLogger("email_agent.drafter")


def _first_name(full: str) -> str:
    return full.split()[0] if full else "there"


def _context_block(state: EmailDraftState) -> str:
    ctx = state.get("context")
    if ctx is None:
        return ""
    lines = []
    if ctx.subject:
        lines.append(f"Subject of original: {ctx.subject}")
    if ctx.meeting_title:
        lines.append(f"Meeting title: {ctx.meeting_title}")
    if ctx.meeting_attendees:
        lines.append("Attendees: " + ", ".join(ctx.meeting_attendees))
    if ctx.meeting_notes:
        lines.append(f"Meeting notes:\n{ctx.meeting_notes}")
    if ctx.next_steps_mentioned:
        lines.append("Next steps mentioned in meeting:\n- " + "\n- ".join(ctx.next_steps_mentioned))
    if ctx.thread_summary:
        lines.append(f"Thread summary: {ctx.thread_summary}")
    if ctx.last_message_excerpt:
        lines.append(f"Most relevant message:\n{ctx.last_message_excerpt}")
    if ctx.days_since_last_touch is not None:
        lines.append(f"Days since last touch: {ctx.days_since_last_touch}")
    return "\n\n".join(lines)


def _sentiment_block(state: EmailDraftState) -> str:
    sentiment = state.get("sentiment")
    if sentiment is None:
        return "neutral (no signal)"
    return (
        f"polarity={sentiment.polarity}, warmth={sentiment.warmth:.2f}, "
        f"urgency={sentiment.urgency:.2f}, hesitation={sentiment.hesitation:.2f}\n"
        f"intent signals: {', '.join(sentiment.intent_signals) or 'none'}\n"
        f"source: {sentiment.source}"
    )


def draft(state: EmailDraftState) -> dict:
    ctx = state.get("context")
    strategy = state.get("strategy")
    full_name = ctx.sender_name if ctx else ""
    org = ctx.sender_org if ctx else ""
    first = _first_name(full_name)

    retry_count = state.get("retry_count", 0)
    critique = state.get("critique")
    previous_draft = state.get("draft")
    if retry_count > 0 and critique and previous_draft:
        retry_block = DRAFTER_RETRY_BLOCK.format(
            critique_reasons="\n- " + "\n- ".join(critique.reasons),
            critique_fixes="\n- " + "\n- ".join(critique.suggested_fixes),
            previous_body=previous_draft.body,
        )
    else:
        retry_block = ""

    user_msg = DRAFTER_USER_TEMPLATE.format(
        strategy_json=json.dumps(strategy.model_dump() if strategy else {}, indent=2),
        first_name=first,
        full_name=full_name,
        org=org,
        context_block=_context_block(state),
        sentiment_block=_sentiment_block(state),
        retry_block=retry_block,
    )

    try:
        result = llm_json(
            VOICE_GUIDE + "\n\n" + DRAFTER_SYSTEM,
            user_msg,
            temperature=0.55,
            max_tokens=900,
        )
        draft_obj = DraftOutput(
            subject=result.get("subject", ""),
            body=result.get("body", ""),
            signature=result.get("signature", "Best,\nSam"),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("drafter failed: %s", exc)
        draft_obj = DraftOutput(
            subject="(drafting failed)",
            body=f"Drafting failed: {exc}",
            signature="",
        )
    return {"draft": draft_obj, "retry_count": retry_count + 1}
