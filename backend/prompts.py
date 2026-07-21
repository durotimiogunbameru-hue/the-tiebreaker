"""
prompts.py — Prompt-optimization layer for The Tiebreaker.

This module owns every piece of natural language that gets sent to the
underlying Large Language Model. Keeping prompt construction in one place is a
deliberate engineering choice: it lets us iterate on wording, tighten the
output contract, and keep the model's responses reliable and context-aware
without touching the API-calling or web-serving code.

The core idea: the model is never asked for prose. It is handed a strict JSON
schema and a system prompt that frames it as a neutral decision analyst, so the
qualitative choices a user types in come back as structured, comparable data.
"""

from __future__ import annotations

from typing import Any


# The system prompt is frozen and stable. It sits at the front of every request
# so that (a) the model's persona and output discipline never drift, and
# (b) it can be prompt-cached — see llm.py — to keep latency and cost down.
SYSTEM_PROMPT = """You are The Tiebreaker: a neutral, rigorous decision-support \
analyst. A person is torn between two or more options and needs structure, not \
a pep talk.

Your job is to turn their qualitative, subjective choices into an objective, \
data-driven comparison. You do this with two analytical frameworks:

1. A SWOT matrix (Strengths, Weaknesses, Opportunities, Threats) for EACH \
option. Strengths and Weaknesses are internal to the option; Opportunities and \
Threats are external factors the option is exposed to.

2. A multi-variable weighted priority list. For each decision criterion the \
user cares about, score every option from 0 (poor fit) to 10 (excellent fit). \
Be discriminating — do not give everything a 7. Meaningful differences between \
options are what make the analysis useful.

Rules:
- Be specific and concrete. "Good work-life balance" beats "it's nice".
- Stay balanced. Every option has real weaknesses; surface them honestly.
- Ground everything in what the user actually told you. Do not invent facts \
about named companies, people, or places. Reason from the decision itself.
- Never tell the user what they "should" feel. Report the structured findings \
and let the weighted math point to a recommendation."""


# The JSON Schema is the output contract. Structured Outputs on the Claude API
# validate the model's response against this shape, which is what makes the
# downstream analysis code safe to write — every field is guaranteed present.
def build_output_schema(option_names: list[str], criteria_names: list[str]) -> dict[str, Any]:
    """Construct the JSON schema the model must fill, given this decision's
    specific options and criteria. Building it dynamically (rather than a fixed
    schema) lets us name-check the model's output against exactly the options
    and criteria the user supplied."""

    swot_entry = {
        "type": "object",
        "properties": {
            "option": {"type": "string", "enum": option_names},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "weaknesses": {"type": "array", "items": {"type": "string"}},
            "opportunities": {"type": "array", "items": {"type": "string"}},
            "threats": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["option", "strengths", "weaknesses", "opportunities", "threats"],
        "additionalProperties": False,
    }

    score_entry = {
        "type": "object",
        "properties": {
            "option": {"type": "string", "enum": option_names},
            "criterion": {"type": "string", "enum": criteria_names},
            "score": {"type": "integer"},
            "reason": {"type": "string"},
        },
        "required": ["option", "criterion", "score", "reason"],
        "additionalProperties": False,
    }

    return {
        "type": "object",
        "properties": {
            "swot": {"type": "array", "items": swot_entry},
            "scores": {"type": "array", "items": score_entry},
            "recommendation": {
                "type": "object",
                "properties": {
                    "winner": {"type": "string", "enum": option_names},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "rationale": {"type": "string"},
                },
                "required": ["winner", "confidence", "rationale"],
                "additionalProperties": False,
            },
        },
        "required": ["swot", "scores", "recommendation"],
        "additionalProperties": False,
    }


def build_user_prompt(
    question: str,
    options: list[str],
    criteria: list[str],
) -> str:
    """Assemble the per-request user message. This is the volatile part of the
    prompt — it changes every request — so it goes last, after the cached
    system prompt, and it restates the exact options and criteria so the model
    stays anchored to this specific decision."""

    option_block = "\n".join(f"  - {opt}" for opt in options)
    criteria_block = "\n".join(f"  - {c}" for c in criteria)

    return f"""Here is the decision I'm stuck on:

DECISION
{question}

OPTIONS I'm choosing between:
{option_block}

CRITERIA that matter to me (score every option on each of these):
{criteria_block}

Produce:
1. A full SWOT matrix for every option listed above.
2. A score from 0-10 for every (option, criterion) pair, each with a one-line \
reason. Use the full range — reserve 8-10 for genuine strengths and 0-3 for \
genuine weaknesses.
3. A recommendation naming the single best option, a confidence level, and a \
short rationale that refers to the criteria that decided it.

Return only the structured data defined by the schema."""
