# 📊 tiktok-stats

Relevé automatique des statistiques **TikTok Studio** (vues, rétention seconde par seconde, temps moyen, taux de complétion, sources de trafic, abonnés gagnés), sans API officielle : l'outil se branche sur une session Chrome déjà connectée à TikTok Studio via le protocole DevTools (CDP) et lit les réponses `insight` des pages analytics.

L'outil est **indépendant des projets** : on l'installe une fois, et chaque projet a son propre fichier `tiktok-stats.toml`.

## Installation (une fois)

```bash
pipx install -e ~/Documents/Projets/tiktok-stats
```

`-e` (mode éditable) : toute modification du code ici est prise en compte immédiatement. Pas besoin de `playwright install` : l'outil pilote votre Chrome, il ne télécharge pas de navigateur.

## Utiliser dans un projet

```bash
cd ~/mon-projet
tiktok-stats init        # crée tiktok-stats.toml (à ajuster)
tiktok-stats chrome      # ouvre Chrome avec le port 9222 → connectez-vous à TikTok Studio
tiktok-stats tout        # relève tout le compte puis consolide
```

La configuration est cherchée dans le dossier courant puis ses parents : on peut lancer la commande depuis n'importe quel sous-dossier du projet. `-c chemin/vers/tiktok-stats.toml` force un fichier précis.

## Commandes

| Commande | Rôle |
|---|---|
| `init` | Crée un `tiktok-stats.toml` modèle dans le dossier courant. |
| `config` | Affiche la configuration résolue (chemins absolus). |
| `chrome` | Lance Chrome avec le port de débogage et le profil configurés (ne fait rien s'il répond déjà). |
| `tout [--liste] [--sans-consolidation]` | Lit la page Contenu, associe chaque vidéo publique à un dossier local d'après sa légende (→ `videos.txt`), relève chaque vidéo, puis régénère le tableau consolidé. `--liste` : association seulement. |
| `releve [ID…] [--hors-ligne]` | Relève les vidéos de `videos.txt` ou les ID donnés. `--hors-ligne` relit les derniers JSON bruts sans contacter TikTok. |
| `consolider` | Régénère `stats_completes.csv` / `.md` (dernier relevé de chaque vidéo). |
| `decouverte [ID…]` | Capture toutes les réponses JSON d'une page analytics et liste les champs utiles (quand TikTok change son API). |
| `explorer [fichier]` | Affiche la structure d'un relevé brut (le plus récent par défaut). |

## Configuration (`tiktok-stats.toml`)

Chemins relatifs au dossier du fichier.

| Clé | Défaut | Rôle |
|---|---|---|
| `videos_dir` | `videos` | Dossiers vidéo locaux ; chacun reçoit `stats.md` et `stats.csv`. |
| `data_dir` | `stats-tiktok` | `videos.txt`, `suivi.csv`, `vues_par_heure.csv`, `stats_brutes/`. |
| `consolidation_dir` | `.` | Où écrire `stats_completes.csv` / `.md`. |
| `cdp_url` | `http://127.0.0.1:9222` | Adresse DevTools de Chrome. |
| `chrome_profile` | `~/.tiktok-stats/chrome-profile` | Profil Chrome (gardez-le pour rester connecté). |
| `marqueurs` | `script.txt`, `stats.md`, `voix.mp3`, `timeline_raw.json` | Fichiers qui identifient un dossier vidéo. |
| `mots_ignores` | `[]` | Mots (hashtags récurrents…) ignorés pour l'association légende → dossier. |
| `seuil_association` | `0.6` | Part minimale des mots-clés de la légende retrouvés dans le dossier. |
| `titre_consolidation` | — | Titre du tableau `stats_completes.md`. |
| `[sujets]` | — | `"dossier" = "Sujet lisible"` pour le tableau consolidé. |

## `videos.txt`

Généré par `tout`, modifiable à la main (une correction est conservée aux relevés suivants) :

```text
# ID de la vidéo        dossier       # légende
7704754452598623521  motion/kola  # Un trou de 23 cm de large…
```

Le dossier est un chemin relatif à `videos_dir` ; un simple nom (`stickman5`) est aussi retrouvé dans les sous-dossiers.

## Fichiers produits

- `<videos_dir>/<dossier>/stats.md` : tableau de bord (résumé, rétention, vues par heure, historique, sources de trafic).
- `<videos_dir>/<dossier>/stats.csv` : historique des relevés de la vidéo.
- `<data_dir>/suivi.csv` : tous les relevés de toutes les vidéos.
- `<data_dir>/vues_par_heure.csv` : vues heure par heure.
- `<data_dir>/stats_brutes/` : JSON bruts archivés (rejouables avec `--hors-ligne`).
- `<consolidation_dir>/stats_completes.csv` / `.md` : une ligne par vidéo publique (taux d'engagement, rétention 1/3/5/10 s, % Pour toi…).
