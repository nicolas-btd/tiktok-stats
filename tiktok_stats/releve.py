"""Moteur de relevé : extraction des stats d'une vidéo, suivi.csv, vues_par_heure.csv, stats.md/.csv par dossier."""
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from .config import Config

STATS_URL = "https://www.tiktok.com/tiktokstudio/analytics/{}"
INSIGHT = "/aweme/v2/data/insight/"

COLONNES = [
    "date_releve", "video_id", "dossier", "publiee_le", "legende", "duree_s", "vues",
    "retention_1s", "retention_3s", "retention_5s", "retention_10s",
    "temps_moyen_s", "vue_entiere_pct", "commentaires", "partages",
    "nouveaux_abonnes", "sources_trafic",
]


def lire_videos(cfg: Config):
    """videos.txt : une vidéo par ligne → `ID [dossier]   # commentaire`."""
    videos = []
    if not cfg.videos_txt.exists():
        return videos
    for l in cfg.videos_txt.read_text(encoding="utf-8").splitlines():
        l = l.split("#")[0].strip()
        if not l:
            continue
        parts = l.split()
        videos.append((parts[0], parts[1] if len(parts) > 1 else None))
    return videos


async def connecter(p, cfg: Config):
    try:
        return await p.chromium.connect_over_cdp(cfg.cdp_url)
    except Exception:
        sys.exit(f"❌ Chrome ne répond pas sur {cfg.cdp_url}. Lancez d'abord : tiktok-stats chrome")


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


def maj_horaire(cfg: Config, heures):
    table = {}
    if cfg.horaire.exists():
        with cfg.horaire.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                table[(r["video_id"], r["heure"])] = r["vues"]
    for vid, heure, vues in heures:
        table[(vid, heure)] = vues
    with cfg.horaire.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["video_id", "heure", "vues"])
        for (vid, heure), vues in sorted(table.items()):
            w.writerow([vid, heure, vues])
    return table


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


def dossier_video(cfg: Config, dossier: str) -> Path | None:
    """Résout un nom de videos.txt : chemin relatif à videos_dir, sinon recherche par nom."""
    chemin = cfg.videos_dir / dossier
    if chemin.is_dir():
        return chemin
    trouve = sorted(p for p in cfg.videos_dir.rglob(Path(dossier).name) if p.is_dir())
    return trouve[0] if trouve else None


def traiter(cfg: Config, vid, dossier, reponses, date_releve):
    d = fusionner(reponses)
    if "video_retention_rate_realtime" not in d:
        print(f"⚠️ {vid} : stats introuvables (page pas chargée ou captcha ?)")
        return
    ligne, heures, courbe = extraire(vid, dossier, d, date_releve)
    ajouter_ligne(cfg.suivi, ligne)
    table = maj_horaire(cfg, heures)

    print(f"✅ {vid} | {ligne['vues']} vues | rét. 3 s {ligne['retention_3s'] or '?'} % "
          f"| moy. {ligne['temps_moyen_s']} s | entière {ligne['vue_entiere_pct']} % "
          f"| {ligne['commentaires']} comm. | {ligne['partages']} partages")
    print(f"   Légende : {ligne['legende'][:70]}")

    if not dossier:
        print("   ℹ️ Pas de dossier associé dans videos.txt → seulement suivi.csv")
        return
    chemin = dossier_video(cfg, dossier)
    if not chemin:
        print(f"   ⚠️ Dossier {dossier} introuvable dans {cfg.videos_dir} → seulement suivi.csv")
        return
    ajouter_ligne(chemin / "stats.csv", ligne)
    heures_vid = sorted((h, v) for (i, h), v in table.items() if i == vid)
    ecrire_resume(chemin, ligne, courbe, heures_vid)
    rel = chemin.relative_to(cfg.racine) if chemin.is_relative_to(cfg.racine) else chemin
    print(f"   📁 {rel}/stats.csv + stats.md")


def hors_ligne(cfg: Config, videos):
    for vid, dossier in videos:
        fichiers = sorted(cfg.brutes.glob(f"{vid}_*.json"), key=lambda f: f.stat().st_mtime)
        if not fichiers:
            print(f"⚠️ {vid} : aucun fichier dans {cfg.brutes}")
            continue
        f = fichiers[-1]
        traiter(cfg, vid, dossier, json.loads(f.read_text()), datetime.fromtimestamp(f.stat().st_mtime))


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


async def en_ligne(cfg: Config, videos):
    from playwright.async_api import async_playwright
    cfg.brutes.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        nav = await connecter(p, cfg)
        page = await nav.contexts[0].new_page()
        reponses = []

        async def on_response(resp):
            if INSIGHT not in resp.url:
                return
            try:
                reponses.append({"url": resp.url, "data": await resp.json()})
            except Exception:
                pass

        page.on("response", on_response)
        for vid, dossier in videos:
            await capturer(page, vid, reponses)
            await page.wait_for_timeout(1000)
            maintenant = datetime.now()
            if reponses:
                (cfg.brutes / f"{vid}_{maintenant:%Y-%m-%d_%Hh%M}.json").write_text(
                    json.dumps(reponses, ensure_ascii=False))
            traiter(cfg, vid, dossier, reponses, maintenant)
            await page.wait_for_timeout(3000)
        await page.close()


def lancer(cfg: Config, ids, hors_ligne_seul=False):
    videos = lire_videos(cfg)
    if ids:
        connus = dict(videos)
        videos = [(i, connus.get(i)) for i in ids]
    if not videos:
        sys.exit(f"Aucune vidéo : passez un ID en argument ou remplissez {cfg.videos_txt}")
    if hors_ligne_seul:
        hors_ligne(cfg, videos)
    else:
        asyncio.run(en_ligne(cfg, videos))
