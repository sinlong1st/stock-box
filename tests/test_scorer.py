import pytest

from stocksense import scorer


def test_score_price_low_and_high():
    assert scorer.score_price(0.0) == 100.0   # at the 52w low
    assert scorer.score_price(1.0) == 0.0      # at the 52w high
    assert scorer.score_price(0.25) == 75.0


def test_score_rsi_bands():
    assert scorer.score_rsi(30) == 100.0
    assert scorer.score_rsi(10) == 100.0       # <=30 clamps to 100
    assert scorer.score_rsi(70) == 0.0
    assert scorer.score_rsi(90) == 0.0         # >=70 clamps to 0
    assert scorer.score_rsi(50) == 50.0        # (70-50)/40*100


def test_score_news_mapping():
    assert scorer.score_news("very_positive") == 100.0
    assert scorer.score_news("neutral") == 50.0
    assert scorer.score_news("very_negative") == 0.0


def test_score_news_invalid_label_raises():
    with pytest.raises(ValueError):
        scorer.score_news("bullish")


def test_validate_weights_ok_within_tolerance():
    scorer.validate_weights({"price": 0.3, "rsi": 0.2, "news": 0.5})
    scorer.validate_weights({"price": 0.3, "rsi": 0.2, "news": 0.505})  # within 0.01


def test_validate_weights_bad_sum_raises():
    with pytest.raises(ValueError):
        scorer.validate_weights({"price": 0.5, "rsi": 0.2, "news": 0.5})


def test_validate_weights_missing_and_extra_keys():
    with pytest.raises(ValueError):
        scorer.validate_weights({"price": 0.5, "news": 0.5})
    with pytest.raises(ValueError):
        scorer.validate_weights({"price": 0.3, "rsi": 0.2, "news": 0.4, "vol": 0.1})


def test_composite_score_normal():
    technicals = {"position_in_range": 0.0, "rsi": 30}  # price=100, rsi=100
    weights = {"price": 0.3, "rsi": 0.2, "news": 0.5}
    result = scorer.composite_score(technicals, "neutral", weights)  # news=50
    # 100*0.3 + 100*0.2 + 50*0.5 = 75
    assert result["final_score"] == 75.0
    assert result["sub_scores"] == {"score_price": 100.0, "score_rsi": 100.0, "score_news": 50.0}
    assert result["flags"] == []


def test_composite_score_redistributes_when_rsi_missing():
    technicals = {"position_in_range": 0.0, "rsi": None}  # price=100
    weights = {"price": 0.3, "rsi": 0.2, "news": 0.5}
    result = scorer.composite_score(technicals, "neutral", weights)  # news=50
    # rsi weight folded into price: price 0.5, news 0.5 -> 100*0.5 + 50*0.5 = 75
    assert result["final_score"] == 75.0
    assert result["sub_scores"]["score_rsi"] is None
    assert result["weights_used"] == {"price": 0.5, "rsi": 0.0, "news": 0.5}
    assert "rsi_unavailable_weight_redistributed_to_price" in result["flags"]


def test_composite_score_rejects_bad_weights_before_compute():
    with pytest.raises(ValueError):
        scorer.composite_score({"position_in_range": 0.0, "rsi": 50}, "neutral",
                               {"price": 0.9, "rsi": 0.2, "news": 0.5})


@pytest.mark.parametrize(
    "score,expected",
    [
        (90, "Strong positive signal"),
        (75, "Strong positive signal"),
        (60, "Mild positive signal"),
        (50, "Neutral"),
        (54.5, "Neutral"),          # gap-safe fractional score
        (30, "Mild negative signal"),
        (10, "Strong negative signal"),
        (0, "Strong negative signal"),
    ],
)
def test_interpret_score(score, expected):
    assert scorer.interpret_score(score)["signal"] == expected
