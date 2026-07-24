"""Authentification OAuth TikTok et publication via la Content Posting API.

Documentation officielle :
- OAuth : https://developers.tiktok.com/doc/oauth-user-access-token-management
- Direct Post : https://developers.tiktok.com/doc/content-posting-api-get-started
"""

from __future__ import annotations

import hashlib
import http.server
import secrets
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests

from . import config

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

REDIRECT_PORT = 8763
SCOPES = "user.info.basic,video.publish"

# Un fichier <= 64 Mo peut être envoyé en un seul chunk.
SINGLE_CHUNK_MAX = 64 * 1024 * 1024


class TikTokError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# OAuth
# --------------------------------------------------------------------------

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Récupère le paramètre `code` renvoyé par TikTok sur le redirect."""

    received: dict = {}

    def do_GET(self):  # noqa: N802
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CallbackHandler.received = {k: v[0] for k, v in params.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "<h2>Autorisation reçue, vous pouvez fermer cet onglet.</h2>".encode()
        )

    def log_message(self, *args):  # silence
        pass


def _build_auth_url(state: str, challenge: str) -> str:
    params = {
        "client_key": config.client_key(),
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": config.redirect_uri(),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def _extract_code(pasted: str, state: str) -> str:
    """Récupère le `code` depuis une URL de redirection collée (ou le code seul)."""
    pasted = pasted.strip()
    if "code=" in pasted or "?" in pasted:
        query = urllib.parse.urlparse(pasted).query or pasted
        params = urllib.parse.parse_qs(query)
        got_state = (params.get("state") or [None])[0]
        if got_state and got_state != state:
            raise TikTokError("Paramètre state invalide, tentative rejetée.")
        codes = params.get("code")
        if not codes:
            raise TikTokError(f"Aucun code trouvé dans : {pasted!r}")
        return codes[0]
    return pasted  # l'utilisateur a collé le code brut


def authorize(manual: bool | None = None) -> dict:
    """Flow OAuth complet (PKCE) ; renvoie et sauvegarde les jetons.

    `manual=None` (défaut) : mode choisi automatiquement — serveur local si
    l'URL de redirection pointe vers localhost, sinon mode manuel (on colle
    l'URL de retour), adapté à une page HTTPS et à un usage depuis le téléphone.
    `manual=True`/`False` force le mode.
    """
    verifier = secrets.token_urlsafe(48)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()
    state = secrets.token_urlsafe(16)
    url = _build_auth_url(state, challenge)
    redirect = config.redirect_uri()
    if manual is None:
        manual = "localhost" not in redirect and "127.0.0.1" not in redirect

    if manual:
        print("1. Ouvrez cette URL dans votre navigateur (téléphone ok) :\n")
        print(f"   {url}\n")
        print("2. Autorisez l'accès. Vous êtes redirigé vers la page de retour ;")
        print("   elle affiche un code (ou l'URL contient ...?code=...&state=...).")
        print("   Copiez-le et collez-le ci-dessous.\n")
        pasted = input("URL de redirection (ou code) : ").strip()
        code = _extract_code(pasted, state)
        return _exchange_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect,
                "code_verifier": verifier,
            }
        )

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Ouvrez cette URL dans votre navigateur si elle ne s'ouvre pas seule :")
    print(f"  {url}")
    webbrowser.open(url)

    thread.join(timeout=300)
    server.server_close()
    received = _CallbackHandler.received
    if not received:
        raise TikTokError("Aucune réponse OAuth reçue (délai de 5 min dépassé).")
    if received.get("state") != state:
        raise TikTokError("Paramètre state invalide, tentative rejetée.")
    if "code" not in received:
        raise TikTokError(f"Autorisation refusée : {received}")

    return _exchange_token(
        {
            "grant_type": "authorization_code",
            "code": received["code"],
            "redirect_uri": redirect,
            "code_verifier": verifier,
        }
    )


def _exchange_token(extra: dict) -> dict:
    data = {
        "client_key": config.client_key(),
        "client_secret": config.client_secret(),
        **extra,
    }
    resp = requests.post(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    payload = resp.json()
    if "access_token" not in payload:
        raise TikTokError(f"Échec d'obtention du jeton : {payload}")
    payload["expires_at"] = time.time() + payload.get("expires_in", 86400)
    config.save_credentials(payload)
    return payload


def get_access_token() -> str:
    """Jeton valide, rafraîchi automatiquement si expiré."""
    creds = config.load_credentials()
    if not creds:
        raise SystemExit("Aucun compte connecté : lancez d'abord `toktool auth`.")
    if time.time() > creds.get("expires_at", 0) - 120:
        creds = _exchange_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": creds["refresh_token"],
            }
        )
    return creds["access_token"]


# --------------------------------------------------------------------------
# Publication
# --------------------------------------------------------------------------

def upload_video(
    video: Path,
    title: str,
    privacy_level: str = "SELF_ONLY",
) -> str:
    """Publie la vidéo en Direct Post ; renvoie le publish_id TikTok."""
    token = get_access_token()
    size = video.stat().st_size
    if size > SINGLE_CHUNK_MAX:
        raise TikTokError(
            f"Fichier de {size / 1e6:.0f} Mo : au-delà de 64 Mo, réduisez la "
            "qualité ou la durée du clip."
        )

    init_body = {
        "post_info": {
            "title": title[:2200],
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,
            "total_chunk_count": 1,
        },
    }
    resp = requests.post(
        INIT_URL,
        json=init_body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    payload = resp.json()
    data = payload.get("data") or {}
    if resp.status_code != 200 or "upload_url" not in data:
        raise TikTokError(f"Échec d'initialisation de la publication : {payload}")

    upload_resp = requests.put(
        data["upload_url"],
        data=video.read_bytes(),
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        },
        timeout=600,
    )
    if upload_resp.status_code not in (200, 201):
        raise TikTokError(
            f"Échec de l'envoi du fichier ({upload_resp.status_code}) : "
            f"{upload_resp.text[:500]}"
        )
    return data["publish_id"]


def wait_for_publish(publish_id: str, timeout: int = 300) -> str:
    """Interroge le statut jusqu'à publication effective ou échec."""
    token = get_access_token()
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.post(
            STATUS_URL,
            json={"publish_id": publish_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        data = (resp.json() or {}).get("data") or {}
        status = data.get("status", "UNKNOWN")
        if status == "PUBLISH_COMPLETE":
            return status
        if status in ("FAILED", "PUBLISH_FAILED"):
            raise TikTokError(f"Publication refusée par TikTok : {data}")
        time.sleep(5)
    return "PROCESSING"
