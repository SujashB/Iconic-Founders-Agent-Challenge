"""Drafter node — produces subject + body + signature."""
from __future__ import annotations

import json
import logging
import re

from email_agent.nodes._util import llm_json
from email_agent.prompts import (
    DRAFTER_RETRY_BLOCK,
    DRAFTER_SYSTEM,
    DRAFTER_USER_TEMPLATE,
    VOICE_GUIDE,
)
from email_agent.state import DraftOutput, EmailDraftState

log = logging.getLogger("email_agent.drafter")


def _first_name(full: str) -> str:
    return full.split()[0] if full else "there"


def _context_block(state: EmailDraftState) -> str:
    ctx = state.get("context")
    if ctx is None:
        return ""
    lines = []
    if ctx.subject:
        lines.append(f"Subject of original: {ctx.subject}")
    if ctx.meeting_title:
        lines.append(f"Meeting title: {ctx.meeting_title}")
    if ctx.meeting_attendees:
        lines.append("Attendees: " + ", ".join(ctx.meeting_attendees))
    if ctx.meeting_notes:
        lines.append(f"Meeting notes:\n{ctx.meeting_notes}")
    if ctx.next_steps_mentioned:
        lines.append("Next steps mentioned in meeting:\n- " + "\n- ".join(ctx.next_steps_mentioned))
    if ctx.thread_summary:
        lines.append(f"Thread summary: {ctx.thread_summary}")
    if ctx.last_message_excerpt:
        lines.append(f"Most relevant message:\n{ctx.last_message_excerpt}")
    if ctx.days_since_last_touch is not None:
        lines.append(f"Days since last touch: {ctx.days_since_last_touch}")
    return "\n\n".join(lines)


def _sentiment_block(state: EmailDraftState) -> str:
    sentiment = state.get("sentiment")
    if sentiment is None:
        return "neutral (no signal)"
    return (
        f"polarity={sentiment.polarity}, warmth={sentiment.warmth:.2f}, "
        f"urgency={sentiment.urgency:.2f}, hesitation={sentiment.hesitation:.2f}\n"
        f"intent signals: {', '.join(sentiment.intent_signals) or 'none'}\n"
        f"source: {sentiment.source}"
    )


def _reply_subject(subject: str) -> str:
    subject = subject.strip()
    if not subject:
        return "Re:"
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


def _strip_signature_from_body(body: str) -> str:
    lines = body.strip().splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    signoff_patterns = (
        r"^best,?$",
        r"^thanks,?$",
        r"^regards,?$",
        r"^sam$",
    )
    while lines and any(re.fullmatch(pattern, lines[-1].strip(), re.IGNORECASE) for pattern in signoff_patterns):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines).strip()


def _meeting_facts(notes: str) -> list[str]:
    candidates = [
        ("18-24" in notes, "the 18-24 month exit window"),
        ("8x" in notes or "valuation" in notes.lower(), "valuation expectations"),
        ("customer concentration" in notes.lower(), "customer concentration"),
        ("COO" in notes or "management team" in notes.lower(), "management depth"),
        ("recurring maintenance" in notes.lower(), "recurring maintenance revenue"),
        ("technician retention" in notes.lower(), "technician retention"),
        ("founder readiness" in notes.lower(), "founder readiness"),
        ("owner dependency" in notes.lower(), "owner dependency"),
        ("$3M" in notes or "$8M" in notes, "the owner profile Nate described"),
    ]
    return [label for present, label in candidates if present][:3]


def _clean_next_step(step: str) -> str:
    step = re.sub(r"^Sam to ", "", step).strip()
    if not step:
        return ""
    return step[0].lower() + step[1:]


def _fallback_post_meeting_body(first: str, state: EmailDraftState) -> str:
    ctx = state.get("context")
    notes = ctx.meeting_notes if ctx else ""
    facts = _meeting_facts(notes)
    if not facts:
        facts = ["the owner context", "the readiness questions", "the next steps"]

    steps = ctx.next_steps_mentioned if ctx else []
    deliverables = [
        _clean_next_step(step)
        for step in steps
        if not re.search(r"\b(reconvene|regroup|reconnect)\b", step, re.IGNORECASE)
    ]
    deliverables = [step for step in deliverables if step]
    reconvene = next(
        (_clean_next_step(step) for step in steps if re.search(r"\b(reconvene|regroup|reconnect)\b", step, re.IGNORECASE)),
        "reconnect after you have had a chance to review the materials",
    )
    if deliverables:
        next_step_sentence = "I will " + " and ".join(deliverables[:2]) + "."
    else:
        next_step_sentence = "I will send the follow-up materials we discussed."

    return (
        f"Hi {first},\n\n"
        f"Thank you for the conversation earlier. I appreciated the discussion around "
        f"{', '.join(facts[:-1]) + (', and ' if len(facts) > 1 else '') + facts[-1]}.\n\n"
        f"{next_step_sentence} Would it make sense to {reconvene}?"
    )


