"""
Run this ONCE locally to obtain a Google OAuth refresh_token for the
Oratorij Print Uploader app.

Usage:
    pip install google-auth-oauthlib
    python scripts/get_refresh_token.py path/to/client_secret_*.json

A browser window opens; sign in with the Google account that owns the Drive
folder + Sheet, approve the consent screen, then the refresh_token (+ client
id/secret) is printed. Paste those three values into .streamlit/secrets.toml
(and into Streamlit Cloud → Settings → Secrets).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


# drive.file = upload + manage files this app creates (non-sensitive scope)
# spreadsheets = read/write Sheets (used by gspread)
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("client_secret_json", type=Path)
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.client_secret_json), scopes=SCOPES
    )
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline",
        open_browser=True,
    )

    data = json.loads(args.client_secret_json.read_text())
    installed = data.get("installed") or data.get("web") or {}

    print()
    print("=" * 70)
    print("PASTE INTO .streamlit/secrets.toml (and Streamlit Cloud Secrets):")
    print("=" * 70)
    print()
    print("[google_oauth]")
    print(f'client_id = "{installed["client_id"]}"')
    print(f'client_secret = "{installed["client_secret"]}"')
    print(f'refresh_token = "{creds.refresh_token}"')
    print()
    print("=" * 70)
    print("Keep these secret. Do NOT commit secrets.toml.")


if __name__ == "__main__":
    main()
