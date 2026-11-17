"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000, description="Text to classify")
    url: Optional[str] = Field(default=None, max_length=2000, description="Optional article URL")
    source: Optional[str] = Field(default=None, max_length=100, description="Optional news source")

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            raise ValueError("text must not be blank")
        return cleaned


class PredictResponse(BaseModel):
    text: str
    prediction: Literal["toxic", "non-toxic"]
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence of the predicted label")
    toxicity_level: Literal["non-toxic", "lightly-toxic", "highly-toxic"]
    date: datetime
    url: Optional[str] = None
    source: Optional[str] = None
    id: Optional[str] = Field(default=None, description="MongoDB inserted document id")
