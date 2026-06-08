#!/usr/bin/env python3
"""
One-time OAuth setup for YouTube Data API.

Run locally (no GitHub Action). Will:
  1. Ask for your Google Cloud OAuth Client ID + Client Secret
  2. Open your browser for authorization
  3. Print a refresh token that you'll save as a GitHub Secret

After running this once, you never need to run it again unless the
refresh token gets revoked.

Install first:
    pip install google-auth-oauthlib

Then run:
    python scripts/get_youtube_refresh_token.py
"""

import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("ERROR: missing dependency. Install with:")
    print("    pip install google-auth-oauthlib")
    sys.exit(1)


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def clean(s: str) -> str:
    """Strip whitespace, quotes, and non-printable characters from pasted input."""
    return "".join(ch for ch in s.strip().strip('"').strip("'") if ch.isprintable())


def main():
    print("\n" + "=" * 60)
    print(" YouTube OAuth Refresh Token Generator")
    print("=" * 60)
    print(
        "\nVoy a pedirte el Client ID y Client Secret.\n"
        "Esta vez los verás mientras los pegas para que confirmes.\n"
        "El Client Secret comienza con 'GOCSPX-'.\n"
    )

    client_id = clean(input("Paste your Client ID: "))
    client_secret = clean(input("Paste your Client Secret: "))

    if not client_id or not client_secret:
        print("\nERROR: both Client ID and Client Secret are required")
        sys.exit(1)

    # Show partial values so user can verify before authorizing
    print(f"\n  Client ID:     {client_id[:15]}...{client_id[-25:]}")
    print(f"  Client Secret: {client_secret[:8]}...{client_secret[-4:]}")
    confirm = input("\n¿Se ven correctos? (s/n): ").strip().lower()
    if confirm not in ("s", "si", "sí", "y", "yes"):
        print("Aborted. Re-run the script with the correct values.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    print("\nOpening browser for Google authorization…\n")
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline",
        authorization_prompt_message=(
            "Si no se abre solo, copia esta URL en tu browser: {url}"
        ),
        success_message="Listo! Ya puedes cerrar esta pestaña y volver a la terminal.",
    )

    if not credentials.refresh_token:
        print("\nERROR: no refresh_token returned. Asegúrate de:")
        print("  1. Haber agregado tu email como Test User en OAuth consent screen")
        print("  2. Haber elegido 'Desktop app' al crear las credenciales")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(" REFRESH TOKEN (guárdalo bien):")
    print("=" * 60)
    print(credentials.refresh_token)
    print("=" * 60)
    print(
        "\nAgrega estos 3 secrets a GitHub:\n"
        "    YOUTUBE_CLIENT_ID = <Client ID que ingresaste>\n"
        "    YOUTUBE_CLIENT_SECRET = <Client Secret que ingresaste>\n"
        "    YOUTUBE_REFRESH_TOKEN = el token de arriba\n"
        "\nGitHub Secrets URL:"
        "\n    https://github.com/jovenjuanpirami/pld.mx/settings/secrets/actions\n"
    )


if __name__ == "__main__":
    main()
