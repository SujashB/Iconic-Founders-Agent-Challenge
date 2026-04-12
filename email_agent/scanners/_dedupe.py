"""Tiny JSON-backed dedupe cache used by all three scanners."""
from __future__ import annotations

import json
from pathlib import Path

from email_agent.config import CONFIG


class DedupeCache:
    def __init__(self, name: str) -> None:
        self.path: Path = CONFIG.state_dir / f"processed_{name}.json"
        self._seen: set[str] = set()
        if self.path.exists():
            try:
                self._seen = set(json.loads(self.path.read_text()))
            except Exception:  # noqa: BLE001
                self._seen = set()

    def __contains__(self, key: str) -> bool:
        return key in self._seen

    def add(self, key: str) -> None:
        self._seen.add(key)

    def flush(self) -> None:
        self.path.write_text(json.dumps(sorted(self._seen)))
