"""Stale RA follow-up scanner — flags emails we sent to an RA domain that
have received no reply within STALE_RA_DAYS."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from email_agent.config import CONFIG
from email_agent.scanners._dedupe import DedupeCache
from email_agent.state import TriggerEvent
from email_agent.tools.o365 import get_account

log = logging.getLogger("email_agent.scanner.stale_followup")


def _is_ra(addr: str) -> bool:
    if not addr or "@" not in addr:
        return False
    domain = addr.split("@", 1)[1].lower()
    return domain in CONFIG.ra_domain_allowlist


def scan() -> list[TriggerEvent]:
    account = get_account()
    if account is None:
        log.info("stale_followup scanner: no O365 account, returning empty")
        return []

    cache = DedupeCache("stale")
    triggers: list[TriggerEvent] = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=CONFIG.stale_ra_days)
    history_floor = now - timedelta(days=90)

    try:
        mailbox = account.mailbox()
        sent = mailbox.sent_folder()
        sent_messages = sent.get_messages(
            limit=200,
            query=mailbox.q().chain("and").received.greater_equal(history_floor),
        )
        for msg in sent_messages:
            recipients = [r.address for r in (msg.to or [])]
            ra_recipients = [r for r in recipients if _is_ra(r)]
            if not ra_recipients:
                continue
            if msg.sent and msg.sent > cutoff:
                continue  # too recent
            cache_key = f"{msg.conversation_id}:{msg.object_id}"
            if cache_key in cache:
                continue

            # Look for any reply in the same conversation since this message
            inbox = mailbox.inbox_folder()
            replies = list(
                inbox.get_messages(
                    limit=5,
                    query=mailbox.q().chain("and").conversation_id.equals(msg.conversation_id),
                )
            )
            has_reply = any(r.received > msg.sent for r in replies if r.received and msg.sent)
            if has_reply:
                continue

            days_since = (now - msg.sent).days if msg.sent else CONFIG.stale_ra_days
            triggers.append(
                TriggerEvent(
                    kind="OUTBOUND_FOLLOWUP",
                    source_ref=str(msg.object_id),
                    raw_payload={
                        "subject": msg.subject,
                        "recipient_name": (msg.to[0].name if msg.to else ""),
                        "recipient_email": ra_recipients[0],
                        "recipient_org": ra_recipients[0].split("@", 1)[1],
                        "thread_summary": "",
                        "last_outbound_excerpt": (msg.body_preview or "")[:600],
                        "days_since_last_touch": days_since,
                    },
                )
            )
            cache.add(cache_key)
    except Exception as exc:  # noqa: BLE001
        log.warning("stale_followup scanner failed: %s", exc)
    finally:
        cache.flush()

    log.info("stale_followup scanner emitted %d triggers", len(triggers))
    return triggers
