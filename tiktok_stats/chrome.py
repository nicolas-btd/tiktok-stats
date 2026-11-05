"""Lance Google Chrome avec le port de débogage (CDP) et un profil dédié."""
import platform
import shutil
import subprocess
import sys
import urllib.request

from .config import Config

CANDIDATS = {
    "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
               "/Applications/Chromium.app/Contents/MacOS/Chromium"],
    "Windows": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
}


def trouver_chrome():
    from pathlib import Path
    for c in CANDIDATS.get(platform.system(), []):
        if Path(c).exists():
            return c
    for nom in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        if p := shutil.which(nom):
            return p
    return None


def deja_lance(cfg: Config) -> bool:
    try:
        urllib.request.urlopen(cfg.cdp_url.rstrip("/") + "/json/version", timeout=2)
        return True
    except Exception:
        return False


def lancer(cfg: Config):
    if deja_lance(cfg):
        print(f"✅ Chrome répond déjà sur {cfg.cdp_url}")
        return
    exe = trouver_chrome()
    if not exe:
        sys.exit("❌ Google Chrome introuvable.")
    cfg.chrome_profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([exe, f"--remote-debugging-port={cfg.cdp_port}",
                      f"--user-data-dir={cfg.chrome_profile}",
                      "https://www.tiktok.com/tiktokstudio/content"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    print(f"🚀 Chrome lancé (port {cfg.cdp_port}, profil {cfg.chrome_profile}).")
    print("   Connectez-vous à TikTok Studio dans cette fenêtre si ce n'est pas déjà fait.")
