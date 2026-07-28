"""Suggestions de titres et de hashtags à partir des métadonnées YouTube.

Aucune API externe : on lit les métadonnées publiques de la vidéo
(`yt-dlp --dump-json`) — titre, description, tags, catégorie, chaîne — et on
en dérive des propositions de légende TikTok. Tout est renvoyé, l'utilisateur
choisit (ou le mode automatique prend la première proposition).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field

# Hashtags génériques qui aident à la découvrabilité, ajoutés en complément
# de ceux tirés du contenu.
GENERIC_HASHTAGS = ["fyp", "pourtoi", "viral", "clip"]

# Mots vides ignorés lors de la fabrication de hashtags (FR + EN).
STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "les", "des", "une", "un",
    "de", "la", "le", "du", "en", "et", "à", "au", "aux", "ce", "ça", "sur",
    "dans", "pour", "avec", "par", "que", "qui", "est", "son", "ses", "mon",
    "official", "video", "audio", "lyrics", "ft", "feat", "hd", "4k",
}

# Catégorie YouTube -> hashtags TikTok pertinents.
CATEGORY_HASHTAGS = {
    "Music": ["musique", "music", "song"],
    "Gaming": ["gaming", "jeuxvideo", "gamer"],
    "Comedy": ["humour", "drole", "funny"],
    "Sports": ["sport", "football", "highlights"],
    "Entertainment": ["divertissement", "buzz"],
    "Film & Animation": ["film", "cinema", "movie"],
    "News & Politics": ["actu", "news"],
    "Education": ["apprendresurtiktok", "education"],
    "Science & Technology": ["tech", "science"],
    "Howto & Style": ["tuto", "astuce", "diy"],
    "People & Blogs": ["vlog", "story"],
}

WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+")


@dataclass
class Suggestions:
    source_title: str
    channel: str
    category: str
    titles: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)

    def caption(self, index: int = 0) -> str:
        """Légende prête à l'emploi : un titre + la ligne de hashtags."""
        title = self.titles[index] if self.titles else self.source_title
        tags = " ".join("#" + h for h in self.hashtags)
        return f"{title}\n\n{tags}".strip()


def fetch_metadata(url: str) -> dict:
    """Récupère les métadonnées JSON de la vidéo sans la télécharger."""
    from .downloader import ytdlp_base

    cmd = [*ytdlp_base(), "--no-playlist", "--skip-download", "--dump-json", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Impossible de lire les métadonnées YouTube :\n"
            + result.stderr.strip()[-800:]
        )
    return json.loads(result.stdout)


def _keywords(text: str, limit: int) -> list[str]:
    seen: list[str] = []
    for match in WORD_RE.finditer(text.lower()):
        word = match.group()
        if len(word) < 3 or word in STOPWORDS or word.isdigit():
            continue
        if word not in seen:
            seen.append(word)
        if len(seen) >= limit:
            break
    return seen


def build_hashtags(meta: dict, limit: int = 12) -> list[str]:
    tags: list[str] = []

    def add(raw: str) -> None:
        clean = WORD_RE.findall(raw.lower())
        if not clean:
            return
        tag = "".join(clean)  # un hashtag = pas d'espace
        if 2 <= len(tag) <= 30 and tag not in tags and tag not in STOPWORDS:
            tags.append(tag)

    for category in meta.get("categories") or []:
        for h in CATEGORY_HASHTAGS.get(category, []):
            add(h)

    for tag in (meta.get("tags") or [])[:15]:
        add(tag)

    for word in _keywords(meta.get("title", ""), limit):
        add(word)

    for generic in GENERIC_HASHTAGS:
        add(generic)

    return tags[:limit]


def build_titles(meta: dict) -> list[str]:
    original = (meta.get("title") or "").strip()
    channel = (meta.get("uploader") or meta.get("channel") or "").strip()
    keywords = _keywords(original, 3)
    hook = " ".join(w.capitalize() for w in keywords) if keywords else original

    candidates = [
        original,
        f"{original} 🔥" if original else "",
        f"Le passage à ne pas rater : {hook} 👀" if hook else "",
        f"{hook} — vous en pensez quoi ? 💬" if hook else "",
    ]
    if channel:
        candidates.append(f"{original} (via {channel})")

    # Déduplique en préservant l'ordre, retire les vides, tronque à 150 car.
    seen: list[str] = []
    for c in candidates:
        c = c.strip()[:150]
        if c and c not in seen:
            seen.append(c)
    return seen


def suggest(url: str) -> Suggestions:
    meta = fetch_metadata(url)
    categories = meta.get("categories") or []
    return Suggestions(
        source_title=(meta.get("title") or "").strip(),
        channel=(meta.get("uploader") or meta.get("channel") or "").strip(),
        category=categories[0] if categories else "",
        titles=build_titles(meta),
        hashtags=build_hashtags(meta),
    )


def suggest_from_meta(meta: dict) -> Suggestions:
    """Variante quand les métadonnées sont déjà en main (évite un 2e appel)."""
    categories = meta.get("categories") or []
    return Suggestions(
        source_title=(meta.get("title") or "").strip(),
        channel=(meta.get("uploader") or meta.get("channel") or "").strip(),
        category=categories[0] if categories else "",
        titles=build_titles(meta),
        hashtags=build_hashtags(meta),
    )
