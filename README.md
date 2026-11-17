# News Analyser

Objectif : scrapage de 8 sites d’actualité → MongoDB → classification de toxicité → API FastAPI → statistiques par source → Docker.

## Architecture (vue rapide)

```
scripts/collect.py  →  MongoDB (articles)
scripts/predict_all.py  →  MongoDB (predictions)
scripts/compute_stats.py  →  MongoDB (stats) + PNG
src/api (FastAPI /predict)  →  MongoDB (predictions)
```

| Couche | Rôle |
|--------|------|
| `src/scrapers/` | Collecte multi-sites (httpx / RSS / Playwright) |
| `src/db/` | Client Mongo + repositories |
| `src/ml/` | Wrapper toxicité Hugging Face |
| `src/api/` | `POST /predict` + Swagger |
| `src/analysis/` | % lightly / highly toxic par source + graphique |
| `scripts/` | Collecte, scoring batch, stats, smoke tests |
| `docker/` | Entrypoint + image API |

## Prérequis (local)

- Python 3.12+
- MongoDB local **ou** Docker
- (Scrapers difficiles) Playwright Chromium : `playwright install chromium`

```powershell
pip install -r requirements.txt
copy .env.example .env
```

## Lancer avec Docker (recommandé pour l’API)

```powershell
docker compose up --build
```

| Service | URL |
|---------|-----|
| Health | http://localhost:8000/health |
| Swagger | http://localhost:8000/docs |
| Mongo (hôte) | `mongodb://localhost:27018` |

Détails : [DOCKER.md](DOCKER.md).

## Pipeline local (données)

```powershell
# 1) Collecter les articles (défaut 30 / source)
python scripts/collect.py

# 2) Scorer toute la base → collection predictions
python scripts/predict_all.py

# 3) Stats % lightly / highly toxic + graphique
python scripts/compute_stats.py

# 4) API locale (sans Docker)
uvicorn src.api.main:app --reload --port 8000
```

Smoke toxicity (2 articles Mongo, sans écrire) :

```powershell
python scripts/test_toxicity.py
```

## Endpoint API

`POST /predict`

```json
{
  "text": "Texte à classer",
  "url": "https://...",
  "source": "lemonde"
}
```

Réponse : `prediction` (`toxic` / `non-toxic`), `score`, `toxicity_level`, `date`, id Mongo.

## Sites couverts

humanite, gamespot, marianne, lemonde, france24, france3, mediacites, lepoint.

## Documentation technique

Voir [TECHNICAL.md](TECHNICAL.md) : choix d’archi, scrapers, modèle ML, et **pourquoi les prédictions sur la presse sont quasi toutes non-toxiques**.
