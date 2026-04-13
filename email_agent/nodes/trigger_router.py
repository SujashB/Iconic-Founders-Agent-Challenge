"""Trigger Router — normalizes a TriggerEvent into the EmailDraftState contract."""
from __future__ import annotations

from email_agent.state import EmailDraftState, TriggerEvent


def trigger_router(state: EmailDraftState) -> dict:
    trigger: TriggerEvent = state["trigger"]
    return {
        "email_type": trigger.kind,
        "retry_count": 0,
        "classifier_verdict": None,
    }


def needs_classifier(state: EmailDraftState) -> str:
    """Conditional edge: only inbound emails go through the classifier."""
    return "classifier" if state.get("email_type") == "INBOUND_VAGUE" else "context_extractor"
