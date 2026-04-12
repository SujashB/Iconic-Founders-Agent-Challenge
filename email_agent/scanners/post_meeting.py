"""Post-meeting scanner — finds meetings that ended in the last N hours
with at least one external attendee."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from email_agent.config import CONFIG
from email_agent.scanners._dedupe import DedupeCache
from email_agent.state import TriggerEvent
from email_agent.tools.o365 import get_account

log = logging.getLogger("email_agent.scanner.post_meeting")


def _is_external(attendee_email: str, organizer_email: str) -> bool:
    if not attendee_email or "@" not in attendee_email:
        return False
    return attendee_email.split("@", 1)[1] != organizer_email.split("@", 1)[1]


def scan() -> list[TriggerEvent]:
    account = get_account()
    if account is None:
        log.info("post_meeting scanner: no O365 account, returning empty")
        return []

    cache = DedupeCache("events")
    triggers: list[TriggerEvent] = []
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=CONFIG.post_meeting_lookback_hours)

    try:
        schedule = account.schedule()
        calendar = schedule.get_default_calendar()
        events = calendar.get_events(
            start_recurring=window_start,
            end_recurring=now,
            include_recurring=False,
        )
        organizer_email = account.get_current_user().mail or ""
        for event in events:
            event_id = str(event.object_id)
            if event_id in cache:
                continue
            end = event.end if event.end else now
            if end > now or end < window_start:
                continue
            attendees = [a.address for a in (event.attendees or [])]
            external = [a for a in attendees if _is_external(a, organizer_email)]
            if not external:
                continue
            triggers.append(
                TriggerEvent(
                    kind="POST_MEETING",
                    source_ref=event_id,
                    raw_payload={
                        "subject": event.subject,
                        "organizer_name": getattr(event.organizer, "name", "") if event.organizer else "",
                        "organizer_email": organizer_email,
                        "attendees": attendees,
                        "body": event.body or "",
                        "next_steps": [],
                    },
                )
            )
            cache.add(event_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("post_meeting scanner failed: %s", exc)
    finally:
        cache.flush()

    log.info("post_meeting scanner emitted %d triggers", len(triggers))
    return triggers
