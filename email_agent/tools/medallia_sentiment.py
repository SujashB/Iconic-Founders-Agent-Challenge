"""Sentiment analysis tool — Beam.ai → Medallia Text Analytics.

The LangGraph node interface is `analyze_sentiment(text: str) -> SentimentSignals`.
The implementation is documented in System Design/implementation_plan.md step 6:

  1. Authenticate against Beam.ai using BEAM_API_KEY.
  2. Create a feedback entry in MEDALLIA_PROGRAM_ID via the Beam.ai integration,
     tagged with a UUID.
  3. Poll the Medallia analytics endpoint until the Text Analytics Engine
     attaches scores (every SENTIMENT_POLL_INTERVAL_S, up to SENTIMENT_TIMEOUT_S).
  4. Map Medallia analytics fields onto our SentimentSignals schema.
  5. On any error or timeout, fall back to neutral signals so the pipeline
     never blocks on a third-party outage.
  6. Optionally delete the temporary feedback entry.

The Beam.ai Medallia integration page (https://beam.ai/integrations/medallia/)
does not publish a Python SDK or REST contract; the actual HTTP calls are
isolated in `_call_beam_create_entry` / `_poll_medallia_score` so they can be
swapped for the real client signatures once Beam.ai exposes them.
"""
from __future__ import annotations

import logging
import time
import uuid

import httpx
from langchain_core.tools import tool

from email_agent.config import CONFIG
from email_agent.state import SentimentSignals

log = logging.getLogger("email_agent.sentiment")

BEAM_API_BASE = "https://api.beam.ai/v1"
MEDALLIA_INTEGRATION_PATH = "/integrations/medallia"


def _neutral() -> SentimentSignals:
    return SentimentSignals(
        polarity="neutral",
        warmth=0.5,
        urgency=0.5,
        hesitation=0.5,
        intent_signals=[],
        source="fallback",
    )


def _call_beam_create_entry(text: str, correlation_id: str) -> str | None:
    """POST the email text to Beam.ai → Medallia as a feedback entry.
    Returns the Medallia entry id, or None on any failure."""
    if not CONFIG.has_beam_creds:
        return None
    try:
        url = f"{BEAM_API_BASE}{MEDALLIA_INTEGRATION_PATH}/feedback"
        headers = {
            "Authorization": f"Bearer {CONFIG.beam_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "program_id": CONFIG.medallia_program_id,
            "tenant": CONFIG.medallia_tenant,
            "correlation_id": correlation_id,
            "text": text,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("entry_id") or data.get("id")
    except Exception as exc:  # noqa: BLE001
        log.warning("beam.create_entry failed: %s", exc)
        return None


def _poll_medallia_score(entry_id: str) -> dict | None:
    """Poll Medallia Text Analytics until the entry is scored or we time out."""
    deadline = time.monotonic() + CONFIG.sentiment_timeout_s
    url = f"{BEAM_API_BASE}{MEDALLIA_INTEGRATION_PATH}/feedback/{entry_id}"
    headers = {
        "Authorization": f"Bearer {CONFIG.beam_api_key}",
        "X-Medallia-Token": CONFIG.medallia_auth_token,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            while time.monotonic() < deadline:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("analytics", {}).get("status") == "scored":
                        return data["analytics"]
                time.sleep(CONFIG.sentiment_poll_interval_s)
    except Exception as exc:  # noqa: BLE001
        log.warning("medallia.poll failed: %s", exc)
    return None


def _delete_entry(entry_id: str) -> None:
    if not CONFIG.medallia_delete_after_score:
        return
    try:
        url = f"{BEAM_API_BASE}{MEDALLIA_INTEGRATION_PATH}/feedback/{entry_id}"
        headers = {"Authorization": f"Bearer {CONFIG.beam_api_key}"}
        with httpx.Client(timeout=5.0) as client:
            client.delete(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        log.debug("medallia.delete failed (non-fatal): %s", exc)


def _map_medallia_to_signals(analytics: dict) -> SentimentSignals:
    """Map Medallia Text Analytics fields onto our SentimentSignals schema."""
    polarity_raw = (analytics.get("sentiment", {}).get("polarity") or "neutral").lower()
    if polarity_raw not in ("positive", "neutral", "negative"):
        polarity_raw = "neutral"

    emotion_intensity = float(analytics.get("emotion", {}).get("intensity", 0.5))
    warmth = max(0.0, min(1.0, emotion_intensity))

    topics = analytics.get("topics", []) or []
    urgency_score = next(
        (t.get("score", 0.5) for t in topics if "urgen" in (t.get("label") or "").lower()),
        0.5,
    )
    hesitation_score = next(
        (
            t.get("score", 0.5)
            for t in topics
            if any(k in (t.get("label") or "").lower() for k in ("hesit", "uncertain"))
        ),
        0.5,
    )
    top_topics = [t.get("label", "") for t in topics[:5] if t.get("label")]

    return SentimentSignals(
        polarity=polarity_raw,
        warmth=warmth,
        urgency=float(urgency_score),
        hesitation=float(hesitation_score),
        intent_signals=top_topics,
        source="medallia",
    )


def analyze_sentiment_impl(text: str) -> SentimentSignals:
    """Pure-Python entry point so other modules can call this without LangChain."""
    if not text or not text.strip():
        return _neutral()
    if not CONFIG.has_beam_creds:
        log.info("sentiment.fallback: Beam.ai/Medallia credentials not configured")
        return _neutral()

    correlation_id = str(uuid.uuid4())
    entry_id = _call_beam_create_entry(text, correlation_id)
    if not entry_id:
        log.warning("sentiment.fallback: could not create Medallia feedback entry")
        return _neutral()

    analytics = _poll_medallia_score(entry_id)
    _delete_entry(entry_id)

    if not analytics:
        log.warning("sentiment.fallback: Medallia scoring exceeded timeout")
        return _neutral()

    try:
        return _map_medallia_to_signals(analytics)
    except Exception as exc:  # noqa: BLE001
        log.warning("sentiment.fallback: mapping failed: %s", exc)
        return _neutral()


@tool("analyze_sentiment")
def analyze_sentiment(text: str) -> dict:
    """Run sentiment analysis on a piece of text via Beam.ai → Medallia Text
    Analytics. Returns SentimentSignals as a dict. Falls back to neutral
    signals if Beam.ai/Medallia is unreachable, unconfigured, or times out."""
    return analyze_sentiment_impl(text).model_dump()


if __name__ == "__main__":
    import json
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else "Thanks for the great chat earlier."
    result = analyze_sentiment_impl(sample)
    print(json.dumps(result.model_dump(), indent=2))
