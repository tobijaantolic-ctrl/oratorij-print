from __future__ import annotations

import argparse
import json
from pathlib import Path


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create .streamlit/secrets.toml from a Google service-account JSON."
    )
    parser.add_argument("service_account_json", type=Path)
    parser.add_argument("--drive-folder-id", required=True)
    parser.add_argument("--sheet-id", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument(
        "--oauth-client-id",
        help="OAuth client_id (run scripts/get_refresh_token.py first).",
    )
    parser.add_argument("--oauth-client-secret")
    parser.add_argument("--oauth-refresh-token")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(".streamlit/secrets.toml"),
        help="Output path. Default: .streamlit/secrets.toml",
    )
    args = parser.parse_args()

    data = json.loads(args.service_account_json.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"admin_password = {toml_string(args.admin_password)}",
        f"drive_folder_id = {toml_string(args.drive_folder_id)}",
        f"sheet_id = {toml_string(args.sheet_id)}",
        "",
    ]

    if args.oauth_client_id or args.oauth_client_secret or args.oauth_refresh_token:
        if not (args.oauth_client_id and args.oauth_client_secret and args.oauth_refresh_token):
            parser.error("Provide all three: --oauth-client-id, --oauth-client-secret, --oauth-refresh-token")
        lines += [
            "[google_oauth]",
            f"client_id = {toml_string(args.oauth_client_id)}",
            f"client_secret = {toml_string(args.oauth_client_secret)}",
            f"refresh_token = {toml_string(args.oauth_refresh_token)}",
            "",
        ]

    lines.append("[gcp_service_account]")
    for key, value in data.items():
        if isinstance(value, str):
            lines.append(f"{key} = {toml_string(value)}")
        else:
            lines.append(f"{key} = {json.dumps(value)}")

    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    print("Copy the same file content into Streamlit Cloud > App settings > Secrets.")


if __name__ == "__main__":
    main()
