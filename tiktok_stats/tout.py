"""Relevé de TOUT le compte :
1. lit la page Contenu de TikTok Studio (ID, légendes, visibilité) ;
2. associe chaque vidéo à un dossier local ;
3. relève les stats de chaque vidéo.
"""
import asyncio
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

from .releve import INSIGHT, capturer, connecter

CONTENU_URL = "https://www.tiktok.com/tiktokstudio/content"
RE_ID = re.compile(r"^\d{17,21}$")
RE_LIEN = re.compile(r"(?:/video/|/analytics/)(\d{17,21})")


def chercher_videos(obj, trouvees):
    if isinstance(obj, dict):
        vid = None
        for k in ("aweme_id", "item_id", "video_id", "id_str", "id"):
            v = obj.get(k)
            if v is not None and RE_ID.match(str(v)):
                vid = str(v)
                break
        if vid and obj.get("desc"):
            t = trouvees.setdefault(vid, {})
            t["legende"] = str(obj["desc"]).replace("\n", " ")
            if obj.get("create_time"):
                t["create_time"] = int(obj["create_time"])
            # visibility : 1 = public, 2 = « Moi uniquement », 3 = amis · status 140 = privé
            if obj.get("visibility") == 1:
                t["is_private"] = False
            elif obj.get("visibility") in (2, "2") or obj.get("status") == 140 or obj.get("is_private") is True:
                t["is_private"] = True
        for v in obj.values():
            chercher_videos(v, trouvees)
    elif isinstance(obj, list):
        for v in obj:
            chercher_videos(v, trouvees)


async def ouvrir_contenu(nav):
    existantes = [pg for pg in nav.contexts[0].pages if "tiktokstudio" in pg.url]
    page = existantes[0] if existantes else await nav.contexts[0].new_page()
    await page.bring_to_front()
    return page, bool(existantes)

JS_LIENS = """() => {
    const results = [];
    document.querySelectorAll("a[href]").forEach(a => {
        if (!/\\/video\\/|\\/analytics\\//.test(a.href)) return;
        let cur = a, isPrivate = null;
        for (let i = 0; i < 15; i++) {
            if (!cur.parentElement) break;
            cur = cur.parentElement;
            const m = cur.innerText.match(/Tout le monde|Moi uniquement|Amis|Privé|Everyone|Only me|Friends|Private/g);
            if (m && m.length === 1) { isPrivate = !/Tout le monde|Everyone/.test(m[0]); break; }
        }
        results.push({href: a.href, text: a.innerText, is_private: isPrivate});
    });
    return results;
}"""

import unicodedata

MOTS_VIDES = set("""pourquoi comment quoi quel quelle quels quelles est-ce que qui vous votre vos
nous notre les des une le la de du et en est sont pas plus tout toute toutes tous dans pour
avec sur ce cette ces certaines certains personnes toujours jamais etre avoir fait faire""".split())
EXTENSIONS = (".json", ".md", ".txt")


def mots(texte, ignores):
    t = unicodedata.normalize("NFD", texte.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [m for m in re.split(r"[^a-z]+", t) if len(m) >= 4 and m not in MOTS_VIDES and m not in ignores]


def mots_cles(legende, ignores):
    question = legende.split("?")[0] if "?" in legende else legende[:80]
    return set(mots(question, ignores)) or set(mots(legende, ignores))


def texte_dossier(dossier: Path, ignores):
    morceaux = []
    for f in dossier.rglob("*"):
        if (f.is_file() and f.suffix.lower() in EXTENSIONS and f.name != "stats.md"
                and f.stat().st_size < 500_000):
            try:
                morceaux.append(f.read_text(errors="ignore"))
            except Exception:
                pass
    return set(mots(" ".join(morceaux), ignores))


def dossiers_videos_liste(videos_dir: Path, marqueurs):
    if not videos_dir.exists():
        return []
    dossiers = [f for f in videos_dir.rglob("*")
                if f.is_dir() and not f.name.startswith((".", "_"))
                and any((f / m).exists() for m in marqueurs)]
    return dossiers or [d for d in videos_dir.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]


def associer_videos(videos_dir: Path, marqueurs, mots_ignores, seuil_association, trouvees, connus):
    ignores = {m.lower() for m in mots_ignores}
    textes = {d.relative_to(videos_dir).as_posix(): texte_dossier(d, ignores)
              for d in dossiers_videos_liste(videos_dir, marqueurs)}
    pris = {d for d in connus.values() if d}
    resultat, candidats = {}, []

    for vid, info in trouvees.items():
        if info.get("is_private"):
            continue
        if connus.get(vid):
            resultat[vid] = connus[vid]
            continue
        cles = mots_cles(info.get("legende", ""), ignores)
        for nom, t in textes.items():
            if cles and nom not in pris:
                candidats.append((len(cles & t) / len(cles), vid, nom))
    for score, vid, nom in sorted(candidats, reverse=True):
        if score >= seuil_association and vid not in resultat and nom not in pris:
            resultat[vid] = nom
            pris.add(nom)
    return resultat

def ecrire_videos_txt_fichier(videos_txt: Path, ordre, trouvees, connus, assoc):
    lignes = ["# ID de la vidéo        dossier       # légende",
              "# Généré par tiktok-stats — vous pouvez corriger un dossier à la main, il sera conservé."]
    for vid in ordre + [v for v in connus if v not in ordre]:
        if trouvees.get(vid, {}).get("is_private"):
            continue
        dossier = assoc.get(vid) or connus.get(vid) or ""
        leg = trouvees.get(vid, {}).get("legende", "")[:60].replace("#", "")
        lignes.append(f"{vid}  {dossier:<12}  # {leg}")
    videos_txt.parent.mkdir(parents=True, exist_ok=True)
    videos_txt.write_text("\n".join(lignes) + "\n", encoding="utf-8")
