"""Streamlit dashboard for analyzing and saving customer feedback."""

import sqlite3
from pathlib import Path
import sys

import requests
import streamlit as st
from pydantic import ValidationError

# Keep this entry point runnable from a source checkout before installation.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from project_feedback_analyzer.analytics import calculate_summary
from project_feedback_analyzer.config import ConfigurationError, get_settings
from project_feedback_analyzer.database import init_db, load_history, save_results
from project_feedback_analyzer.models import Analysis

st.set_page_config(page_title="Customer Feedback Analyzer", page_icon="📝")


def analyze_review(review: str, api_url: str, timeout: float) -> dict:
    """Request one analysis from the FastAPI backend."""
    response = requests.post(api_url, json={"text": review}, timeout=timeout)
    response.raise_for_status()
    analysis = Analysis.model_validate(response.json())
    return {"review": review, **analysis.model_dump()}


def error_message(error: Exception) -> str:
    """Convert expected request failures into concise dashboard messages."""
    if isinstance(error, requests.Timeout):
        return "The analysis request timed out."
    if isinstance(error, requests.ConnectionError):
        return "Could not connect to the analysis API."
    if isinstance(error, requests.HTTPError):
        try:
            detail = error.response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        return detail or f"The analysis API returned HTTP {error.response.status_code}."
    if isinstance(error, (ValidationError, ValueError)):
        return "The analysis API returned an invalid response."
    return "An unexpected error occurred while analyzing this review."


try:
    settings = get_settings()
    init_db(settings.database_path)
except (ConfigurationError, sqlite3.Error, OSError) as exc:
    st.error(f"Application configuration error: {exc}")
    st.stop()


def analyze_or_error(review: str) -> dict:
    try:
        return analyze_review(review, settings.api_url, settings.http_timeout)
    except (requests.RequestException, ValidationError, ValueError) as exc:
        return {
            "review": review, "label": "error", "score": 0, "theme": "error",
            "error": error_message(exc),
        }


st.title("📝 Customer Feedback Analyzer")
st.write(
    "Turn customer reviews into structured sentiment, scores, and themes. "
    "Enter one review per line."
)

reviews_text = st.text_area("Reviews", height=200)

if st.button("Analyze", type="primary"):
    reviews = [line.strip() for line in reviews_text.splitlines() if line.strip()]

    if not reviews:
        st.warning("Please enter at least one review.")
    else:
        results = []
        with st.spinner("Analyzing reviews..."):
            for review in reviews:
                results.append(analyze_or_error(review))

        st.session_state.results = results

if "results" in st.session_state:
    results = st.session_state.results
    summary = calculate_summary(results)

    st.subheader("Results")
    st.dataframe(results, width="stretch")

    st.subheader("Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Submitted", summary.total)
    col2.metric("Succeeded", summary.succeeded)
    col3.metric("Failed", summary.failed)
    col4.metric(
        "Average score",
        summary.average_score if summary.average_score is not None else "N/A",
    )

    if summary.positive_percentage is not None:
        st.metric("Positive reviews", f"{summary.positive_percentage:.0f}%")
    if len(summary.top_themes) == 1:
        st.info(f"Customers talk most about: **{summary.top_themes[0]}**")
    elif summary.top_themes:
        st.info(f"Top themes: **{', '.join(summary.top_themes)}**")
    if summary.failed:
        st.warning(
            f"{summary.failed} review(s) failed and were excluded from all summary metrics."
        )

    if summary.failed and st.button("Retry failed reviews"):
        with st.spinner("Retrying failed reviews..."):
            st.session_state.results = [
                analyze_or_error(row["review"]) if row["label"] == "error" else row
                for row in results
            ]
        st.rerun()

    if st.button("💾 Save successful results"):
        try:
            saved_count = save_results(results, settings.database_path)
            if saved_count:
                st.success(
                    f"Saved {saved_count} successful review(s) to "
                    f"{settings.database_path}."
                )
            else:
                st.warning("There are no successful results to save.")
        except (sqlite3.Error, OSError) as exc:
            st.error(f"Could not save results: {exc}")

with st.expander("📚 Saved history"):
    try:
        history = load_history(settings.database_path)
        if history:
            st.write(f"Total saved reviews: {len(history)}")
            st.dataframe(
                [
                    {"review": row[0], "label": row[1], "score": row[2], "theme": row[3]}
                    for row in history
                ],
                width="stretch",
            )
        else:
            st.write("Nothing saved yet. Analyze reviews and save successful results.")
    except (sqlite3.Error, OSError) as exc:
        st.error(f"Could not load saved history: {exc}")
