"""Interface en ligne de commande de toktool.

Usage typique :
    toktool auth
    toktool clip "https://youtu.be/XXXX" --start 12:30 --duration 45 \
        --title "Mon clip" --publish
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from . import MAX_CLIP_SECONDS, clipper, downloader, tiktok

TIMECODE_RE = re.compile(r"^(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)$")


def parse_timecode(value: str) -> float:
    """Accepte 90, 1:30, 01:02:03 ou 12.5 et renvoie des secondes."""
    match = TIMECODE_RE.match(value.strip())
    if not match:
        raise argparse.ArgumentTypeError(f"timecode invalide : {value!r}")
    h, m, s = match.groups()
    seconds = float(s)
    if m is not None:
        seconds += int(m) * 60
        seconds += int(h) * 3600
    elif h is not None:
        seconds += int(h) * 60
    return seconds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toktool",
        description="Clip une vidéo YouTube (max 60 s) et la publie sur TikTok.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", help="Connecter votre compte TikTok (OAuth).")

    clip = sub.add_parser("clip", help="Créer un clip et (option) le publier.")
    clip.add_argument("url", help="URL de la vidéo YouTube.")
    clip.add_argument(
        "--start", type=parse_timecode, required=True,
        help="Timecode de début (ex : 90, 1:30, 00:12:30).",
    )
    group = clip.add_mutually_exclusive_group()
    group.add_argument(
        "--duration", type=parse_timecode,
        help=f"Durée du clip en secondes (max {MAX_CLIP_SECONDS}).",
    )
    group.add_argument(
        "--end", type=parse_timecode,
        help="Timecode de fin (au plus start + 60 s).",
    )
    clip.add_argument(
        "--title", default="",
        help="Légende/titre TikTok (hashtags inclus).",
    )
    clip.add_argument(
        "-o", "--output", type=Path,
        help="Fichier mp4 de sortie (défaut : ./clip_<start>.mp4).",
    )
    clip.add_argument(
        "--no-vertical", action="store_true",
        help="Conserver le format d'origine au lieu du 9:16 avec fond flouté.",
    )
    clip.add_argument(
        "--publish", action="store_true",
        help="Publier sur TikTok après la découpe (sinon : fichier local seul).",
    )
    clip.add_argument(
        "--privacy",
        default="SELF_ONLY",
        choices=["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
        help="Visibilité TikTok (SELF_ONLY par défaut ; les apps non auditées "
        "par TikTok ne peuvent publier qu'en SELF_ONLY).",
    )
    return parser


def cmd_auth() -> int:
    tiktok.authorize()
    print("Compte TikTok connecté, jetons enregistrés dans ~/.toktool/.")
    return 0


def cmd_clip(args: argparse.Namespace) -> int:
    if args.duration is not None:
        duration = args.duration
    elif args.end is not None:
        duration = args.end - args.start
    else:
        duration = float(MAX_CLIP_SECONDS)
    if duration <= 0:
        print("La fin du clip doit être après le début.", file=sys.stderr)
        return 1
    if duration > MAX_CLIP_SECONDS:
        print(
            f"Durée demandée {duration:.0f} s : plafonnée à {MAX_CLIP_SECONDS} s.",
        )
        duration = float(MAX_CLIP_SECONDS)

    downloader.check_dependencies()
    output = args.output or Path(f"clip_{int(args.start)}s.mp4")

    with tempfile.TemporaryDirectory(prefix="toktool-") as tmp:
        print(f"1/3 Téléchargement de la section utile ({args.url})…")
        source, file_start = downloader.download_section(
            args.url, args.start, args.start + duration, Path(tmp)
        )
        print("2/3 Découpe et encodage du clip…")
        clipper.cut_clip(
            source,
            offset=args.start - file_start,
            duration=duration,
            output=output,
            vertical=not args.no_vertical,
        )
    print(f"Clip prêt : {output} ({duration:.0f} s)")

    if not args.publish:
        print("(pas de --publish : rien n'a été envoyé sur TikTok)")
        return 0

    print("3/3 Publication sur TikTok…")
    publish_id = tiktok.upload_video(output, args.title, args.privacy)
    status = tiktok.wait_for_publish(publish_id)
    if status == "PUBLISH_COMPLETE":
        print("Publié sur TikTok ✔")
    else:
        print(
            f"Vidéo envoyée (publish_id={publish_id}), TikTok la traite encore ; "
            "vérifiez votre profil dans quelques minutes."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "auth":
            return cmd_auth()
        return cmd_clip(args)
    except (downloader.DownloadError, clipper.ClipError, tiktok.TikTokError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
