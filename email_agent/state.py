"""Pydantic + TypedDict state schemas for the LangGraph email-drafting pipeline."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

EmailType = Literal["POST_MEETING", "OUTBOUND_FOLLOWUP", "INBOUND_VAGUE"]
Polarity = Literal["positive", "neutral", "negative"]


class TriggerEvent(BaseModel):
    kind: EmailType
    source_ref: str
    raw_payload: dict[str, Any]
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class SentimentSignals(BaseModel):
    polarity: Polarity = "neutral"
    warmth: float = 0.5
    urgency: float = 0.5
    hesitation: float = 0.5
    intent_signals: list[str] = Field(default_factory=list)
    source: Literal["medallia", "fallback"] = "fallback"


class ExtractedContext(BaseModel):
    sender_name: str = ""
    sender_email: str = ""
    sender_org: str = ""
    subject: str = ""
    thread_summary: str = ""
    last_message_excerpt: str = ""
    meeting_title: str = ""
    meeting_attendees: list[str] = Field(default_factory=list)
    meeting_notes: str = ""
    next_steps_mentioned: list[str] = Field(default_factory=list)
    days_since_last_touch: int | None = None


class DraftStrategy(BaseModel):
    tone: str
    structural_template: str
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    target_word_count: int = 120


class DraftOutput(BaseModel):
    subject: str
    body: str
    signature: str = ""

    def render(self) -> str:
        return f"Subject: {self.subject}\n\n{self.body}\n\n{self.signature}".strip()


class Critique(BaseModel):
    passed: bool
    score: float
    reasons: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)


class EmailDraftState(TypedDict, total=False):
    trigger: TriggerEvent
    email_type: EmailType | None
    classifier_verdict: str | None  # "vague" / "drop" / "n/a"
    context: ExtractedContext | None
    sentiment: SentimentSignals | None
    strategy: DraftStrategy | None
    draft: DraftOutput | None
    critique: Critique | None
    retry_count: int
    final_draft: DraftOutput | None
    outlook_draft_id: str | None
    error: str | None
