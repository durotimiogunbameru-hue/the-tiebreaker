"""
api/index.py — Vercel serverless entry point (also the local uvicorn target).

Vercel serves the ASGI `app` exported here for every /api/* request (see
vercel.json). If importing the real application fails for any reason, we expose
a *real FastAPI* fallback app (which Vercel reliably recognizes as ASGI) whose
routes return the startup traceback as plain text — so the failure is readable
in the browser at /api/health instead of Vercel's opaque crash page.
"""

import os
import sys

# Vercel does not put a function's own directory on sys.path — add it so the
# `_main` / `_analysis` / `_llm` / `_prompts` modules resolve at runtime.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from _main import app  # the real FastAPI app (a proper ASGI application)
except Exception:  # noqa: BLE001 — surface ANY startup failure to the client
    import traceback

    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    _startup_error = traceback.format_exc()
    app = FastAPI()

    @app.get("/{full_path:path}")
    def _report_startup_error(full_path: str) -> PlainTextResponse:
        return PlainTextResponse(
            "The Tiebreaker failed to start.\n\n" + _startup_error,
            status_code=500,
        )
