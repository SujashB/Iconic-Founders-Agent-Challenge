"""Critic node — rubric-gated structured output."""
from __future__ import annotations

import json
import logging

from email_agent.nodes._util import llm_json
from email_agent.prompts import CRITIC_SYSTEM, CRITIC_USER_TEMPLATE, VOICE_GUIDE
from email_agent.state import Critique, EmailDraftState

log = logging.getLogger("email_agent.critic")

MAX_RETRIES = 1


def critique(state: EmailDraftState) -> dict:
    draft = state.get("draft")
    strategy = state.get("strategy")
    if draft is None:
        return {"critique": Critique(passed=False, score=0.0, reasons=["no draft"])}

    user_msg = CRITIC_USER_TEMPLATE.format(
        email_type=state["email_type"],
        strategy_json=json.dumps(strategy.model_dump() if strategy else {}, indent=2),
        subject=draft.subject,
        body=draft.body,
        signature=draft.signature,
    )
    try:
        result = llm_json(
            VOICE_GUIDE + "\n\n" + CRITIC_SYSTEM,
            user_msg,
            temperature=0.1,
            max_tokens=600,
        )
        crit = Critique(**result)
    except Exception as exc:  # noqa: BLE001
        log.warning("critic failed, defaulting to pass: %s", exc)
        crit = Critique(passed=True, score=0.75, reasons=[f"critic failed: {exc}"])
    return {"critique": crit}


def critic_decision(state: EmailDraftState) -> str:
    """Conditional edge after critic."""
    crit = state.get("critique")
    if crit is None or crit.passed:
        return "draft_writer"
    if state.get("retry_count", 0) > MAX_RETRIES:
        return "draft_writer"
    return "drafter"
