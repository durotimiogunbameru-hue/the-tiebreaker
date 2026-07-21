"""
api/index.py — The Tiebreaker web application (FastAPI app + Vercel entry point).

This file is the ASGI entry point for both local uvicorn and Vercel. Vercel's
build statically inspects the entry file and requires a top-level `app` that is
a FastAPI instance, so the app is defined *here* directly (not re-exported from
another module).

Flow:
  frontend -> POST /api/analyze -> llm.analyze_decision (Claude or mock)
           -> analysis.compute_priority (weighted SWOT + priority list)
           -> structured JSON -> frontend renders matrices + rankings

The static single-page frontend lives in web/ (NOT public/, which Vercel
reserves for its own CDN). web/ is bundled with the function via
vercel.json's includeFiles, and this app's StaticFiles mount serves it in
both production and local dev.
"""

from __future__ import annotations

import os
import sys

# Vercel does not put a function's own directory on sys.path — add it so the
# sibling helper modules (_analysis, _llm, _prompts) resolve at runtime. Must
# run before importing them.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import _analysis as analysis
import _llm as llm

app = FastAPI(title="The Tiebreaker", version="1.0.0")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "web"


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #
class CriterionIn(BaseModel):
    name: str
    weight: float = Field(default=3.0, ge=0, le=5)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    options: list[str] = Field(..., min_length=2, max_length=6)
    criteria: Optional[list[CriterionIn]] = None

    @field_validator("options")
    @classmethod
    def _clean_options(cls, v: list[str]) -> list[str]:
        cleaned = [o.strip() for o in v if o and o.strip()]
        if len(cleaned) < 2:
            raise ValueError("Provide at least two distinct options.")
        if len(set(o.lower() for o in cleaned)) != len(cleaned):
            raise ValueError("Options must be distinct.")
        return cleaned


# Sensible default criteria so the app works even if the user adds none.
DEFAULT_CRITERIA = [
    analysis.Criterion("Overall upside", 4.0),
    analysis.Criterion("Cost / effort", 3.0),
    analysis.Criterion("Risk", 3.0),
    analysis.Criterion("Alignment with my goals", 4.0),
]


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "engine": "claude" if llm.has_api_key() else "mock"}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    # Resolve criteria: use the user's, or fall back to sensible defaults.
    if req.criteria:
        criteria = [
            analysis.Criterion(c.name, c.weight) for c in req.criteria if c.name
        ]
    else:
        criteria = []
    if not criteria:
        criteria = list(DEFAULT_CRITERIA)

    criteria_names = [c.name for c in criteria]

    # 1. Ask the model (or the mock) for the raw SWOT + per-criterion scores.
    try:
        raw, engine = llm.analyze_decision(req.question, req.options, criteria_names)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # network / API / parse failures
        raise HTTPException(
            status_code=502,
            detail=f"The analysis engine failed: {exc}",
        ) from exc

    # 2. Compute the weighted priority list from the raw scores.
    results, warnings = analysis.compute_priority(
        req.options, criteria, raw.get("swot", []), raw.get("scores", [])
    )
    weights = analysis.normalize_weights(criteria)

    # 3. Assemble the structured response the frontend renders.
    return {
        "engine": engine,
        "question": req.question,
        "criteria": [
            {"name": c.name, "weight": c.weight, "normalized": round(weights[c.name], 3)}
            for c in criteria
        ],
        "results": analysis.serialize(results, weights),
        "recommendation": raw.get("recommendation", {}),
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# Static frontend from web/ (bundled with the function). Mounted last so the
# /api/* routes take precedence over the catch-all static mount.
# --------------------------------------------------------------------------- #
@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
