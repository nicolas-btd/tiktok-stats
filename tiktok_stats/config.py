"""Configuration par projet : fichier tiktok-stats.toml cherché depuis le dossier courant vers le haut.

Tous les chemins relatifs du fichier sont résolus par rapport au dossier qui contient le .toml.
Sans fichier, l'outil travaille dans le dossier courant avec les valeurs par défaut.
"""
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

NOM_FICHIER = "tiktok-stats.toml"

MODELE = '''# Configuration de tiktok-stats pour ce projet
# Chemins relatifs à ce fichier.
videos_dir = "videos"            # dossiers vidéo locaux (reçoivent stats.md / stats.csv)
data_dir = "stats-tiktok"        # videos.txt, suivi.csv, vues_par_heure.csv, stats_brutes/
consolidation_dir = "."          # où écrire stats_completes.csv / .md

cdp_url = "http://127.0.0.1:9222"
chrome_profile = "~/.tiktok-stats/chrome-profile"   # profil Chrome connecté à TikTok Studio

# Fichiers qui signalent qu'un dossier est un dossier vidéo
marqueurs = ["script.txt", "stats.md", "voix.mp3", "timeline_raw.json"]
# Mots (hashtags récurrents…) ignorés lors de l'association légende → dossier
mots_ignores = []
seuil_association = 0.6
titre_consolidation = "Tableau statistique global des vidéos publiques"

# Titre lisible par dossier pour le tableau consolidé (sinon début de la légende)
[sujets]
# "ma-video-1" = "Sujet de la vidéo"
'''


@dataclass
class Config:
    racine: Path
    fichier: Path | None
    videos_dir: Path
    data_dir: Path
    consolidation_dir: Path
    cdp_url: str = "http://127.0.0.1:9222"
    chrome_profile: Path = field(default_factory=lambda: Path.home() / ".tiktok-stats" / "chrome-profile")
    marqueurs: list[str] = field(default_factory=lambda: ["script.txt", "stats.md", "voix.mp3", "timeline_raw.json"])
    mots_ignores: list[str] = field(default_factory=list)
    seuil_association: float = 0.6
    titre_consolidation: str = "Tableau statistique global des vidéos publiques"
    sujets: dict[str, str] = field(default_factory=dict)

    @property
    def brutes(self) -> Path:
        return self.data_dir / "stats_brutes"

    @property
    def videos_txt(self) -> Path:
        return self.data_dir / "videos.txt"

    @property
    def suivi(self) -> Path:
        return self.data_dir / "suivi.csv"

    @property
    def horaire(self) -> Path:
        return self.data_dir / "vues_par_heure.csv"

    @property
    def cdp_port(self) -> int:
        return urlparse(self.cdp_url).port or 9222


def trouver(depart: Path) -> Path | None:
    for d in [depart, *depart.parents]:
        if (d / NOM_FICHIER).is_file():
            return d / NOM_FICHIER
    return None


def charger(chemin: str | None = None) -> Config:
    if chemin:
        fichier = Path(chemin).expanduser().resolve()
        if not fichier.is_file():
            sys.exit(f"❌ Fichier de configuration introuvable : {fichier}")
    else:
        fichier = trouver(Path.cwd().resolve())

    brut = tomllib.loads(fichier.read_text(encoding="utf-8")) if fichier else {}
    racine = fichier.parent if fichier else Path.cwd().resolve()

    def chemin_de(cle, defaut):
        p = Path(str(brut.get(cle, defaut))).expanduser()
        return p if p.is_absolute() else (racine / p).resolve()

    cfg = Config(
        racine=racine,
        fichier=fichier,
        videos_dir=chemin_de("videos_dir", "videos"),
        data_dir=chemin_de("data_dir", "stats-tiktok"),
        consolidation_dir=chemin_de("consolidation_dir", "."),
    )
    if "chrome_profile" in brut:
        cfg.chrome_profile = chemin_de("chrome_profile", "")
    for cle in ("cdp_url", "marqueurs", "mots_ignores", "seuil_association", "titre_consolidation", "sujets"):
        if cle in brut:
            setattr(cfg, cle, brut[cle])
    return cfg


def initialiser(dossier: Path):
    f = dossier / NOM_FICHIER
    if f.exists():
        sys.exit(f"⚠️ {f} existe déjà.")
    f.write_text(MODELE, encoding="utf-8")
    print(f"✅ {f} créé — ajustez videos_dir / data_dir puis lancez `tiktok-stats chrome`.")
