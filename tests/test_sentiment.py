from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from stocksense import sentiment


def test_empty_headlines_returns_neutral_without_api_call():
    with patch("stocksense.sentiment.anthropic.Anthropic") as client:
        assert sentiment.label_sentiment("AAPL", []) == "neutral"
        client.assert_not_called()  # short-circuits before touching the API


def test_parse_label_plain_json():
    assert sentiment._parse_label('{"sentiment": "positive"}') == "positive"


def test_parse_label_tolerates_markdown_fences():
    raw = '```json\n{"sentiment": "very_negative"}\n```'
    assert sentiment._parse_label(raw) == "very_negative"


def test_parse_label_unknown_label_falls_back_to_neutral():
    assert sentiment._parse_label('{"sentiment": "bullish"}') == "neutral"


def test_parse_label_garbage_falls_back_to_neutral():
    assert sentiment._parse_label("not json at all") == "neutral"


def _fake_client_returning(text: str) -> MagicMock:
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text=text)]
    )
    return client


def test_label_sentiment_happy_path_with_mocked_api():
    fake = _fake_client_returning('{"sentiment": "positive"}')
    with patch("stocksense.sentiment.anthropic.Anthropic", return_value=fake):
        assert sentiment.label_sentiment("AAPL", ["Analyst upgrade"]) == "positive"


def test_label_sentiment_api_error_degrades_to_neutral():
    with patch("stocksense.sentiment.anthropic.Anthropic", side_effect=RuntimeError("boom")):
        assert sentiment.label_sentiment("AAPL", ["some headline"]) == "neutral"
