from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from email_agent.state import TriggerEvent


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class FixtureCoverageTest(unittest.TestCase):
    def test_each_email_type_has_multiple_fixture_cases(self) -> None:
        counts: Counter[str] = Counter()
        for path in FIXTURES_DIR.glob("*.json"):
            event = TriggerEvent(**json.loads(path.read_text()))
            counts[event.kind] += 1

        self.assertGreaterEqual(counts["INBOUND_VAGUE"], 3)
        self.assertGreaterEqual(counts["OUTBOUND_FOLLOWUP"], 3)
        self.assertGreaterEqual(counts["POST_MEETING"], 3)

    def test_fixture_payloads_have_required_context(self) -> None:
        for path in FIXTURES_DIR.glob("*.json"):
            with self.subTest(path=path.name):
                event = TriggerEvent(**json.loads(path.read_text()))
                payload = event.raw_payload
                self.assertTrue(payload.get("subject"))
                if event.kind == "INBOUND_VAGUE":
                    self.assertTrue(payload.get("sender_name"))
                    self.assertTrue(payload.get("sender_email"))
                    self.assertTrue(payload.get("body"))
                    body = payload.get("body", "").lower()
                    self.assertTrue(
                        any(phrase in body for phrase in ("connect", "quick chat", "intro call")),
                        body,
                    )
                elif event.kind == "OUTBOUND_FOLLOWUP":
                    self.assertTrue(payload.get("recipient_name"))
                    self.assertTrue(payload.get("recipient_email"))
                    self.assertTrue(payload.get("last_outbound_excerpt"))
                    self.assertGreaterEqual(payload.get("days_since_last_touch", 0), 10)
                else:
                    self.assertTrue(payload.get("organizer_name"))
                    self.assertTrue(payload.get("attendees"))
                    self.assertTrue(payload.get("body"))
                    self.assertTrue(payload.get("next_steps"))


if __name__ == "__main__":
    unittest.main()
