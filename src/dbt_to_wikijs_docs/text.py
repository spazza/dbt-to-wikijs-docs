# Copyright (c) 2026 spazza
"""Plain-text helpers shared by the dbt model and the renderers."""

from __future__ import annotations

import re

_SENTENCE = re.compile(r"(.+?[.!?])(\s|$)")


def collapse_whitespace(text: str | None) -> str:
    """Join lines and runs of spaces into single spaces."""
    return " ".join((text or "").split())


def first_sentence(text: str | None, limit: int = 250) -> str:
    """Return the first sentence of `text`, cut to `limit` characters."""
    text = collapse_whitespace(text)
    match = _SENTENCE.match(text)
    sentence = match.group(1) if match else text
    return sentence if len(sentence) <= limit else sentence[: limit - 1] + "…"
