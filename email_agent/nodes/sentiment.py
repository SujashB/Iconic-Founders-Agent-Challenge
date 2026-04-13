"""Sentiment node — delegates to the sentiment subagent.

The node is a thin shim: it picks the right text out of state.context for the
email type, hands it to the sentiment subagent, and writes the returned
SentimentSignals back into state. The subagent is the place that decides
which tool(s) to call (Medallia vs heuristic) and how to merge their output.
See email_agent/agents/sentiment_agent.py.
"""
from __future__ import annotations

from email_agent.agents.sentiment_agent import run_sentiment_subagent
from email_agent.state import EmailDraftState, SentimentSignals


def _pick_text(state: EmailDraftState) -> str:
    ctx = state.get("context")
    if ctx is None:
        return ""
    email_type = state["email_type"]
    if email_type == "POST_MEETING":
        return f"{ctx.meeting_title}\n\n{ctx.meeting_notes}".strip()
    if email_type == "OUTBOUND_FOLLOWUP":
        return ctx.last_message_excerpt or ctx.thread_summary or ""
    # INBOUND_VAGUE
    return ctx.last_message_excerpt or ""


def analyze(state: EmailDraftState) -> dict:
    text = _pick_text(state)
    signals = run_sentiment_subagent(text)
    if not isinstance(signals, SentimentSignals):
        signals = SentimentSignals()
    return {"sentiment": signals}
