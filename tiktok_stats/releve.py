"""Moteur de relevé : extraction des stats d'une vidéo via Chrome DevTools Protocol."""
import asyncio
import json
import sys
from pathlib import Path

STATS_URL = "https://www.tiktok.com/tiktokstudio/analytics/{}"
INSIGHT = "/aweme/v2/data/insight/"


async def connecter(p, cdp_url="http://127.0.0.1:9222"):
    try:
        return await p.chromium.connect_over_cdp(cdp_url)
    except Exception:
        sys.exit(f"❌ Chrome ne répond pas sur {cdp_url}. Lancez Chrome avec le port 9222.")


async def capturer(page, vid, reponses, essais=2, attente=50):
    """Ouvre la page analytics d'une vidéo et attend les réponses insight. Renvoie True si complet."""
    for tentative in range(essais):
        reponses.clear()
        try:
            await page.goto(STATS_URL.format(vid), wait_until="commit", timeout=30000)
            for _ in range(attente):
                await page.wait_for_timeout(500)
                if "tiktokstudio/content" in page.url or "not-found" in page.url:
                    break
                if any(INSIGHT in r.get("url", "") for r in reponses):
                    return True
            if reponses:
                return False
        except Exception as e:
            print(f"   ⚠️ Tentative {tentative + 1}/{essais} pour {vid} : {e}")
            await page.wait_for_timeout(1500)
    return False
