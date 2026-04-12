"""Inbound vague RA request scanner — finds unread inbox messages from
allowlisted RA domains. The classifier downstream confirms vagueness."""
from __future__ import annotations

import logging

from email_agent.config import CONFIG
from email_agent.scanners._dedupe import DedupeCache
from email_agent.state import TriggerEvent
from email_agent.tools.o365 import get_account

log = logging.getLogger("email_agent.scanner.inbound_vague")


def _is_ra(addr: str) -> bool:
    if not addr or "@" not in addr:
        return False
    return addr.split("@", 1)[1].lower() in CONFIG.ra_domain_allowlist


def scan() -> list[TriggerEvent]:
    account = get_account()
    if account is None:
        log.info("inbound_vague scanner: no O365 account, returning empty")
        return []

    cache = DedupeCache("inbound")
    triggers: list[TriggerEvent] = []

    try:
        mailbox = account.mailbox()
        inbox = mailbox.inbox_folder()
        unread = inbox.get_messages(
            limit=50,
            query=mailbox.q().chain("and").is_read.equals(False),
        )
        for msg in unread:
            sender_addr = msg.sender.address if msg.sender else ""
            if not _is_ra(sender_addr):
                continue
            if str(msg.object_id) in cache:
                continue
            triggers.append(
                TriggerEvent(
                    kind="INBOUND_VAGUE",
                    source_ref=str(msg.object_id),
                    raw_payload={
                        "subject": msg.subject,
                        "sender_name": getattr(msg.sender, "name", "") if msg.sender else "",
                        "sender_email": sender_addr,
                        "sender_org": sender_addr.split("@", 1)[1] if sender_addr else "",
                        "sender": sender_addr,
                        "body": (msg.body_preview or "")[:1500],
                    },
                )
            )
            cache.add(str(msg.object_id))
    except Exception as exc:  # noqa: BLE001
        log.warning("inbound_vague scanner failed: %s", exc)
    finally:
        cache.flush()

    log.info("inbound_vague scanner emitted %d triggers", len(triggers))
    return triggers
