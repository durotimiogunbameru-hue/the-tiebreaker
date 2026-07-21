"""
analysis.py — Analytical frameworks for The Tiebreaker.

The LLM produces raw, per-criterion scores and SWOT text. This module turns
that raw material into the decision-intelligence output: a multi-variable
weighted priority list. It is deliberately pure Python with no LLM or web
dependencies, so the scoring math is deterministic, testable, and auditable —
the numbers a user sees are computed here, not hallucinated by a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Criterion:
    """A single decision variable the user cares about, plus how much it
    matters. Weights are supplied on a 1-5 scale in the UI and normalized here
    so that the weighted totals are always on a comparable 0-10 footing
    regardless of how many criteria the user added."""

    name: str
    weight: float = 3.0


@dataclass
class OptionResult:
    """The fully-scored result for one option: its per-criterion scores, its
    weighted total, and its SWOT matrix."""

    name: str
    scores: dict[str, int] = field(default_factory=dict)          # criterion -> 0..10
    reasons: dict[str, str] = field(default_factory=dict)         # criterion -> why
    weighted_total: float = 0.0                                    # 0..10
    swot: dict[str, list[str]] = field(default_factory=dict)      # quadrant -> items


def normalize_weights(criteria: list[Criterion]) -> dict[str, float]:
    """Turn raw 1-5 importance weights into fractions that sum to 1.0.

    Normalizing means the weighted score stays on the same 0-10 scale as the
    individual scores, so a user can read a total of 7.4 the same way they read
    a single criterion score of 7.4 — no matter whether they entered three
    criteria or ten."""

    total = sum(max(c.weight, 0.0) for c in criteria)
    if total <= 0:
        # Degenerate case (all weights zero): fall back to equal weighting so
        # the app never divides by zero.
        n = len(criteria) or 1
        return {c.name: 1.0 / n for c in criteria}
    return {c.name: max(c.weight, 0.0) / total for c in criteria}


def compute_priority(
    options: list[str],
    criteria: list[Criterion],
    swot_rows: list[dict[str, Any]],
    score_rows: list[dict[str, Any]],
) -> tuple[list[OptionResult], list[str]]:
    """Combine the model's SWOT and per-criterion scores into ranked
    OptionResults.

    Returns the results sorted best-first, plus a list of human-readable
    warnings (e.g. a score the model left out, which we treat as a neutral 5).
    """

    warnings: list[str] = []
    weights = normalize_weights(criteria)

    # Index the model output for O(1) lookup.
    swot_by_option = {row["option"]: row for row in swot_rows}
    score_by_pair: dict[tuple[str, str], dict[str, Any]] = {
        (row["option"], row["criterion"]): row for row in score_rows
    }

    results: list[OptionResult] = []
    for opt in options:
        res = OptionResult(name=opt)

        # SWOT quadrants (default to empty lists if the model omitted one).
        swot = swot_by_option.get(opt, {})
        res.swot = {
            "strengths": list(swot.get("strengths", [])),
            "weaknesses": list(swot.get("weaknesses", [])),
            "opportunities": list(swot.get("opportunities", [])),
            "threats": list(swot.get("threats", [])),
        }

        # Weighted priority score.
        weighted = 0.0
        for crit in criteria:
            pair = score_by_pair.get((opt, crit.name))
            if pair is None:
                score = 5  # neutral fallback for a missing pair
                reason = "No score returned; treated as neutral."
                warnings.append(f'Missing score for "{opt}" on "{crit.name}" — used 5.')
            else:
                score = int(_clamp(pair.get("score", 5), 0, 10))
                reason = str(pair.get("reason", "")).strip()
            res.scores[crit.name] = score
            res.reasons[crit.name] = reason
            weighted += score * weights[crit.name]

        res.weighted_total = round(weighted, 2)
        results.append(res)

    # Rank best-first. Ties broken by the raw sum of scores, then name, so the
    # ordering is stable and reproducible.
    results.sort(
        key=lambda r: (r.weighted_total, sum(r.scores.values()), r.name),
        reverse=True,
    )
    return results, warnings


def _clamp(value: Any, low: int, high: int) -> int:
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return (low + high) // 2
    return max(low, min(high, v))


def serialize(results: list[OptionResult], weights: dict[str, float]) -> list[dict[str, Any]]:
    """Flatten OptionResults into plain dicts for the JSON API response."""
    return [
        {
            "name": r.name,
            "weighted_total": r.weighted_total,
            "scores": r.scores,
            "reasons": r.reasons,
            "swot": r.swot,
        }
        for r in results
    ]
