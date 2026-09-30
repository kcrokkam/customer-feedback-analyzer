"""Environment-based application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_API_URL = "http://127.0.0.1:8000/analyze"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_DATABASE_PATH = Path("feedback.db")


class ConfigurationError(ValueError):
    """Raised when required application configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    gemini_api_key: str | None
    gemini_model: str
    api_url: str
    http_timeout: float
    database_path: Path


def get_settings() -> Settings:
    """Load settings from `.env` and the process environment."""
    load_dotenv()

    timeout_value = os.getenv("HTTP_TIMEOUT", str(DEFAULT_HTTP_TIMEOUT))
    try:
        http_timeout = float(timeout_value)
    except ValueError as exc:
        raise ConfigurationError("HTTP_TIMEOUT must be a number.") from exc

    if http_timeout <= 0:
        raise ConfigurationError("HTTP_TIMEOUT must be greater than zero.")

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    return Settings(
        gemini_api_key=api_key,
        gemini_model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        api_url=os.getenv("FASTAPI_URL", DEFAULT_API_URL),
        http_timeout=http_timeout,
        database_path=Path(os.getenv("DATABASE_PATH", str(DEFAULT_DATABASE_PATH))),
    )


def require_gemini_api_key(settings: Settings) -> str:
    """Return the configured API key or raise a user-friendly error."""
    if not settings.gemini_api_key:
        raise ConfigurationError(
            "Gemini API key is missing. Set GEMINI_API_KEY in your .env file."
        )
    return settings.gemini_api_key
