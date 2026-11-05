"""Configuration par projet : fichier tiktok-stats.toml."""
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


def initialiser(dossier: Path):
    f = dossier / NOM_FICHIER
    if f.exists():
        import sys
        sys.exit(f"⚠️ {f} existe déjà.")
    f.write_text(MODELE, encoding="utf-8")
    print(f"✅ {f} créé — ajustez videos_dir / data_dir puis lancez `tiktok-stats chrome`.")
