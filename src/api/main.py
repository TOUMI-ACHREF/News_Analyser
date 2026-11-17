"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes.predict import router as predict_router
from src.db import close_client, ensure_indexes, ping
from src.ml import get_toxicity_classifier

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    # Entrypoint already waits for Mongo; ping again for clear startup logs.
    ping()
    ensure_indexes()
    # Warm the model once at startup so the first /predict is not cold.
    get_toxicity_classifier()
    logger.info("API ready")
    try:
        yield
    finally:
        close_client()


app = FastAPI(
    title="News Analyser API",
    description="Toxicity prediction for news texts (SMART CONSEIL).",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(predict_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
