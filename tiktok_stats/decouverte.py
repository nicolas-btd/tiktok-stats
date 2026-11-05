"""Mode découverte : capture toutes les réponses JSON d'une page analytics et liste les champs intéressants."""
import asyncio
import json
from datetime import datetime

from .config import Config
from .releve import STATS_URL, connecter

MOTS_CLES = ("watch", "retention", "finish", "play", "view", "duration", "comment", "share")


def chercher_champs(obj, chemin="", trouves=None):
    if trouves is None:
        trouves = []
    if isinstance(obj, dict):
        for cle, v in obj.items():
            p = f"{chemin}.{cle}" if chemin else cle
            if any(m in cle.lower() for m in MOTS_CLES):
                trouves.append((p, str(type(v).__name__ if isinstance(v, (dict, list)) else v)[:60]))
            chercher_champs(v, p, trouves)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):
            chercher_champs(v, f"{chemin}[{i}]", trouves)
    return trouves


async def principal(cfg: Config, ids):
    from playwright.async_api import async_playwright
    dossier = cfg.brutes / "decouverte"
    dossier.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        nav = await connecter(p, cfg)
        page = await nav.contexts[0].new_page()
        reponses = []

        async def on_response(resp):
            if "tiktok" not in resp.url or "json" not in resp.headers.get("content-type", ""):
                return
            try:
                reponses.append({"url": resp.url, "data": await resp.json()})
            except Exception:
                pass

        page.on("response", on_response)
        for vid in ids:
            reponses.clear()
            await page.goto(STATS_URL.format(vid), wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)
            f = dossier / f"{vid}_{datetime.now():%Y-%m-%d_%Hh%M}.json"
            f.write_text(json.dumps(reponses, ensure_ascii=False, indent=2))
            print(f"\n=== {vid} : {len(reponses)} réponses JSON → {f}")
            for r in reponses:
                champs = chercher_champs(r["data"])
                if champs:
                    print(f"  {r['url'].split('?')[0]}")
                    for chemin, ap in champs[:12]:
                        print(f"      {chemin} = {ap}")
            await page.wait_for_timeout(4000)
        await page.close()


def lancer(cfg: Config, ids):
    asyncio.run(principal(cfg, ids))
