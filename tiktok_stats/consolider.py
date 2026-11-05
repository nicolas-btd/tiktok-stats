"""Tableau global : dernier relevé de chaque vidéo de videos.txt → stats_completes.csv / .md"""
import csv
import json
from datetime import datetime
from pathlib import Path, PurePosixPath

from .releve import courbe_retention, fusionner, val

COLONNES = [
    "dossier", "video_id", "date_publication", "heure_publication", "sujet", "duree_s",
    "vues", "likes", "taux_likes_pct", "commentaires", "taux_commentaires_pct", "partages",
    "taux_partages_pct", "favoris", "nouveaux_abonnes", "taux_abonnes_pct", "retention_1s_pct",
    "retention_3s_pct", "retention_5s_pct", "retention_10s_pct", "temps_moyen_s",
    "ratio_temps_moyen_pct", "vue_entiere_pct", "pour_toi_pct", "legende",
]


def taux(x, vues):
    return round(x / vues * 100, 2) if vues else 0.0


def ligne_video_donnees(dossier_brutes: Path, vid, dossier, sujets_map=None):
    if sujets_map is None:
        sujets_map = {}
    fichiers = sorted(dossier_brutes.glob(f"{vid}_*.json"))
    if not fichiers:
        return None
    d = fusionner(json.loads(fichiers[-1].read_text()))
    if not d:
        return None
    info = d.get("video_info") or {}
    stats = info.get("statistics") or {}

    vues = int(val(d, "realtime_total_video_views", "value", "value") or stats.get("play_count") or 0)
    likes = int(stats.get("digg_count") or 0)
    commentaires = int(stats.get("comment_count") or 0)
    partages = int(stats.get("share_count") or 0)
    favoris = int(stats.get("collect_count") or 0)
    abos = int(val(d, "realtime_new_followers", "value", "value")
               or val(d, "video_new_followers", "value", "value") or 0)

    duree_ms = val(info, "video", "duration") or 0
    duree_s = round(duree_ms / 1000.0, 1) if duree_ms else 0.0
    create = int(info.get("create_time") or 0)
    dt = datetime.fromtimestamp(create) if create else None

    courbe = {s: round(v, 1) for s, v in courbe_retention(d)}
    tps = val(d, "video_per_duration_realtime", "value", "value")
    tps_moyen_s = round(float(tps), 1) if tps is not None else 0.0
    fin = val(d, "video_finish_rate_realtime", "value", "value")

    pour_toi = 0.0
    for s in val(d, "video_traffic_source_percent_realtime", "value", "value") or []:
        if s.get("key") in ("For You", "Pour toi", "FYP"):
            pour_toi = round(float(s.get("value", 0)) * 100, 1)
            break

    legende = (info.get("desc") or "").replace("\n", " ").strip()
    dossier = dossier or ""
    sujet = (sujets_map.get(dossier) or sujets_map.get(PurePosixPath(dossier).name)
             or legende[:50])

    return {
        "_tri": create,
        "dossier": dossier, "video_id": vid,
        "date_publication": dt.strftime("%d/%m/%Y") if dt else "",
        "heure_publication": dt.strftime("%Hh%M") if dt else "",
        "sujet": sujet, "duree_s": duree_s, "vues": vues,
        "likes": likes, "taux_likes_pct": taux(likes, vues),
        "commentaires": commentaires, "taux_commentaires_pct": taux(commentaires, vues),
        "partages": partages, "taux_partages_pct": taux(partages, vues),
        "favoris": favoris,
        "nouveaux_abonnes": abos, "taux_abonnes_pct": taux(abos, vues),
        "retention_1s_pct": courbe.get(1, 0.0), "retention_3s_pct": courbe.get(3, 0.0),
        "retention_5s_pct": courbe.get(5, 0.0), "retention_10s_pct": courbe.get(10, 0.0),
        "temps_moyen_s": tps_moyen_s,
        "ratio_temps_moyen_pct": round(tps_moyen_s / duree_s * 100, 1) if duree_s else 0.0,
        "vue_entiere_pct": round(float(fin) * 100, 1) if fin is not None else 0.0,
        "pour_toi_pct": pour_toi,
        "legende": legende,
    }
