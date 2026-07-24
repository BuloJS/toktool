"""Téléchargement de la section utile d'une vidéo YouTube via yt-dlp."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Marge téléchargée autour du clip pour garantir une coupe précise ensuite.
PADDING_SECONDS = 5


class DownloadError(RuntimeError):
    pass


def check_dependencies() -> None:
    missing = [tool for tool in ("yt-dlp", "ffmpeg") if shutil.which(tool) is None]
    if missing:
        raise SystemExit(
            "Outils manquants : " + ", ".join(missing)
            + ". Installez-les (pip install yt-dlp ; apt/brew install ffmpeg)."
        )


def download_section(
    url: str, start: float, end: float, workdir: Path
) -> tuple[Path, float]:
    """Télécharge [start-marge, end+marge] de la vidéo.

    Renvoie (fichier, timecode absolu du début du fichier téléchargé), pour
    que la découpe précise puisse se faire relativement à ce fichier.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    output_template = str(workdir / "source.%(ext)s")
    section_start = max(0.0, start - PADDING_SECONDS)
    section_end = end + PADDING_SECONDS

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--force-keyframes-at-cuts",
        "--download-sections", f"*{section_start:.2f}-{section_end:.2f}",
        # Flux vidéo <=1080p + meilleur audio, fusionnés en mp4.
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "-o", output_template,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise DownloadError(
            f"Échec du téléchargement yt-dlp :\n{result.stderr.strip()[-2000:]}"
        )

    files = sorted(workdir.glob("source.*"))
    if not files:
        raise DownloadError("yt-dlp n'a produit aucun fichier.")
    return files[0], section_start
