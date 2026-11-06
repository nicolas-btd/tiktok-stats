"""Point d'entrée : tiktok-stats <commande>."""
import argparse
from pathlib import Path

from . import __version__
from . import config as config_mod


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="tiktok-stats",
        description="Relevé des statistiques TikTok Studio via une session Chrome (CDP). "
                    "La configuration est lue dans tiktok-stats.toml (dossier courant ou parents).")
    ap.add_argument("-c", "--config", help="chemin d'un tiktok-stats.toml précis")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="crée un tiktok-stats.toml dans le dossier courant")
    sub.add_parser("config", help="affiche la configuration résolue")
    sub.add_parser("chrome", help="lance Chrome avec le port de débogage et le profil configuré")
    p = sub.add_parser("tout", help="liste le compte, associe les vidéos aux dossiers, relève tout puis consolide")
    p.add_argument("--liste", action="store_true", help="liste + association seulement, sans relevé")
    p.add_argument("--sans-consolidation", action="store_true", help="ne pas régénérer stats_completes")
    p = sub.add_parser("releve", help="relève les vidéos de videos.txt (ou les ID donnés)")
    p.add_argument("ids", nargs="*")
    p.add_argument("--hors-ligne", action="store_true", help="relit les derniers JSON bruts, sans TikTok")
    sub.add_parser("consolider", help="régénère stats_completes.csv / .md depuis les relevés bruts")
    p = sub.add_parser("decouverte", help="capture toutes les réponses JSON d'une page analytics")
    p.add_argument("ids", nargs="*")
    p = sub.add_parser("explorer", help="affiche la structure d'un relevé brut (le plus récent par défaut)")
    p.add_argument("fichier", nargs="?")

    a = ap.parse_args(argv)

    if a.cmd == "init":
        return config_mod.initialiser(Path.cwd())

    cfg = config_mod.charger(a.config)

    if a.cmd == "config":
        print(f"Fichier          : {cfg.fichier or '(aucun — valeurs par défaut, dossier courant)'}")
        for nom in ("videos_dir", "data_dir", "consolidation_dir", "chrome_profile", "cdp_url",
                    "marqueurs", "mots_ignores", "seuil_association"):
            print(f"{nom:<17}: {getattr(cfg, nom)}")
        print(f"{'sujets':<17}: {len(cfg.sujets)} entrée(s)")
    elif a.cmd == "chrome":
        from . import chrome
        chrome.lancer(cfg)
    elif a.cmd == "tout":
        from . import consolider, tout
        tout.lancer(cfg, a.liste)
        if not a.liste and not a.sans_consolidation:
            consolider.lancer(cfg)
    elif a.cmd == "releve":
        from . import releve
        releve.lancer(cfg, a.ids, a.hors_ligne)
    elif a.cmd == "consolider":
        from . import consolider
        consolider.lancer(cfg)
    elif a.cmd == "decouverte":
        from . import decouverte
        from .releve import lire_videos
        ids = a.ids or [v for v, _ in lire_videos(cfg)]
        if not ids:
            raise SystemExit("Aucun ID : passez-en un en argument ou remplissez videos.txt")
        decouverte.lancer(cfg, ids)
    elif a.cmd == "explorer":
        from . import explorer
        explorer.lancer(cfg, a.fichier)


if __name__ == "__main__":
    main()
