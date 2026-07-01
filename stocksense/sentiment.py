"""AI news sentiment labeling via the Claude API.

Reads recent headlines and returns exactly one label from the fixed enum
(schema.json > sentiment.labels). JSON-only output, one label per run.

Build order step 4 (TECH_STACK.md).
"""

from __future__ import annotations

import json
import re

import anthropic

from .scorer import SENTIMENT_SCORES

MODEL = "claude-sonnet-4-6"  # always use this model, do not swap (TECH_STACK.md)
MAX_TOKENS = 50
FALLBACK_LABEL = "neutral"

VALID_LABELS = frozenset(SENTIMENT_SCORES)  # single source of truth for the enum

_PROMPT_TEMPLATE = """You are a financial news sentiment classifier.
Given the following headlines for ticker {ticker}, assign exactly one label from:
very_positive, positive, neutral, negative, very_negative

Headlines:
{headlines}

Respond with JSON only: {{"sentiment": "<label>"}}"""


def label_sentiment(ticker: str, headlines: list[str]) -> str:
    """Return one sentiment label for the ticker's recent headlines.

    - Empty ``headlines`` -> skip the API call, return ``"neutral"``.
    - Any API error, JSON parse failure, or unknown label -> ``"neutral"``.

    The caller is responsible for flagging the empty/fallback case in the output.
    """
    if not headlines:
        return FALLBACK_LABEL

    prompt = _PROMPT_TEMPLATE.format(
        ticker=ticker,
        headlines="\n".join(f"- {h}" for h in headlines),
    )

    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        return _parse_label(raw)
    except Exception:
        # Network/auth/rate-limit/SDK errors all degrade gracefully to neutral.
        return FALLBACK_LABEL


def _parse_label(text: str) -> str:
    """Extract and validate the sentiment label from the model's raw output."""
    payload = _extract_json(text)
    try:
        label = json.loads(payload)["sentiment"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return FALLBACK_LABEL
    return label if label in VALID_LABELS else FALLBACK_LABEL


def _extract_json(text: str) -> str:
    """Best-effort pull of the first JSON object, tolerating markdown fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text
