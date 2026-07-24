"""Découpe et mise au format du clip avec ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

# Filtre 9:16 : la vidéo est ajustée dans un cadre 1080x1920, l'arrière-plan
# est la même image agrandie et floutée (rendu classique TikTok).
VERTICAL_FILTER = (
    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,boxblur=20:5[bg];"
    "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
)


class ClipError(RuntimeError):
    pass


def cut_clip(
    source: Path,
    offset: float,
    duration: float,
    output: Path,
    vertical: bool = True,
) -> Path:
    """Coupe `duration` secondes à partir de `offset` dans `source`."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{offset:.3f}",
        "-i", str(source),
        "-t", f"{duration:.3f}",
    ]
    if vertical:
        cmd += ["-filter_complex", VERTICAL_FILTER]
    else:
        cmd += ["-vf", "format=yuv420p"]
    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ClipError(f"Échec ffmpeg :\n{result.stderr.strip()[-2000:]}")
    if not output.exists() or output.stat().st_size == 0:
        raise ClipError("ffmpeg n'a produit aucun fichier de sortie.")
    return output
