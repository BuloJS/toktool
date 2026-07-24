"""Interface en ligne de commande de toktool.

Usage typique :
    toktool auth
    toktool suggest "https://youtu.be/XXXX"
    toktool clip "https://youtu.be/XXXX" --start 12:30 --duration 45 \
        --title "Mon clip" --publish
    toktool clip "https://youtu.be/XXXX" --start 12:30 --auto-title \
        --publish --at "2026-07-25 18:00"
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

from . import MAX_CLIP_SECONDS, clipper, downloader, scheduler, suggest, tiktok

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

    sugg = sub.add_parser(
        "suggest", help="Proposer titres et hashtags pour une vidéo YouTube."
    )
    sugg.add_argument("url", help="URL de la vidéo YouTube.")

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
        help="Légende/titre TikTok (hashtags inclus). Voir aussi --auto-title.",
    )
    clip.add_argument(
        "--auto-title", action="store_true",
        help="Générer automatiquement titre + hashtags depuis la vidéo YouTube.",
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
        "--at", metavar="QUAND",
        help="Programmer la publication ('AAAA-MM-JJ HH:MM' ou 'HH:MM'). "
        "Le clip est créé tout de suite, la publication attend l'heure dite.",
    )
    clip.add_argument(
        "--privacy",
        default="SELF_ONLY",
        choices=["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
        help="Visibilité TikTok (SELF_ONLY = privé/test, par défaut ; les apps "
        "non auditées par TikTok ne peuvent publier qu'en SELF_ONLY).",
    )
    return parser


def cmd_auth() -> int:
    tiktok.authorize()
    print("Compte TikTok connecté, jetons enregistrés dans ~/.toktool/.")
    return 0


def _print_suggestions(s: suggest.Suggestions) -> None:
    print(f"Vidéo : {s.source_title or '(titre inconnu)'}")
    if s.channel:
        print(f"Chaîne : {s.channel}" + (f"  ·  {s.category}" if s.category else ""))
    print("\nTitres proposés :")
    for i, title in enumerate(s.titles, 1):
        print(f"  {i}. {title}")
    print("\nHashtags proposés :")
    print("  " + " ".join("#" + h for h in s.hashtags))
    print("\nLégende prête à l'emploi (titre 1 + hashtags) :")
    print("  " + s.caption(0).replace("\n", "\n  "))


def cmd_suggest(args: argparse.Namespace) -> int:
    downloader.check_dependencies()
    _print_suggestions(suggest.suggest(args.url))
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

    when = None
    if args.at:
        try:
            when = scheduler.parse_when(args.at)
        except ValueError as exc:
            print(f"Erreur : {exc}", file=sys.stderr)
            return 1

    downloader.check_dependencies()
    output = args.output or Path(f"clip_{int(args.start)}s.mp4")

    # Titre : explicite, ou généré si --auto-title (ou si publication sans titre).
    title = args.title
    if not title and (args.auto_title or args.publish):
        try:
            suggestions = suggest.suggest(args.url)
            title = suggestions.caption(0)
            print("Titre généré automatiquement :")
            print("  " + title.replace("\n", "\n  "))
        except (RuntimeError, ValueError) as exc:
            print(f"(suggestions indisponibles : {exc})", file=sys.stderr)

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

    if when is not None:
        print(f"Publication programmée pour le {when:%Y-%m-%d à %H:%M}.")
        scheduler.wait_until(when)

    label = "privé (SELF_ONLY, visible par vous seul)" \
        if args.privacy == "SELF_ONLY" else args.privacy
    print(f"3/3 Publication sur TikTok — visibilité : {label}…")
    publish_id = tiktok.upload_video(output, title, args.privacy)
    status = tiktok.wait_for_publish(publish_id)
    if status == "PUBLISH_COMPLETE":
        print("Publié sur TikTok ✔")
        if args.privacy == "SELF_ONLY":
            print("→ Vidéo en privé sur votre compte : ouvrez l'app TikTok pour "
                  "la vérifier, puis passez-la en public si elle vous convient.")
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
        if args.command == "suggest":
            return cmd_suggest(args)
        return cmd_clip(args)
    except (downloader.DownloadError, clipper.ClipError, tiktok.TikTokError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
