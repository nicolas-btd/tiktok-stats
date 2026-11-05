"""Affiche la structure des réponses insight d'un relevé brut (hors ligne)."""
import json
import sys
from pathlib import Path

from .config import Config
from .releve import INSIGHT


def apercu(v, profondeur=0):
    if profondeur > 3:
        return "…"
    if isinstance(v, dict):
        items = list(v.items())
        texte = ", ".join(f"{k}: {apercu(x, profondeur + 1)}" for k, x in items[:8])
        return "{" + texte + (", …" if len(items) > 8 else "") + "}"
    if isinstance(v, list):
        if not v:
            return "[]"
        return f"[{len(v)} éléments, ex. {apercu(v[0], profondeur + 1)} … dernier {apercu(v[-1], profondeur + 1)}]"
    return str(v)[:40]


def lancer(cfg: Config, fichier: str | None):
    if fichier:
        f = Path(fichier)
    else:
        fichiers = sorted((x for x in cfg.brutes.glob("*.json") if not x.name.startswith("_")),
                          key=lambda x: x.stat().st_mtime)
        if not fichiers:
            sys.exit(f"Aucun relevé brut dans {cfg.brutes}")
        f = fichiers[-1]
    print(f"Fichier : {f.name}\n")
    n = 0
    for r in json.loads(f.read_text()):
        if INSIGHT not in r["url"]:
            continue
        n += 1
        print(f"===== Réponse insight n°{n} =====")
        for cle, v in r["data"].items():
            if v is None or cle in ("video_info", "extra", "log_pb"):
                continue
            print(f"• {cle}\n    {apercu(v)[:400]}")
        print()
