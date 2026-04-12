"""One-time OAuth flow for Outlook (delegated permissions).

Run this once after configuring MS_CLIENT_ID / MS_CLIENT_SECRET / MS_TENANT_ID
in .env. It will open a browser, prompt consent, and persist the token to
o365_token.txt (gitignored). Subsequent runs of the agent reuse the token.
"""
from __future__ import annotations

import sys

from email_agent.config import CONFIG

SCOPES = [
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.Read",
    "User.Read",
    "offline_access",
]


def main() -> int:
    if not CONFIG.has_o365_creds:
        print(
            "ERROR: MS_CLIENT_ID, MS_CLIENT_SECRET, and MS_TENANT_ID must all be set in .env",
            file=sys.stderr,
        )
        return 1

    try:
        from O365 import Account, FileSystemTokenBackend
    except ImportError:
        print("ERROR: O365 library not installed. Run: pip install O365", file=sys.stderr)
        return 1

    token_backend = FileSystemTokenBackend(
        token_path=str(CONFIG.o365_token_path.parent),
        token_filename=CONFIG.o365_token_path.name,
    )
    account = Account(
        credentials=(CONFIG.ms_client_id, CONFIG.ms_client_secret),
        tenant_id=CONFIG.ms_tenant_id,
        token_backend=token_backend,
    )

    if account.is_authenticated:
        print("Already authenticated. Token at:", CONFIG.o365_token_path)
    else:
        print("Opening browser for OAuth consent ...")
        if not account.authenticate(scopes=SCOPES):
            print("ERROR: authentication failed", file=sys.stderr)
            return 1
        print("Token saved to:", CONFIG.o365_token_path)

    # Smoke test: list 3 most recent inbox subjects
    try:
        mailbox = account.mailbox()
        inbox = mailbox.inbox_folder()
        messages = list(inbox.get_messages(limit=3))
        print(f"\nMost recent {len(messages)} inbox subjects:")
        for msg in messages:
            print(f"  - {msg.subject}")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: smoke test failed: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
