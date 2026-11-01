"""Lance Google Chrome avec le port de débogage (CDP) et un profil dédié."""
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

CANDIDATS = {
    "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
               "/Applications/Chromium.app/Contents/MacOS/Chromium"],
    "Windows": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
}

DEFAULT_CDP_URL = "http://127.0.0.1:9222"
DEFAULT_PROFILE = Path.home() / ".tiktok-stats" / "chrome-profile"


def trouver_chrome():
    for c in CANDIDATS.get(platform.system(), []):
        if Path(c).exists():
            return c
    for nom in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        if p := shutil.which(nom):
            return p
    return None


def deja_lance(cdp_url: str = DEFAULT_CDP_URL) -> bool:
    try:
        urllib.request.urlopen(cdp_url.rstrip("/") + "/json/version", timeout=2)
        return True
    except Exception:
        return False


def lancer(cdp_url: str = DEFAULT_CDP_URL, profile_dir: Path = DEFAULT_PROFILE):
    if deja_lance(cdp_url):
        print(f"✅ Chrome répond déjà sur {cdp_url}")
        return
    exe = trouver_chrome()
    if not exe:
        sys.exit("❌ Google Chrome introuvable.")
    profile_dir.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([exe, "--remote-debugging-port=9222",
                      f"--user-data-dir={profile_dir}",
                      "https://www.tiktok.com/tiktokstudio/content"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    print(f"🚀 Chrome lancé (port 9222, profil {profile_dir}).")
    print("   Connectez-vous à TikTok Studio dans cette fenêtre si ce n'est pas déjà fait.")
