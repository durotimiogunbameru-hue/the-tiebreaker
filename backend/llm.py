"""
llm.py — The bridge to the underlying Large Language Model.

This module isolates every LLM concern behind one function, `analyze_decision`.
Two things live here:

1. The real Claude integration. It sends the optimized prompt (from prompts.py)
   to the Anthropic API using Structured Outputs, so the model's reply is
   guaranteed to match our JSON schema. Prompt caching is used on the stable
   system prompt to keep repeat requests fast and cheap.

2. A deterministic mock analyst. When no API key is configured, the app still
   works end-to-end for portfolio viewers: the mock generates a stable,
   plausible SWOT-and-scores analysis from the input text alone. No network,
   no key, no surprises — the same input always yields the same output.

The rest of the app never imports `anthropic` or knows which path ran.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from prompts import SYSTEM_PROMPT, build_output_schema, build_user_prompt

# Default to the latest and most capable Claude model. Override with the
# CLAUDE_MODEL env var if you want to trade some quality for lower cost.
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")


def has_api_key() -> bool:
    """True when a real Anthropic key is available. The SDK also honors an
    `ant auth login` profile, but for a simple portfolio deploy we key off the
    env var so the mode is explicit and predictable."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def analyze_decision(
    question: str,
    options: list[str],
    criteria: list[str],
) -> tuple[dict[str, Any], str]:
    """Run one decision through the model (or the mock).

    Returns (raw_analysis, engine) where raw_analysis has keys `swot`,
    `scores`, and `recommendation`, and engine is "claude" or "mock" so the UI
    can be transparent about which produced the result.
    """
    if has_api_key():
        return _analyze_with_claude(question, options, criteria), "claude"
    return _analyze_with_mock(question, options, criteria), "mock"


# --------------------------------------------------------------------------- #
# Real model path
# --------------------------------------------------------------------------- #
def _analyze_with_claude(
    question: str,
    options: list[str],
    criteria: list[str],
) -> dict[str, Any]:
    import json

    import anthropic

    client = anthropic.Anthropic()
    schema = build_output_schema(options, criteria)

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        # Cache the frozen system prompt so repeat calls skip re-processing it.
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        # Structured Outputs: the reply is constrained to our schema, so the
        # downstream analysis code can trust every field is present.
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[
            {"role": "user", "content": build_user_prompt(question, options, criteria)}
        ],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(
            "The model declined to analyze this decision. Try rephrasing it."
        )

    # With output_config.format the first text block is guaranteed valid JSON.
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


# --------------------------------------------------------------------------- #
# Deterministic mock path (zero-setup demo mode)
# --------------------------------------------------------------------------- #
def _seed(*parts: str) -> int:
    """A stable integer derived from text, so the mock is fully reproducible."""
    h = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _score_for(option: str, criterion: str) -> int:
    """Deterministic pseudo-score in 0..10 for an (option, criterion) pair.
    Spread across the range so the weighted math produces meaningful spreads,
    not a wall of 5s."""
    return _seed(option.lower(), criterion.lower()) % 11


def _analyze_with_mock(
    question: str,
    options: list[str],
    criteria: list[str],
) -> dict[str, Any]:
    # Generic-but-plausible SWOT fragments, selected deterministically per
    # option so the demo reads like a real analysis.
    strengths_pool = [
        "Plays to your stated priorities better than the alternatives",
        "Lower switching cost from your current situation",
        "Momentum and familiarity are on its side",
        "Clear, near-term upside you can act on immediately",
    ]
    weaknesses_pool = [
        "Demands more of a resource you're already short on",
        "Harder to reverse if it turns out to be wrong",
        "Depends on factors partly outside your control",
        "Slower to show a payoff than you might like",
    ]
    opportunities_pool = [
        "Opens doors that compound over the next few years",
        "Positions you well if conditions shift in your favor",
        "Room to renegotiate or expand scope later",
        "Builds a skill or asset that transfers elsewhere",
    ]
    threats_pool = [
        "External conditions could erode the advantage",
        "A competing option may close this window",
        "Hidden costs tend to surface after commitment",
        "Your own priorities could change and strand you",
    ]

    def pick(pool: list[str], option: str, salt: str) -> list[str]:
        s = _seed(option.lower(), salt)
        # Choose 2 distinct items deterministically.
        i = s % len(pool)
        j = (s // len(pool) + 1) % len(pool)
        if j == i:
            j = (j + 1) % len(pool)
        return [pool[i], pool[j]]

    swot = [
        {
            "option": opt,
            "strengths": pick(strengths_pool, opt, "S"),
            "weaknesses": pick(weaknesses_pool, opt, "W"),
            "opportunities": pick(opportunities_pool, opt, "O"),
            "threats": pick(threats_pool, opt, "T"),
        }
        for opt in options
    ]

    scores = [
        {
            "option": opt,
            "criterion": crit,
            "score": _score_for(opt, crit),
            "reason": f'Deterministic demo estimate of how "{opt}" fits "{crit}".',
        }
        for opt in options
        for crit in criteria
    ]

    # Winner = highest simple average of scores (the weighted refinement happens
    # in analysis.py; here we just name a plausible leader for the rationale).
    def avg(opt: str) -> float:
        vals = [_score_for(opt, c) for c in criteria]
        return sum(vals) / len(vals) if vals else 0.0

    winner = max(options, key=avg)

    return {
        "swot": swot,
        "scores": scores,
        "recommendation": {
            "winner": winner,
            "confidence": "medium",
            "rationale": (
                f'In demo mode, "{winner}" comes out ahead on the balance of your '
                "criteria. Add an ANTHROPIC_API_KEY to get a real, reasoned analysis "
                "from Claude instead of this deterministic estimate."
            ),
        },
    }
