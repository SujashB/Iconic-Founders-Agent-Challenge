"""Stale RA follow-up scanner — flags emails we sent to an RA domain that
have received no reply within STALE_RA_DAYS."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from email_agent.config import CONFIG
from email_agent.scanners._dedupe import DedupeCache
from email_agent.state import TriggerEvent

log = logging.getLogger("email_agent.scanner.stale_followup")


def _is_ra(addr: str) -> bool:
    if not addr or "@" not in addr:
        return False
    domain = addr.split("@", 1)[1].lower()
    return domain in CONFIG.ra_domain_allowlist


def _scan_composio() -> list[TriggerEvent]:
    """Scan sent folder via Composio MCP."""
    from email_agent.tools.composio_outlook import fetch_sent_messages, fetch_inbox_messages

    cache = DedupeCache("stale")
    triggers: list[TriggerEvent] = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=CONFIG.stale_ra_days)

    sent_messages = fetch_sent_messages(limit=200)
    # Pre-fetch inbox for reply checking
    inbox_messages = fetch_inbox_messages(limit=200, unread_only=False)

    for msg in sent_messages:
        # Extract recipients
        to_list = msg.get("toRecipients", []) or msg.get("to", [])
        recipients = []
        for r in to_list:
            if isinstance(r, dict):
                addr = r.get("emailAddress", {}).get("address", "") or r.get("address", "")
            elif isinstance(r, str):
                addr = r
            else:
                continue
            if addr:
                recipients.append(addr)

        ra_recipients = [r for r in recipients if _is_ra(r)]
        if not ra_recipients:
            continue

        # Check if sent date is old enough
        sent_date_str = msg.get("sentDateTime", "") or msg.get("sent", "")
        if sent_date_str:
            try:
                sent_date = datetime.fromisoformat(sent_date_str.replace("Z", "+00:00"))
                if sent_date > cutoff:
                    continue  # too recent
            except (ValueError, TypeError):
                pass

        msg_id = msg.get("id", "") or msg.get("object_id", "")
        conv_id = msg.get("conversationId", "") or msg.get("conversation_id", "")
        cache_key = f"{conv_id}:{msg_id}"
        if cache_key in cache:
            continue

        # Check for replies in the same conversation
        has_reply = False
        if conv_id and sent_date_str:
            for inbox_msg in inbox_messages:
                inbox_conv = inbox_msg.get("conversationId", "") or inbox_msg.get("conversation_id", "")
                if inbox_conv == conv_id:
                    recv_str = inbox_msg.get("receivedDateTime", "") or inbox_msg.get("received", "")
                    if recv_str:
                        try:
                            recv_date = datetime.fromisoformat(recv_str.replace("Z", "+00:00"))
                            sent_dt = datetime.fromisoformat(sent_date_str.replace("Z", "+00:00"))
                            if recv_date > sent_dt:
                                has_reply = True
                                break
                        except (ValueError, TypeError):
                            pass

        if has_reply:
            continue

        days_since = (now - datetime.fromisoformat(sent_date_str.replace("Z", "+00:00"))).days if sent_date_str else CONFIG.stale_ra_days
        first_recipient_name = ""
        if to_list and isinstance(to_list[0], dict):
            first_recipient_name = to_list[0].get("emailAddress", {}).get("name", "")

        triggers.append(
            TriggerEvent(
                kind="OUTBOUND_FOLLOWUP",
                source_ref=msg_id,
                raw_payload={
                    "subject": msg.get("subject", ""),
                    "recipient_name": first_recipient_name,
                    "recipient_email": ra_recipients[0],
                    "recipient_org": ra_recipients[0].split("@", 1)[1],
                    "thread_summary": "",
                    "last_outbound_excerpt": (msg.get("bodyPreview", "") or "")[:600],
                    "days_since_last_touch": days_since,
                },
            )
        )
        cache.add(cache_key)

    cache.flush()
    log.info("stale_followup scanner (composio) emitted %d triggers", len(triggers))
    return triggers


def _scan_o365() -> list[TriggerEvent]:
    """Scan sent folder via O365 Python library."""
    from email_agent.tools.o365 import get_account

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
                continue
            cache_key = f"{msg.conversation_id}:{msg.object_id}"
            if cache_key in cache:
                continue

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


def scan() -> list[TriggerEvent]:
    if CONFIG.has_composio:
        try:
            return _scan_composio()
        except Exception as exc:  # noqa: BLE001
            log.warning("composio scan failed, falling back to O365: %s", exc)
    return _scan_o365()