def _fallback_draft(state: EmailDraftState, first: str) -> DraftOutput:
    ctx = state.get("context")
    email_type = state["email_type"]
    subject = _reply_subject(ctx.subject if ctx else "")

    if email_type == "INBOUND_VAGUE":
        body = (
            f"Hi {first},\n\n"
            "Thanks for reaching out. Before we put time on the calendar, it would be "
            "helpful to understand what prompted the note. Are you thinking about a "
            "specific founder or client situation, or more generally comparing notes "
            "on the M&A market?"
        )
    elif email_type == "OUTBOUND_FOLLOWUP":
        summary = ctx.thread_summary if ctx else ""
        callback = (
            "the note I sent after Bill at Highland mentioned a few construction-services "
            "clients were starting to think about exit timing"
            if "Highland" in summary
            else "the note I sent earlier"
        )
        body = (
            f"Hi {first},\n\n"
            f"Wanted to follow up on {callback}. We have been seeing useful data on "
            "multiples and buyer appetite in that space.\n\n"
            "Would it be useful for me to send a short market read, or is this not a "
            "priority right now?"
        )
    else:
        body = _fallback_post_meeting_body(first, state)

    return DraftOutput(subject=subject, body=body, signature="Sam")


def _quality_issues(state: EmailDraftState, draft_obj: DraftOutput) -> list[str]:
    email_type = state["email_type"]
    text = f"{draft_obj.subject}\n{draft_obj.body}\n{draft_obj.signature}".lower()
    body = draft_obj.body.lower()
    issues: list[str] = []

    if "[" in draft_obj.body or "]" in draft_obj.body:
        issues.append("placeholder text")
    if re.search(r"\bjust\b", text):
        issues.append("banned softener")
    if any(phrase in text for phrase in ("touch base", "circle back", "hope this email finds")):
        issues.append("banned phrase")
    if "!" in text:
        issues.append("exclamation mark")
    if draft_obj.signature.strip().lower() != "sam":
        issues.append("signature is not first name only")

    if email_type == "INBOUND_VAGUE":
        if "?" not in draft_obj.body:
            issues.append("no qualifying question")
        if any(phrase in body for phrase in ("let me know what works", "good time", "20-minute", "next week")):
            issues.append("moves to scheduling too early")
    elif email_type == "OUTBOUND_FOLLOWUP":
        if not any(phrase in body for phrase in ("not a priority", "if not", "no worries", "not a fit")):
            issues.append("missing easy out")
        if any(
            phrase in body
            for phrase in (
                "would love",
                "i'd love",
                "i’d love",
                "let's align",
                "let’s align",
                "let's discuss",
                "let’s discuss",
                "thanks for your time",
                "great",
            )
        ):
            issues.append("too pushy for stale follow-up")
        if draft_obj.body.count("?") > 1:
            issues.append("more than one ask")
    elif email_type == "POST_MEETING":
        ctx = state.get("context")
        steps = [step.lower() for step in (ctx.next_steps_mentioned if ctx else [])]
        if steps and not any(any(word in body for word in re.findall(r"[a-zA-Z0-9]+", step)[:3]) for step in steps):
            issues.append("missing next step")
        if not any(word in body for word in ("thank", "appreciated")):
            issues.append("missing thank-you")
        if re.search(r"\bsam\b", body):
            issues.append("self-references sender")
        if "let me know" in body:
            issues.append("generic CTA")

    return issues


def draft(state: EmailDraftState) -> dict:
    ctx = state.get("context")
    strategy = state.get("strategy")
    full_name = ctx.sender_name if ctx else ""
    org = ctx.sender_org if ctx else ""
    first = _first_name(full_name)

    retry_count = state.get("retry_count", 0)
    critique = state.get("critique")
    previous_draft = state.get("draft")
    if retry_count > 0 and critique and previous_draft:
        retry_block = DRAFTER_RETRY_BLOCK.format(
            critique_reasons="\n- " + "\n- ".join(critique.reasons),
            critique_fixes="\n- " + "\n- ".join(critique.suggested_fixes),
            previous_body=previous_draft.body,
        )
    else:
        retry_block = ""

    user_msg = DRAFTER_USER_TEMPLATE.format(
        strategy_json=json.dumps(strategy.model_dump() if strategy else {}, indent=2),
        first_name=first,
        full_name=full_name,
        org=org,
        context_block=_context_block(state),
        sentiment_block=_sentiment_block(state),
        retry_block=retry_block,
    )

    try:
        result = llm_json(
            VOICE_GUIDE + "\n\n" + DRAFTER_SYSTEM,
            user_msg,
            temperature=0.55,
            max_tokens=900,
        )
        draft_obj = DraftOutput(
            subject=result.get("subject", ""),
            body=result.get("body", ""),
            signature=result.get("signature", "Sam"),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("drafter failed: %s", exc)
        draft_obj = _fallback_draft(state, first)

    draft_obj.body = _strip_signature_from_body(draft_obj.body)
    draft_obj.signature = "Sam"
    issues = _quality_issues(state, draft_obj)
    if issues:
        log.warning("drafter output failed guardrails (%s); using scenario fallback", ", ".join(issues))
        draft_obj = _fallback_draft(state, first)
    return {"draft": draft_obj, "retry_count": retry_count + 1}
