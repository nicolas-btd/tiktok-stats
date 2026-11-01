"""Moteur de relevé : extraction des stats d'une vidéo via Chrome DevTools Protocol."""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

STATS_URL = "https://www.tiktok.com/tiktokstudio/analytics/{}"
INSIGHT = "/aweme/v2/data/insight/"


async def connecter(p, cdp_url="http://127.0.0.1:9222"):
    try:
        return await p.chromium.connect_over_cdp(cdp_url)
    except Exception:
        sys.exit(f"❌ Chrome ne répond pas sur {cdp_url}. Lancez Chrome avec le port 9222.")


def fusionner(reponses):
    fusion = {}
    for r in reponses:
        if INSIGHT not in r["url"] or not isinstance(r["data"], dict):
            continue
        for k, v in r["data"].items():
            if v is not None and k not in fusion:
                fusion[k] = v
    return fusion


def val(d, *chemin):
    for c in chemin:
        if not isinstance(d, dict):
            return None
        d = d.get(c)
    return d


def nb(x, dec=1):
    if x is None or x == "":
        return ""
    return f"{float(x):.{dec}f}".replace(".", ",")


def courbe_retention(d):
    """[(seconde, % de spectateurs restants)] triés par seconde."""
    ret = val(d, "video_retention_rate_realtime", "value") or {}
    pic = float(ret.get("peak_value") or 1000)
    courbe = []
    for p in sorted(ret.get("list") or [], key=lambda p: float(p.get("timestamp") or 0)):
        if p.get("value") is None:
            continue
        v = float(p["value"])
        courbe.append((round(float(p.get("timestamp") or 0) / 1000), v * 100 if v <= 1 else v * 100 / pic))
    return courbe


def extraire(vid, dossier, d, date_releve):
    info = d.get("video_info") or {}
    stats = info.get("statistics") or {}
    courbe = courbe_retention(d)
    par_seconde = dict(courbe)

    fin = val(d, "video_finish_rate_realtime", "value", "value")
    sources = val(d, "video_traffic_source_percent_realtime", "value", "value") or []
    create = info.get("create_time")
    duree = val(info, "video", "duration")

    ligne = {
        "date_releve": date_releve.strftime("%Y-%m-%d %H:%M"),
        "video_id": vid,
        "dossier": dossier or "",
        "publiee_le": datetime.fromtimestamp(int(create)).strftime("%Y-%m-%d %H:%M") if create else "",
        "legende": (info.get("desc") or "").replace("\n", " ")[:100],
        "duree_s": nb(duree / 1000 if duree else None),
        "vues": val(d, "realtime_total_video_views", "value", "value") or stats.get("play_count", ""),
        "retention_1s": nb(par_seconde.get(1), 0),
        "retention_3s": nb(par_seconde.get(3), 0),
        "retention_5s": nb(par_seconde.get(5), 0),
        "retention_10s": nb(par_seconde.get(10), 0),
        "temps_moyen_s": nb(val(d, "video_per_duration_realtime", "value", "value")),
        "vue_entiere_pct": nb(fin * 100 if fin is not None else None),
        "commentaires": stats.get("comment_count", ""),
        "partages": stats.get("share_count", ""),
        "nouveaux_abonnes": val(d, "realtime_new_followers", "value", "value") or "",
        "sources_trafic": " | ".join(
            f"{s.get('key')}={s.get('str_value') or s.get('value')}" for s in sources),
    }
    return ligne, courbe


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
                d = fusionner(reponses)
                if "video_retention_rate_realtime" in d and "video_info" in d:
                    return True
            if reponses:
                return False
        except Exception as e:
            print(f"   ⚠️ Tentative {tentative + 1}/{essais} pour {vid} : {e}")
            await page.wait_for_timeout(1500)
    return False
