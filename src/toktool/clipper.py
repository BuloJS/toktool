"""Découpe et mise au format du clip avec ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

# Mode "fit" : la vidéo entière est visible, centrée dans un cadre 1080x1920,
# l'arrière-plan étant la même image agrandie et floutée (rien n'est coupé).
FIT_FILTER = (
    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,boxblur=20:5[bg];"
    "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
)

# Mode "fill" (plein écran) : la vidéo est agrandie pour remplir tout le
# cadre 9:16, les bords qui dépassent sont rognés — rendu TikTok natif.
FILL_FILTER = (
    "scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,setsar=1,format=yuv420p"
)


class ClipError(RuntimeError):
    pass


def cut_clip(
    source: Path,
    offset: float,
    duration: float,
    output: Path,
    vertical: bool = True,
    fill: bool = False,
) -> Path:
    """Coupe `duration` secondes à partir de `offset` dans `source`.

    `vertical` : met au format 9:16. `fill` : remplit tout l'écran en rognant
    les bords (sinon la vidéo entière est gardée avec un fond flou).
    """
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{offset:.3f}",
        "-i", str(source),
        "-t", f"{duration:.3f}",
    ]
    if vertical and fill:
        cmd += ["-vf", FILL_FILTER]
    elif vertical:
        cmd += ["-filter_complex", FIT_FILTER]
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
