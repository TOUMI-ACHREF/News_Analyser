"""Toxicity classifier wrapper (label + confidence + toxicity level)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

PredictionLabel = Literal["toxic", "non-toxic"]
ToxicityLevel = Literal["non-toxic", "lightly-toxic", "highly-toxic"]


@dataclass(slots=True)
class ToxicityResult:
    """Structured output of one toxicity prediction."""

    text: str
    prediction: PredictionLabel
    score: float
    toxicity_level: ToxicityLevel
    probabilities: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "prediction": self.prediction,
            "score": self.score,
            "toxicity_level": self.toxicity_level,
            "probabilities": self.probabilities,
        }


class ToxicityClassifier:
    """
    Thin wrapper around textdetox/xlmr-base-toxicity-classifier.

    Labels (model): 0 = neutral, 1 = toxic.
    Brief labels: non-toxic / toxic + confidence score.
    Extra: toxicity_level for Part 3 stats (thresholds from settings).
    """

    def __init__(self, settings: Settings | None = None, device: str | None = None):
        self.settings = settings or get_settings()
        self.model_name = self.settings.toxicity_model_name
        self.max_length = self.settings.toxicity_max_length
        self.toxic_threshold = self.settings.toxicity_toxic_threshold
        self.highly_threshold = self.settings.toxicity_highly_threshold

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)

        logger.info("Loading toxicity model %s on %s…", self.model_name, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()
        logger.info("Toxicity model ready.")

    @staticmethod
    def build_text(title: str | None, content: str | None) -> str:
        """Concatenate title + content for scoring."""
        parts = [p.strip() for p in (title or "", content or "") if p and p.strip()]
        return "\n".join(parts).strip()

    def _level_from_toxic_prob(self, toxic_prob: float) -> ToxicityLevel:
        if toxic_prob < self.toxic_threshold:
            return "non-toxic"
        if toxic_prob < self.highly_threshold:
            return "lightly-toxic"
        return "highly-toxic"

    def predict(self, text: str) -> ToxicityResult:
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            raise ValueError("text must be non-empty")

        encoded = self.tokenizer(
            cleaned,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=False,
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.inference_mode():
            logits = self.model(**encoded).logits[0]
            probs = torch.softmax(logits, dim=-1)

        neutral_p = float(probs[0].item())
        toxic_p = float(probs[1].item())
        is_toxic = toxic_p >= self.toxic_threshold
        prediction: PredictionLabel = "toxic" if is_toxic else "non-toxic"
        # Confidence = probability of the chosen class.
        score = toxic_p if is_toxic else neutral_p

        return ToxicityResult(
            text=cleaned,
            prediction=prediction,
            score=round(score, 6),
            toxicity_level=self._level_from_toxic_prob(toxic_p),
            probabilities={
                "non-toxic": round(neutral_p, 6),
                "toxic": round(toxic_p, 6),
            },
        )

    def predict_article(self, *, title: str | None, content: str | None) -> ToxicityResult:
        return self.predict(self.build_text(title, content))


@lru_cache
def get_toxicity_classifier() -> ToxicityClassifier:
    """Process-wide singleton (model load is expensive)."""
    return ToxicityClassifier()
