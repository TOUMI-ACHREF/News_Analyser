# Docker — News Analyser

Stack: **FastAPI** (`api`) + **MongoDB 7** (`mongo`).

Works on another PC with only Docker Desktop: toxicity model is **baked into the image** at build time.

## Prerequisites

- Docker Desktop (Compose v2)

## Build & run

```powershell
docker compose up --build
```

First build is long (PyTorch CPU + Hugging Face model). Later starts are much faster.

## URLs

| Service | URL / connection |
|---------|------------------|
| API health | http://localhost:8000/health |
| Swagger | http://localhost:8000/docs |
| Mongo (from host) | `mongodb://localhost:27018` (db `news_analyser`) |

> Host port **27018** → container `27017`, so a local Mongo on `27017` does not conflict.

## Test `/predict`

```powershell
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d "{\"text\":\"Some text for testing\"}"
```

Or open http://localhost:8000/docs

## Useful commands

```powershell
docker compose down
docker compose down -v
docker compose logs -f api
docker compose ps
```

## Notes

- Inside Docker, the API uses `MONGO_URI=mongodb://mongo:27017` (Compose DNS).
- Host scripts (`collect.py`, `predict_all.py`) against this Compose Mongo:

```powershell
$env:MONGO_URI="mongodb://localhost:27018"
python scripts/collect.py
```
