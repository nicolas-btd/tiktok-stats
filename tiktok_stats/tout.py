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
