"""POST /predict — toxicity classification + Mongo persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.api.schemas import PredictRequest, PredictResponse
from src.db import PredictionRepository
from src.ml import get_toxicity_classifier

router = APIRouter(tags=["toxicity"])


@router.post("/predict", response_model=PredictResponse, summary="Classify text toxicity")
def predict(body: PredictRequest) -> PredictResponse:
    try:
        result = get_toxicity_classifier().predict(body.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Model error: {exc}") from exc

    now = datetime.now(timezone.utc)
    repo = PredictionRepository()
    inserted = repo.create(
        text=result.text,
        prediction=result.prediction,
        score=result.score,
        url=body.url,
        source=body.source,
        date=now,
        toxicity_level=result.toxicity_level,
    )

    return PredictResponse(
        text=result.text,
        prediction=result.prediction,
        score=result.score,
        toxicity_level=result.toxicity_level,
        date=now,
        url=body.url,
        source=body.source,
        id=str(inserted.inserted_id),
    )
