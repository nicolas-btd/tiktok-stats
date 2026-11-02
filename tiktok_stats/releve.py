"""Moteur de relevé : extraction des stats d'une vidéo via Chrome DevTools Protocol."""
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

STATS_URL = "https://www.tiktok.com/tiktokstudio/analytics/{}"
INSIGHT = "/aweme/v2/data/insight/"

COLONNES = [
    "date_releve", "video_id", "dossier", "publiee_le", "legende", "duree_s", "vues",
    "retention_1s", "retention_3s", "retention_5s", "retention_10s",
    "temps_moyen_s", "vue_entiere_pct", "commentaires", "partages",
    "nouveaux_abonnes", "sources_trafic",
]


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
    heures = [
        (vid, datetime.fromtimestamp(int(p["key"])).strftime("%Y-%m-%d %H:00"), p.get("value", 0))
        for p in (val(d, "realtime_video_view_history", "list") or []) if p.get("key")
    ]
    return ligne, heures, courbe


def ajouter_ligne(chemin: Path, ligne):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not chemin.exists()
    with chemin.open("a", newline="", encoding="utf-8-sig" if nouveau else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";")
        if nouveau:
            w.writeheader()
        w.writerow(ligne)


def maj_horaire(chemin_horaire: Path, heures):
    table = {}
    if chemin_horaire.exists():
        with chemin_horaire.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                table[(r["video_id"], r["heure"])] = r["vues"]
    for vid, heure, vues in heures:
        table[(vid, heure)] = vues
    with chemin_horaire.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["video_id", "heure", "vues"])
        for (vid, heure), vues in sorted(table.items()):
            w.writerow([vid, heure, vues])
    return table


async def capturer(page, vid, reponses, essais=2, attente=50):
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


def ecrire_resume(dossier: Path, ligne, courbe, heures):
    leg = ligne["legende"]
    titre = leg.split("?")[0] + " ?" if "?" in leg else leg[:60]
    L = [f"# 📊 {titre}\n",
         f"Dernier relevé : **{ligne['date_releve']}** · publiée le {ligne['publiee_le']} "
         f"· durée {ligne['duree_s']} s · ID {ligne['video_id']}\n",
         "| Vues | Rét. 1 s | Rét. 3 s | Rét. 10 s | Temps moyen | Vue entière | Comm. | Partages | Abonnés |",
         "|---|---|---|---|---|---|---|---|---|",
         f"| {ligne['vues']} | {ligne['retention_1s']} % | {ligne['retention_3s']} % | "
         f"{ligne['retention_10s']} % | {ligne['temps_moyen_s']} s | {ligne['vue_entiere_pct']} % | "
         f"{ligne['commentaires']} | {ligne['partages']} | {ligne['nouveaux_abonnes'] or 0} |",
         "\n## Rétention\n", "| Seconde | Spectateurs restants |", "|---|---|"]
    for s, v in courbe:
        if s <= 10 or s % 5 == 0 or s == courbe[-1][0]:
            L.append(f"| {s} s | {v:.0f} % |")

    L += ["\n## Vues par heure\n", "| Heure | Vues |", "|---|---|"]
    L += [f"| {h} | {v} |" for h, v in heures]

    L += ["\n## Historique des relevés\n",
          "| Relevé | Vues | Rét. 3 s | Temps moyen | Vue entière | Comm. | Partages |",
          "|---|---|---|---|---|---|---|"]
    if (dossier / "stats.csv").exists():
        with (dossier / "stats.csv").open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                L.append(f"| {r['date_releve']} | {r['vues']} | {r['retention_3s']} % | "
                         f"{r['temps_moyen_s']} s | {r['vue_entiere_pct']} % | "
                         f"{r['commentaires']} | {r['partages']} |")

    if ligne["sources_trafic"]:
        L.append("\n## Sources de trafic\n")
        L += [f"- {s}" for s in ligne["sources_trafic"].split(" | ")]

    L.append(f"\n**Légende publiée :** {leg}")
    (dossier / "stats.md").write_text("\n".join(L) + "\n", encoding="utf-8")
