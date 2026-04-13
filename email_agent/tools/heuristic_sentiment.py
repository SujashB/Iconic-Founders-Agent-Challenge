"""Local, no-network, no-LLM sentiment heuristic.

Used as the second tool exposed to the sentiment subagent so it can fall back
when Medallia is unreachable. Deliberately simple — keyword and punctuation
counts mapped onto the SentimentSignals schema. Not a substitute for Medallia
when Medallia is available; it exists so the subagent always has *something*
to return without blocking on a third-party outage.
"""
from __future__ import annotations

import re

from langchain_core.tools import tool

from email_agent.state import SentimentSignals

POSITIVE_TERMS = {
    "thanks", "thank you", "appreciate", "great", "glad", "happy", "excited",
    "looking forward", "pleasure", "wonderful", "perfect", "love", "helpful",
    "useful", "good fit", "benefit", "enjoyed", "productive", "appreciated",
}
NEGATIVE_TERMS = {
    "concern", "worried", "issue", "problem", "frustrated", "disappointed",
    "unhappy", "delay", "stuck", "blocker", "unfortunately", "regret",
    "risk", "not ready", "concentration", "dependency", "gap", "no reply",
    "haven't heard", "hasn't replied", "silent",
}
URGENCY_TERMS = {
    "asap", "urgent", "today", "right away", "tomorrow", "deadline", "by eod",
    "by end of", "soon", "quickly", "time-sensitive", "this week", "next week",
    "within 1 week", "within a week", "near term", "coming weeks",
}
HESITATION_TERMS = {
    "maybe", "perhaps", "not sure", "might", "thinking about", "considering",
    "exploring", "wondering", "could be", "i guess", "if it works",
    "no rush", "whenever", "potential", "starting to think", "not yet",
    "not ready", "risk", "concentration", "dependency", "anchored",
}
INTENT_PATTERNS = [
    (r"\bquick (chat|call|connect)\b", "introductory_chat"),
    (r"\bconnect\b", "introductory_chat"),
    (r"\bswap notes\b", "peer_exchange"),
    (r"\b(exit|sale|sell|sale-side|transaction)\b", "exit_intent"),
    (r"\bvaluation|multiple(s)?|ebitda|8x\b", "valuation_question"),
    (r"\bbuyer(s)?\b", "buyer_interest"),
    (r"\bclient(s)?|founder(s)?|portfolio company\b", "client_referral"),
    (r"\bcoverage\b", "coverage_gap"),
    (r"\bfollow.?up\b", "followup"),
    (r"\bnext steps?\b", "next_steps"),
    (r"\bmarket read\b", "market_read_request"),
    (r"\b(concentration|coo|not ready|risk|dependency)\b", "concern_or_risk"),
    (r"\breconvene|walk through|timeline\b", "next_steps"),
]


def _count_hits(text_lc: str, terms: set[str]) -> int:
    return sum(1 for t in terms if t in text_lc)


def _score(hits: int, *, scale: int = 3) -> float:
    """Map a small integer hit-count onto [0, 1] with diminishing returns."""
    if hits <= 0:
        return 0.0
    return min(1.0, hits / scale)


def heuristic_sentiment_impl(text: str) -> SentimentSignals:
    if not text or not text.strip():
        return SentimentSignals(source="fallback")

    text_lc = text.lower()

    pos_hits = _count_hits(text_lc, POSITIVE_TERMS)
    neg_hits = _count_hits(text_lc, NEGATIVE_TERMS)
    urg_hits = _count_hits(text_lc, URGENCY_TERMS)
    hes_hits = _count_hits(text_lc, HESITATION_TERMS)

    # Polarity: negatives win ties to err on caution.
    if neg_hits > pos_hits:
        polarity = "negative"
    elif pos_hits > neg_hits:
        polarity = "positive"
    else:
        polarity = "neutral"

    # Warmth: positives raise it, negatives lower it; baseline 0.5.
    warmth = max(0.0, min(1.0, 0.5 + 0.15 * (pos_hits - neg_hits)))

    urgency = max(0.5, _score(urg_hits, scale=2)) if urg_hits else 0.3
    hesitation = max(0.5, _score(hes_hits, scale=2)) if hes_hits else 0.3

    intent_signals: list[str] = []
    for pattern, label in INTENT_PATTERNS:
        if re.search(pattern, text_lc):
            intent_signals.append(label)

    return SentimentSignals(
        polarity=polarity,
        warmth=round(warmth, 2),
        urgency=round(urgency, 2),
        hesitation=round(hesitation, 2),
        intent_signals=intent_signals,
        source="fallback",
    )


@tool("heuristic_sentiment")
def heuristic_sentiment(text: str) -> dict:
    """Score a piece of text for sentiment using a local keyword/regex
    heuristic. No network, no LLM, always returns. Use this as a fallback
    when the Medallia tool is unavailable, or as a secondary signal to
    cross-check intent_signals against Medallia output.

    Returns a SentimentSignals dict with polarity (positive/neutral/negative),
    warmth/urgency/hesitation in [0,1], a list of intent_signals labels, and
    source="fallback"."""
    return heuristic_sentiment_impl(text).model_dump()


if __name__ == "__main__":
    import json
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else "Hi Sam, just a quick chat?"
    print(json.dumps(heuristic_sentiment_impl(sample).model_dump(), indent=2))
