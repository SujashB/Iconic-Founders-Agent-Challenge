"""Strategy node — picks tone and structural template from email_type × sentiment."""
from __future__ import annotations

import logging

from email_agent.nodes._util import llm_json
from email_agent.prompts import STRATEGY_SYSTEM, STRATEGY_USER_TEMPLATE, VOICE_GUIDE
from email_agent.state import DraftStrategy, EmailDraftState

log = logging.getLogger("email_agent.strategy")

_FALLBACK_BY_TYPE = {
    "POST_MEETING": DraftStrategy(
        tone="warm_specific",
        structural_template="thanks → 2 concrete callbacks → next-step proposal",
        must_include=["specific reference to the conversation", "concrete next-step window"],
        must_avoid=["generic gratitude", "exclamation marks"],
        target_word_count=120,
    ),
    "OUTBOUND_FOLLOWUP": DraftStrategy(
        tone="soft_nudge",
        structural_template="brief callback to prior outreach → low-pressure ask → easy out",
        must_include=["reference to prior outreach", "easy out"],
        must_avoid=["pressure language", "apology", "circle back / touch base"],
        target_word_count=80,
    ),
    "INBOUND_VAGUE": DraftStrategy(
        tone="warm_inquisitive",
        structural_template="warm acknowledgement → 1-2 qualifying questions → light close",
        must_include=["1-2 qualifying questions"],
        must_avoid=["proposing a meeting time yet", "generic enthusiasm"],
        target_word_count=110,
    ),
}


def _summarize_context(state: EmailDraftState) -> str:
    ctx = state.get("context")
    if ctx is None:
        return ""
    parts = []
    if ctx.sender_name:
        parts.append(f"Sender: {ctx.sender_name}" + (f" ({ctx.sender_org})" if ctx.sender_org else ""))
    if ctx.subject:
        parts.append(f"Subject: {ctx.subject}")
    if ctx.meeting_title:
        parts.append(f"Meeting: {ctx.meeting_title}")
    if ctx.next_steps_mentioned:
        parts.append("Next steps from meeting: " + "; ".join(ctx.next_steps_mentioned))
    if ctx.last_message_excerpt:
        parts.append(f"Last message: {ctx.last_message_excerpt[:400]}")
    if ctx.thread_summary:
        parts.append(f"Thread: {ctx.thread_summary}")
    if ctx.days_since_last_touch is not None:
        parts.append(f"Days since last touch: {ctx.days_since_last_touch}")
    return "\n".join(parts)


def select_strategy(state: EmailDraftState) -> dict:
    email_type = state["email_type"]
    sentiment = state.get("sentiment")
    user_msg = STRATEGY_USER_TEMPLATE.format(
        email_type=email_type,
        polarity=sentiment.polarity if sentiment else "neutral",
        warmth=f"{sentiment.warmth:.2f}" if sentiment else "0.50",
        urgency=f"{sentiment.urgency:.2f}" if sentiment else "0.50",
        hesitation=f"{sentiment.hesitation:.2f}" if sentiment else "0.50",
        intent_signals=", ".join(sentiment.intent_signals) if sentiment else "",
        context_summary=_summarize_context(state),
    )
    try:
        result = llm_json(
            VOICE_GUIDE + "\n\n" + STRATEGY_SYSTEM,
            user_msg,
            temperature=0.2,
            max_tokens=500,
        )
        strategy = DraftStrategy(**result)
    except Exception as exc:  # noqa: BLE001
        log.warning("strategy LLM failed, using fallback for %s: %s", email_type, exc)
        strategy = _FALLBACK_BY_TYPE[email_type]
    return {"strategy": strategy}
