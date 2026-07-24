"""Planification simple de la publication.

Le clip est fabriqué immédiatement (pour détecter tout de suite une erreur de
téléchargement/découpe) ; seule la publication attend l'heure demandée. Le
processus reste actif jusque-là — pour une planification qui survit à la
fermeture du terminal, voir la section cron du README.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

ACCEPTED_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%H:%M")


def parse_when(value: str, now: datetime | None = None) -> datetime:
    """Interprète '2026-07-25 18:00' ou '18:00' (aujourd'hui, sinon demain)."""
    now = now or datetime.now()
    value = value.strip()
    for fmt in ACCEPTED_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if fmt == "%H:%M":
            parsed = now.replace(
                hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0
            )
            if parsed <= now:
                parsed += timedelta(days=1)
        return parsed
    raise ValueError(
        f"Date/heure invalide : {value!r}. "
        "Utilisez 'AAAA-MM-JJ HH:MM' ou 'HH:MM'."
    )


def wait_until(target: datetime, tick: int = 30) -> None:
    """Bloque jusqu'à `target`, avec un affichage périodique du temps restant."""
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        if remaining > 90:
            mins = int(remaining // 60)
            print(f"  ⏳ Publication programmée dans ~{mins} min "
                  f"(à {target:%H:%M})…", flush=True)
        time.sleep(min(tick, max(1, remaining)))
