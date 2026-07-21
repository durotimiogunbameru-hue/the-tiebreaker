"""
api/index.py — Vercel serverless entry point (also the local uvicorn target).

Vercel serves the ASGI `app` exported here for every /api/* request (see
vercel.json); the static frontend in public/ is served from Vercel's CDN.

Robustness: Vercel does NOT put a function's own directory on sys.path, so we
add it explicitly before importing the app's modules. If importing the app
still fails for any reason, we fall back to a tiny ASGI app that returns the
full traceback as plain text — so the failure is visible in the browser
(at /api/health) instead of showing Vercel's opaque crash page.
"""

import os
import sys
import traceback

# Put this file's directory (api/) on the import path so `_main`, `_analysis`,
# `_llm`, and `_prompts` resolve regardless of the process working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from _main import app  # the real FastAPI app; `app` is the ASGI callable
except Exception:  # noqa: BLE001 — surface *any* startup failure to the client
    _startup_traceback = traceback.format_exc()

    async def app(scope, receive, send):  # type: ignore[no-redef]
        """Minimal fallback ASGI app that reports why startup failed."""
        if scope["type"] != "http":
            return
        message = (
            "The Tiebreaker function failed to start.\n\n"
            + _startup_traceback
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": message})
