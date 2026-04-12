"""Sentiment subagent.

A small ReAct-style agent that lives inside the macro email-drafting workflow.
It is the *only* place in the pipeline where the LLM gets tool-calling autonomy
— every other stage (classifier, strategy, drafter, critic) is a single LLM
call with a fixed contract. Sentiment is the exception because it has two
genuinely different tools to choose between:

  1. `analyze_sentiment` — Beam.ai → Medallia Text Analytics. Authoritative
     when available, but a third-party round-trip with timeout/outage risk.
  2. `heuristic_sentiment` — local keyword/regex scorer. Always returns,
     no network, weaker signal.

The subagent is told to prefer Medallia when configured, fall back to the
heuristic on failure, and emit a single SentimentSignals object via
structured output. The macro workflow's sentiment node calls this subagent
and treats its `structured_response` as the new state["sentiment"].

If the subagent itself fails (no API key, all tools error, parsing breaks),
the caller falls back to a neutral SentimentSignals so the rest of the
pipeline never blocks on sentiment.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from langchain.agents import create_agent

from email_agent.config import CONFIG
from email_agent.llm import get_chat_model
from email_agent.state import SentimentSignals
from email_agent.tools.heuristic_sentiment import heuristic_sentiment
from email_agent.tools.medallia_sentiment import analyze_sentiment

log = logging.getLogger("email_agent.sentiment_agent")

SENTIMENT_AGENT_SYSTEM = """You are the Sentiment subagent inside the IFG
email-drafting pipeline. Your one job: produce a SentimentSignals object that
captures the emotional and intent shape of a piece of email or meeting text,
so the downstream Drafter can match tone.

You have two tools:
  - analyze_sentiment(text): Beam.ai → Medallia Text Analytics. Authoritative.
    May fall back to neutral on its own if Medallia is unconfigured or
    unreachable — you can detect this by checking the returned `source` field:
    "medallia" means real scoring, "fallback" means it returned a neutral stub.
  - heuristic_sentiment(text): local keyword/regex scorer. Always returns
    something. Source is always "fallback". Useful when Medallia returned a
    fallback, AND for cross-checking intent_signals (it extracts named
    intents from regex patterns that Medallia's generic Text Analytics
    sometimes misses).

PROCEDURE
1. Always call `analyze_sentiment` first.
2. If its `source` is "medallia", that is your primary signal. Then call
   `heuristic_sentiment` to enrich the `intent_signals` list with any
   IFG-specific labels Medallia missed. Merge by taking the union.
3. If its `source` is "fallback" (Medallia unconfigured or unreachable),
   call `heuristic_sentiment` and use its output as the primary signal.
4. Produce ONE final SentimentSignals object via structured output. Do not
   call any tool more than twice.

RULES
- Do not invent signals that no tool returned.
- Keep `intent_signals` to at most 5 labels.
- `polarity` must be one of: "positive", "neutral", "negative".
- `source` should reflect where the dominant signal came from: "medallia"
  if Medallia returned real scoring, "fallback" otherwise.
"""


@lru_cache(maxsize=1)
def _build_agent():
    """Build the sentiment subagent once and cache it."""
    if not CONFIG.openrouter_api_key:
        return None

    model = get_chat_model(temperature=0.1, max_tokens=600)
    return create_agent(
        model=model,
        tools=[analyze_sentiment, heuristic_sentiment],
        system_prompt=SENTIMENT_AGENT_SYSTEM,
        response_format=SentimentSignals,
        name="sentiment_subagent",
    )


def run_sentiment_subagent(text: str) -> SentimentSignals:
    """Run the sentiment subagent against a piece of text and return a
    SentimentSignals. Falls back to a neutral SentimentSignals on any
    failure so the macro workflow never blocks on sentiment."""
    if not text or not text.strip():
        log.info("sentiment_subagent: empty text, returning neutral")
        return SentimentSignals()

    agent = _build_agent()
    if agent is None:
        log.warning("sentiment_subagent: OPENROUTER_API_KEY not set, returning neutral")
        return SentimentSignals()

    try:
        result = agent.invoke({"messages": [("user", f"Analyze this text:\n\n{text}")]})
    except Exception as exc:  # noqa: BLE001
        log.warning("sentiment_subagent: invocation failed: %s", exc)
        return SentimentSignals()

    structured = result.get("structured_response")
    if isinstance(structured, SentimentSignals):
        return structured
    if isinstance(structured, dict):
        try:
            return SentimentSignals(**structured)
        except Exception as exc:  # noqa: BLE001
            log.warning("sentiment_subagent: structured_response not parseable: %s", exc)

    log.warning("sentiment_subagent: no structured_response, returning neutral")
    return SentimentSignals()


if __name__ == "__main__":
    import json
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else (
        "Hi Sam, hope you're doing well. I came across IFG through a "
        "colleague and wanted to see if there might be a good time for a "
        "quick chat in the coming weeks."
    )
    print(json.dumps(run_sentiment_subagent(sample).model_dump(), indent=2))
