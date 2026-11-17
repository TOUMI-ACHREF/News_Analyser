"""Central application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Ordered list of sources.
NEWS_SOURCES: list[dict[str, str]] = [
    {"name": "humanite", "base_url": "https://www.humanite.fr/"},
    {"name": "gamespot", "base_url": "https://www.gamespot.com/"},
    {"name": "marianne", "base_url": "https://www.marianne.net/"},
    {"name": "lemonde", "base_url": "https://www.lemonde.fr/"},
    {"name": "france24", "base_url": "https://www.france24.com/fr/"},
    {"name": "france3", "base_url": "https://france3-regions.francetvinfo.fr/"},
    {"name": "mediacites", "base_url": "https://www.mediacites.fr/"},
    {"name": "lepoint", "base_url": "https://www.lepoint.fr/"},
]


class Settings(BaseSettings):
    """Runtime configuration. Values come from env / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MongoDB
    mongo_uri: str = Field(default="mongodb://localhost:27017", alias="MONGO_URI")
    mongo_db: str = Field(default="news_analyser", alias="MONGO_DB")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Scraping
    scrape_timeout_seconds: int = Field(default=20, alias="SCRAPE_TIMEOUT_SECONDS")
    scrape_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        alias="SCRAPE_USER_AGENT",
    )
    max_articles_per_source: int = Field(default=30, alias="MAX_ARTICLES_PER_SOURCE")
    # Calendar days to walk backwards (monthly archives skip duplicate URLs).
    max_archive_days: int = Field(default=120, alias="MAX_ARCHIVE_DAYS")
    archive_empty_streak: int = Field(default=5, alias="ARCHIVE_EMPTY_STREAK")
    # Some sites need a visible Chromium window (anti-bot).
    scrape_headed: bool = Field(default=False, alias="SCRAPE_HEADED")

    # Toxicity ML
    toxicity_model_name: str = Field(
        default="textdetox/xlmr-base-toxicity-classifier",
        alias="TOXICITY_MODEL_NAME",
    )
    toxicity_max_length: int = Field(default=512, alias="TOXICITY_MAX_LENGTH")
    # toxic_prob < toxic_threshold → non-toxic
    # toxic_threshold ≤ p < highly_threshold → lightly-toxic
    # p ≥ highly_threshold → highly-toxic
    toxicity_toxic_threshold: float = Field(default=0.5, alias="TOXICITY_TOXIC_THRESHOLD")
    toxicity_highly_threshold: float = Field(default=0.8, alias="TOXICITY_HIGHLY_THRESHOLD")

    # Collection names
    articles_collection: str = "articles"
    predictions_collection: str = "predictions"
    stats_collection: str = "stats"

    @property
    def sources(self) -> list[dict[str, str]]:
        return NEWS_SOURCES


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton for app / scripts."""
    return Settings()
