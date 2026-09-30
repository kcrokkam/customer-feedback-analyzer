from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import requests
from streamlit.testing.v1 import AppTest


def response(data):
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: data)


def test_retry_only_processes_failed_reviews(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "feedback.db"))
    first = {"label": "positive", "score": 5, "theme": "delivery"}
    second = {"label": "negative", "score": 1, "theme": "service"}
    post = Mock(side_effect=[response(first), requests.Timeout(), response(second)])
    monkeypatch.setattr(requests, "post", post)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20).run()
    app.text_area[0].set_value("Fast delivery\nNo customer support")
    app.button[0].click().run()
    assert not app.exception
    assert [row["label"] for row in app.session_state["results"]] == ["positive", "error"]
    next(button for button in app.button if button.label == "Retry failed reviews").click().run()
    assert not app.exception
    assert [row["label"] for row in app.session_state["results"]] == ["positive", "negative"]
    assert post.call_count == 3
    assert post.call_args.kwargs["json"] == {"text": "No customer support"}
