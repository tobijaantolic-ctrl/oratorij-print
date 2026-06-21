"""
One-shot helper: opens browser for OAuth consent, retrieves refresh_token,
and patches .streamlit/secrets.toml with [google_oauth] section.

Usage (run from repo root):
    pip install google-auth-oauthlib
    python scripts/setup_oauth.py
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
CRED_DIR = REPO_ROOT / "credentials"
SECRETS_PATH = REPO_ROOT / ".streamlit" / "secrets.toml"


def find_client_secret() -> Path:
    matches = sorted(glob.glob(str(CRED_DIR / "client_secret*.json")))
    if not matches:
        print(f"ERROR: No client_secret_*.json found in {CRED_DIR}/.")
        print("Move the OAuth client JSON from Downloads into that folder first.")
        sys.exit(1)
    if len(matches) > 1:
        print(f"Multiple client_secret files found; using {matches[-1]}")
    return Path(matches[-1])


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def patch_secrets_with_oauth(client_id: str, client_secret: str, refresh_token: str) -> None:
    if not SECRETS_PATH.exists():
        print(f"ERROR: {SECRETS_PATH} not found. Run make_streamlit_secrets.py first.")
        sys.exit(1)

    text = SECRETS_PATH.read_text(encoding="utf-8")

    new_block = (
        "[google_oauth]\n"
        f"client_id = {toml_string(client_id)}\n"
        f"client_secret = {toml_string(client_secret)}\n"
        f"refresh_token = {toml_string(refresh_token)}\n"
    )

    if "[google_oauth]" in text:
        # Replace existing block
        text = re.sub(
            r"\[google_oauth\][^\[]*",
            new_block + "\n",
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        # Insert before [gcp_service_account]
        text = text.replace(
            "[gcp_service_account]",
            new_block + "\n[gcp_service_account]",
        )

    SECRETS_PATH.write_text(text, encoding="utf-8")
    print(f"Updated {SECRETS_PATH}")


def main() -> None:
    client_secret_path = find_client_secret()
    print(f"Using OAuth client: {client_secret_path.name}")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes=SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline",
        open_browser=True,
    )

    if not creds.refresh_token:
        print("ERROR: No refresh_token returned. Re-run after revoking previous consent.")
        sys.exit(1)

    data = json.loads(client_secret_path.read_text())
    installed = data.get("installed") or data.get("web") or {}
    client_id = installed["client_id"]
    client_secret = installed["client_secret"]

    patch_secrets_with_oauth(client_id, client_secret, creds.refresh_token)

    print("\nNow paste the full contents of .streamlit/secrets.toml")
    print("into Streamlit Cloud → App settings → Secrets, then save.")


if __name__ == "__main__":
    main()
