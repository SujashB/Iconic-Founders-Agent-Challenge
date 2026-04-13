"""Classifier node — only invoked on the inbound path. Confirms the email is
actually a vague RA connection request, or drops it."""
from __future__ import annotations

import logging

from email_agent.nodes._util import llm_json
from email_agent.prompts import CLASSIFIER_SYSTEM, CLASSIFIER_USER_TEMPLATE
from email_agent.state import EmailDraftState

log = logging.getLogger("email_agent.classifier")


def classify(state: EmailDraftState) -> dict:
    payload = state["trigger"].raw_payload
    user_msg = CLASSIFIER_USER_TEMPLATE.format(
        sender=payload.get("sender", "unknown"),
        subject=payload.get("subject", ""),
        body=payload.get("body", ""),
    )
    try:
        result = llm_json(CLASSIFIER_SYSTEM, user_msg, temperature=0.1, max_tokens=300)
        verdict = result.get("verdict", "drop")
    except Exception as exc:  # noqa: BLE001
        log.warning("classifier failed, defaulting to 'vague': %s", exc)
        verdict = "vague"
    return {"classifier_verdict": verdict}


def classifier_decision(state: EmailDraftState) -> str:
    """Conditional edge after classifier."""
    if state.get("classifier_verdict") == "vague":
        return "context_extractor"
    return "drop"
