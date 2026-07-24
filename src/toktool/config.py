"""Configuration et stockage des identifiants TikTok.

Les identifiants de l'application (client key/secret) viennent des variables
d'environnement ; le jeton d'accès obtenu via OAuth est conservé dans
~/.toktool/credentials.json.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("TOKTOOL_HOME", Path.home() / ".toktool"))
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


def client_key() -> str:
    key = os.environ.get("TIKTOK_CLIENT_KEY", "")
    if not key:
        raise SystemExit(
            "TIKTOK_CLIENT_KEY manquant. Créez une app sur "
            "https://developers.tiktok.com puis exportez TIKTOK_CLIENT_KEY "
            "et TIKTOK_CLIENT_SECRET."
        )
    return key


def client_secret() -> str:
    secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    if not secret:
        raise SystemExit("TIKTOK_CLIENT_SECRET manquant (voir README).")
    return secret


def load_credentials() -> dict:
    if not CREDENTIALS_FILE.exists():
        return {}
    try:
        return json.loads(CREDENTIALS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_credentials(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    CREDENTIALS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
