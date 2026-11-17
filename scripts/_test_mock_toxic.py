"""Quick check: new toxicity model on mock toxic + neutral French texts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from src.ml import ToxicityClassifier


MOCK_TOXIC_ARTICLE = {
    "title": "Opinion: ces journalistes sont tous des merdes inutiles",
    "content": (
        "Franchement allez tous vous faire foutre. Vous êtes des cons finis, "
        "des racistes de merde, et personne ne devrait vous lire. "
        "Sale bande d'idiots, crevez."
    ),
}

MOCK_NEUTRAL_ARTICLE = {
    "title": "La Bourse de Paris termine en légère hausse",
    "content": (
        "Le CAC 40 a terminé en hausse de 0,4 % ce mardi, porté par les valeurs "
        "bancaires et le pétrole. Les analystes restent prudents pour la suite."
    ),
}


def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    print("model:", settings.toxicity_model_name)
    clf = ToxicityClassifier(settings=settings)

    rows = []
    for name, art in (
        ("mock_toxic", MOCK_TOXIC_ARTICLE),
        ("mock_neutral", MOCK_NEUTRAL_ARTICLE),
    ):
        pred = clf.predict_article(title=art["title"], content=art["content"])
        row = {
            "name": name,
            "title": art["title"],
            "prediction": pred.prediction,
            "score": pred.score,
            "toxicity_level": pred.toxicity_level,
            "probabilities": pred.probabilities,
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=2))

    out = ROOT / "outputs_toxicity_mock_twitter.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
