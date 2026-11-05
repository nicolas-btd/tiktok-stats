"""Relevé de TOUT le compte :
1. lit la page Contenu de TikTok Studio (ID, légendes, visibilité) ;
2. associe chaque vidéo publique à un dossier local d'après sa légende → videos.txt ;
3. relève les stats de chaque vidéo → <dossier>/stats.csv + stats.md, suivi.csv, vues_par_heure.csv.
"""
import asyncio
import json
import random
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from .config import Config
from .releve import INSIGHT, capturer, connecter, lire_videos, traiter

CONTENU_URL = "https://www.tiktok.com/tiktokstudio/content"
RE_ID = re.compile(r"^\d{17,21}$")
RE_LIEN = re.compile(r"(?:/video/|/analytics/)(\d{17,21})")
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


def dossiers_videos(cfg: Config):
    if not cfg.videos_dir.exists():
        return []
    dossiers = [f for f in cfg.videos_dir.rglob("*")
                if f.is_dir() and not f.name.startswith((".", "_"))
                and any((f / m).exists() for m in cfg.marqueurs)]
    return dossiers or [d for d in cfg.videos_dir.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]


def associer(cfg: Config, trouvees, connus):
    ignores = {m.lower() for m in cfg.mots_ignores}
    textes = {d.relative_to(cfg.videos_dir).as_posix(): texte_dossier(d, ignores) for d in dossiers_videos(cfg)}
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
        if score >= cfg.seuil_association and vid not in resultat and nom not in pris:
            resultat[vid] = nom
            pris.add(nom)
    return resultat


def ecrire_videos_txt(cfg: Config, ordre, trouvees, connus, assoc):
    lignes = ["# ID de la vidéo        dossier       # légende",
              "# Généré par tiktok-stats — vous pouvez corriger un dossier à la main, il sera conservé."]
    for vid in ordre + [v for v in connus if v not in ordre]:
        if trouvees.get(vid, {}).get("is_private"):
            continue
        dossier = assoc.get(vid) or connus.get(vid) or ""
        leg = trouvees.get(vid, {}).get("legende", "")[:60].replace("#", "")
        lignes.append(f"{vid}  {dossier:<12}  # {leg}")
    cfg.videos_txt.parent.mkdir(parents=True, exist_ok=True)
    cfg.videos_txt.write_text("\n".join(lignes) + "\n", encoding="utf-8")


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


async def ouvrir_contenu(nav):
    existantes = [pg for pg in nav.contexts[0].pages if "tiktokstudio" in pg.url]
    page = existantes[0] if existantes else await nav.contexts[0].new_page()
    await page.bring_to_front()
    return page, bool(existantes)


async def principal(cfg: Config, liste_seule: bool):
    from playwright.async_api import async_playwright
    cfg.brutes.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        nav = await connecter(p, cfg)
        page, deja_ouverte = await ouvrir_contenu(nav)
        lot = []

        async def on_response(resp):
            if "tiktok" not in resp.url or "json" not in resp.headers.get("content-type", ""):
                return
            try:
                lot.append({"url": resp.url, "data": await resp.json()})
            except Exception:
                pass

        page.on("response", on_response)
        print("🔎 Lecture de la page Contenu de TikTok Studio…")
        try:
            if deja_ouverte and "tiktokstudio/content" in page.url:
                await page.reload(wait_until="commit", timeout=30000)
            else:
                await page.goto(CONTENU_URL, wait_until="commit", timeout=45000)
        except Exception as e:
            print(f"⚠️ Chargement de la page Contenu : {e}")
        await page.wait_for_timeout(5000)
        try:
            await page.wait_for_selector("a[href*='/video/'], a[href*='/analytics/']", timeout=12000)
        except Exception:
            pass
        await page.mouse.move(700, 500)
        for _ in range(6):
            await page.mouse.wheel(0, 4000)
            await page.wait_for_timeout(1500)

        trouvees = {}
        for r in lot:
            chercher_videos(r["data"], trouvees)
        for item in await page.evaluate(JS_LIENS):
            m = RE_LIEN.search(item["href"])
            if not m:
                continue
            t = trouvees.setdefault(m.group(1), {})
            if not t.get("legende") and item.get("text"):
                t["legende"] = item["text"].replace("\n", " ").strip()
            if item.get("is_private") is not None and "is_private" not in t:
                t["is_private"] = item["is_private"]
        (cfg.brutes / f"_contenu_{datetime.now():%Y-%m-%d_%Hh%M}.json").write_text(
            json.dumps(lot, ensure_ascii=False))

        connus = dict(lire_videos(cfg))
        if not trouvees:
            if not connus:
                if not deja_ouverte:
                    await page.close()
                sys.exit("⚠️ Aucune vidéo trouvée sur la page Contenu (êtes-vous connecté à TikTok Studio ?).")
            print("⚠️ Page Contenu non détectée, reprise des vidéos connues depuis videos.txt…")
            for vid, dos in connus.items():
                trouvees[vid] = {"legende": dos or ""}

        ordre = sorted(trouvees, key=lambda v: trouvees[v].get("create_time", 0), reverse=True)
        assoc = associer(cfg, trouvees, connus)
        ecrire_videos_txt(cfg, ordre, trouvees, connus, assoc)
        publiques = [v for v in ordre if not trouvees[v].get("is_private")]
        n_privees = len(ordre) - len(publiques)

        print(f"\n📋 {len(publiques)} vidéos publiques trouvées"
              + (f" ({n_privees} privée(s) ignorée(s)) :" if n_privees else " :"))
        for vid in ordre:
            info = trouvees[vid]
            date = (datetime.fromtimestamp(info["create_time"]).strftime("%d/%m %Hh%M")
                    if info.get("create_time") else "?")
            etiquette = "🔒 PRIVÉE (ignorée)" if info.get("is_private") else (assoc.get(vid) or "❓ aucun dossier")
            print(f"   {date} | {etiquette:<18} | {info.get('legende', '(légende ?)')[:55]}")
        print(f"   → enregistré dans {cfg.videos_txt}\n")

        if not liste_seule:
            for vid in publiques:
                await capturer(page, vid, lot, attente=20)
                await page.wait_for_timeout(1000)
                maintenant = datetime.now()
                insight = [r for r in lot if INSIGHT in r["url"]]
                if insight:
                    (cfg.brutes / f"{vid}_{maintenant:%Y-%m-%d_%Hh%M}.json").write_text(
                        json.dumps(insight, ensure_ascii=False))
                    traiter(cfg, vid, assoc.get(vid), insight, maintenant)
                else:
                    print(f"   ⏭️ {vid} : stats non disponibles — ignorée.")
                await page.wait_for_timeout(random.randint(2500, 4500))
            print("\n✅ Relevé terminé.")

        if deja_ouverte:
            try:
                await page.goto(CONTENU_URL, wait_until="commit", timeout=20000)
            except Exception:
                pass
        else:
            await page.close()


def lancer(cfg: Config, liste_seule=False):
    asyncio.run(principal(cfg, liste_seule))
