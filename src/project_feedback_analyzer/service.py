"""Gemini integration for structured customer-review analysis."""

from google import genai
from google.genai import types
from pydantic import ValidationError

from project_feedback_analyzer.models import Analysis


class AnalysisProviderError(RuntimeError):
    """Raised when Gemini cannot provide a valid analysis."""


class GeminiAnalyzer:
    """Analyze customer reviews with Google Gemini."""

    def __init__(self, api_key: str, model: str) -> None:
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=12000,
                retry_options=types.HttpRetryOptions(
                    attempts=2, initial_delay=1, max_delay=1,
                    http_status_codes=[500, 502, 503, 504],
                ),
            ),
        )
        self.model = model

    def analyze(self, review_text: str) -> Analysis:
        """Return a validated sentiment, score, and theme for one review."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=(
                    "Analyze this customer review.\n"
                    "label must be 'positive', 'negative', or 'neutral'.\n"
                    "score must be a number from 1 (very bad) to 5 (very good).\n"
                    "theme must be ONE lowercase word for the main topic "
                    "(for example: delivery, taste, price, service, quality).\n"
                    f"Review: {review_text}"
                ),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Analysis,
                ),
            )
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code in {500, 502, 503, 504}:
                message = "The AI service is temporarily busy. Please retry this review shortly."
            elif code == 429:
                message = "The AI service reached its request limit. Please wait before retrying."
            else:
                message = "Gemini could not analyze the review. Please try again later."
            raise AnalysisProviderError(message) from exc

        if response.parsed is None:
            raise AnalysisProviderError("Gemini returned an empty response.")

        try:
            return Analysis.model_validate(response.parsed)
        except ValidationError as exc:
            raise AnalysisProviderError("Gemini returned an invalid response.") from exc
