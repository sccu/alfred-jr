"""One-time OAuth flow to generate token.json for Gmail access.

Usage:
    uv run scripts/gmail_auth.py [path/to/credentials.json]

Defaults to credentials.json in the project root.
Saves token.json alongside the credentials file.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCOPES = ["https://mail.google.com/"]


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path = sys.argv[1] if len(sys.argv) > 1 else "credentials.json"
    token_path = str(Path(credentials_path).parent / "token.json")

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, _SCOPES)
    creds = flow.run_local_server(port=0)
    Path(token_path).write_text(creds.to_json())
    print(f"저장됨: {token_path}")


if __name__ == "__main__":
    main()
