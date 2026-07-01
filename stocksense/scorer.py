"""Weighted composite scoring logic.

Pure Python math — no external dependencies, fully unit-testable. All formulas,
thresholds, and enums are derived from ``specs/schema.json``.
"""

from __future__ import annotations

# schema.json > sentiment.labels — label -> numeric score (0-100).
SENTIMENT_SCORES: dict[str, float] = {
    "very_positive": 100.0,
    "positive": 75.0,
    "neutral": 50.0,
    "negative": 25.0,
    "very_negative": 0.0,
}

# schema.json > scoring.interpretation. Ordered high -> low so we can pick the
# first band whose minimum the score clears (gap-safe for fractional scores).
INTERPRETATION: list[dict] = [
    {"min": 75, "label": "Strong positive signal", "action": "Worth serious consideration"},
    {"min": 55, "label": "Mild positive signal", "action": "Monitor closely, seek confirmation"},
    {"min": 45, "label": "Neutral", "action": "No clear edge, wait"},
    {"min": 25, "label": "Mild negative signal", "action": "Caution, avoid new positions"},
    {"min": 0, "label": "Strong negative signal", "action": "High risk, stay out"},
]

# schema.json > scoring.composite.weight_validation
WEIGHT_KEYS = ("price", "rsi", "news")
WEIGHT_SUM_TARGET = 1.0
WEIGHT_TOLERANCE = 0.01


def score_price(position_in_range: float) -> float:
    """Higher score when price is closer to the 52-week low.

    schema.json > scoring.score_price: ``(1 - position_in_range) * 100``.
    """
    return _clamp((1.0 - position_in_range) * 100.0)


def score_rsi(rsi: float) -> float:
    """Higher score when RSI is lower (oversold), lower when overbought.

    schema.json > scoring.score_rsi.
    """
    if rsi <= 30:
        return 100.0
    if rsi >= 70:
        return 0.0
    return (70.0 - rsi) / 40.0 * 100.0


def score_news(sentiment_label: str) -> float:
    """Direct mapping from a sentiment label to its numeric score.

    schema.json > sentiment.labels.
    """
    try:
        return SENTIMENT_SCORES[sentiment_label]
    except KeyError:
        raise ValueError(
            f"Unknown sentiment label {sentiment_label!r}. "
            f"Expected one of: {', '.join(SENTIMENT_SCORES)}"
        ) from None


def validate_weights(weights: dict) -> None:
    """Validate a weight config. Raises ``ValueError`` if invalid.

    Weights must cover exactly {price, rsi, news} and sum to 1.0 within a
    tolerance of 0.01 (schema.json > scoring.composite.weight_validation).
    Must be called before computing a composite score.
    """
    missing = set(WEIGHT_KEYS) - set(weights)
    if missing:
        raise ValueError(f"Missing weight keys: {', '.join(sorted(missing))}")
    unexpected = set(weights) - set(WEIGHT_KEYS)
    if unexpected:
        raise ValueError(f"Unexpected weight keys: {', '.join(sorted(unexpected))}")

    total = sum(float(weights[k]) for k in WEIGHT_KEYS)
    if abs(total - WEIGHT_SUM_TARGET) > WEIGHT_TOLERANCE:
        raise ValueError(
            f"Weights must sum to {WEIGHT_SUM_TARGET} "
            f"(tolerance {WEIGHT_TOLERANCE}); got {total:.4f}"
        )


def composite_score(technicals: dict, sentiment_label: str, weights: dict) -> dict:
    """Compute the weighted composite score and its sub-scores.

    ``technicals`` must contain ``position_in_range`` and ``rsi`` (``rsi`` may be
    ``None`` when there was insufficient data to compute it — per
    SPEC.md §6 its weight is then redistributed to price).

    Returns a dict with ``sub_scores``, ``weights_used`` (effective weights after
    any redistribution), ``final_score``, and ``flags``.
    """
    validate_weights(weights)

    flags: list[str] = []
    effective = {k: float(weights[k]) for k in WEIGHT_KEYS}

    sp = score_price(technicals["position_in_range"])
    sn = score_news(sentiment_label)

    rsi = technicals.get("rsi")
    if rsi is None:
        # Skip RSI, fold its weight into price (SPEC.md §6).
        effective["price"] += effective["rsi"]
        effective["rsi"] = 0.0
        sr = None
        flags.append("rsi_unavailable_weight_redistributed_to_price")
    else:
        sr = score_rsi(float(rsi))

    final = sp * effective["price"] + sn * effective["news"]
    if sr is not None:
        final += sr * effective["rsi"]

    return {
        "sub_scores": {
            "score_price": round(sp, 2),
            "score_rsi": None if sr is None else round(sr, 2),
            "score_news": round(sn, 2),
        },
        "weights_used": {k: round(effective[k], 4) for k in WEIGHT_KEYS},
        "final_score": round(_clamp(final), 2),
        "flags": flags,
    }


def interpret_score(score: float) -> dict:
    """Map a final score (0-100) to its signal label and suggested action.

    schema.json > scoring.interpretation. Returns ``{"signal", "action"}``.
    """
    for band in INTERPRETATION:
        if score >= band["min"]:
            return {"signal": band["label"], "action": band["action"]}
    # score below 0 (shouldn't happen after clamping) -> weakest band.
    weakest = INTERPRETATION[-1]
    return {"signal": weakest["label"], "action": weakest["action"]}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))
