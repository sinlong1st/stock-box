"""AI news sentiment labeling via the Claude API.

Reads recent headlines and returns exactly one label from the fixed enum
(schema.json > sentiment.labels). JSON-only output, one label per run.

STATUS: stub. Build order step 4 (TECH_STACK.md).
"""

from __future__ import annotations

MODEL = "claude-sonnet-4-6"  # always use this model, do not swap (TECH_STACK.md)


def label_sentiment(ticker: str, headlines: list[str]) -> str:
    """Return one sentiment label for the ticker's recent headlines.

    - Empty ``headlines`` -> skip the API call, return ``"neutral"`` (flag upstream).
    - ``max_tokens=50`` is enough for ``{"sentiment": "<label>"}``.
    - Wrap ``json.loads`` in try/except; fall back to ``"neutral"`` on parse failure.

    See the prompt template in schema.json > sentiment.ai_prompt_template and the
    reference call in TECH_STACK.md §02.
    """
    if not headlines:
        return "neutral"
    raise NotImplementedError("sentiment.label_sentiment is not implemented yet")
