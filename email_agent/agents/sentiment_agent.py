"""Sentiment subagent.

The sentiment station uses DeepSeek via local Ollama as a focused scorer, then
merges that judgment with deterministic local heuristics and Medallia when it is
configured. This avoids the prior failure mode where a small local chat model
missed structured tool output and collapsed sentiment back to neutral.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from email_agent.config import CONFIG
from email_agent.llm import get_sentiment_chat_model
from email_agent.nodes._util import extract_json
from email_agent.state import SentimentSignals
from email_agent.tools.heuristic_sentiment import heuristic_sentiment_impl
from email_agent.tools.medallia_sentiment import analyze_sentiment_impl

log = logging.getLogger("email_agent.sentiment_agent")

ALLOWED_INTENT_SIGNALS = {
    "introductory_chat",
    "peer_exchange",
    "client_referral",
    "exit_intent",
    "valuation_question",
    "buyer_interest",
    "market_read_request",
    "next_steps",
    "followup",
    "coverage_gap",
    "concern_or_risk",
}

SENTIMENT_AGENT_SYSTEM = """You are a sentiment analyst for IFG's M&A email
drafting workflow. Score the text for how the reply should sound.

Return JSON only in this exact shape:
{
  "polarity": "positive" | "neutral" | "negative",
  "warmth": 0.0-1.0,
  "urgency": 0.0-1.0,
  "hesitation": 0.0-1.0,
  "intent_signals": ["up to five short snake_case labels"]
}

Definitions:
- warmth: friendliness, openness, gratitude, collaborative tone.
- urgency: time pressure, near-term asks, this-week language, deadline pressure.
- hesitation: uncertainty, exploration, risk, reluctance, tentative sale timing.
- intent_signals: use M&A-specific labels such as introductory_chat,
  client_referral, exit_intent, valuation_question, buyer_interest,
  market_read_request, next_steps, followup, concern_or_risk.

Be conservative. Do not mark positive just because the email is polite. Treat
valuation risk, customer concentration, leadership dependency, no-reply threads,
and "exploring" language as meaningful hesitation even when the tone is warm.
"""


def _clamp(raw: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return default


def _merge_intents(*items: list[str]) -> list[str]:
    seen: list[str] = []
    for labels in items:
        for label in labels:
            normalized = str(label).strip().lower().replace(" ", "_")
            if normalized in ALLOWED_INTENT_SIGNALS and normalized not in seen:
                seen.append(normalized)
    return seen[:5]


def _merge_polarity(base: str, refined: str, text: str, hesitation: float) -> str:
    if refined not in ("positive", "neutral", "negative"):
        return base
    text_lc = text.lower()
    caution_terms = ("risk", "concentration", "not ready", "dependency", "no reply", "haven't heard")
    if refined == "positive" and (base == "negative" or hesitation >= 0.65 or any(t in text_lc for t in caution_terms)):
        return "neutral" if base == "neutral" else base
    return refined


def _dominant_base_signal(text: str) -> SentimentSignals:
    medallia = analyze_sentiment_impl(text)
    heuristic = heuristic_sentiment_impl(text)
    if medallia.source == "medallia":
        return SentimentSignals(
            polarity=medallia.polarity,
            warmth=medallia.warmth,
            urgency=max(medallia.urgency, heuristic.urgency),
            hesitation=max(medallia.hesitation, heuristic.hesitation),
            intent_signals=_merge_intents(medallia.intent_signals, heuristic.intent_signals),
            source="medallia",
        )
    return heuristic


def _deepseek_signal(text: str, base: SentimentSignals) -> SentimentSignals | None:
    model = get_sentiment_chat_model(temperature=0.0, max_tokens=700)
    user = (
        f"Baseline local signal:\n{json.dumps(base.model_dump(), indent=2)}\n\n"
        f"Text to score:\n{text}"
    )
    response = model.invoke(
        [SystemMessage(content=SENTIMENT_AGENT_SYSTEM), HumanMessage(content=user)]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    data = extract_json(content)
    urgency = max(base.urgency, _clamp(data.get("urgency"), base.urgency))
    hesitation = max(base.hesitation, _clamp(data.get("hesitation"), base.hesitation))
    polarity = _merge_polarity(base.polarity, data.get("polarity", base.polarity), text, hesitation)
    warmth = _clamp(data.get("warmth"), base.warmth)
    if polarity == "negative":
        warmth = min(warmth, 0.45)
    elif hesitation >= 0.65 and "concern_or_risk" in base.intent_signals:
        warmth = min(warmth, 0.6)
    return SentimentSignals(
        polarity=polarity,
        warmth=warmth,
        urgency=urgency,
        hesitation=hesitation,
        intent_signals=_merge_intents(base.intent_signals, data.get("intent_signals", [])),
        source=base.source,
    )


def run_sentiment_subagent(text: str) -> SentimentSignals:
    """Run the sentiment subagent against a piece of text and return a
    SentimentSignals. Falls back to a neutral SentimentSignals on any
    failure so the macro workflow never blocks on sentiment."""
    if not text or not text.strip():
        log.info("sentiment_subagent: empty text, returning neutral")
        return SentimentSignals()

    base = _dominant_base_signal(text)

    try:
        refined = _deepseek_signal(text, base)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "sentiment_subagent: DeepSeek refinement failed for %s, using baseline: %s",
            CONFIG.sentiment_ollama_model,
            exc,
        )
        return base

    return refined or base


if __name__ == "__main__":
    import json
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else (
        "Hi Sam, hope you're doing well. I came across IFG through a "
        "colleague and wanted to see if there might be a good time for a "
        "quick chat in the coming weeks."
    )
    print(json.dumps(run_sentiment_subagent(sample).model_dump(), indent=2))
