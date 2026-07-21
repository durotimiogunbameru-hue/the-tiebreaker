"""
api/index.py — Vercel serverless entry point.

Vercel's Python runtime serves the ASGI `app` it finds in this module. We reuse
the exact FastAPI app from backend/app.py, so there is one source of truth for
the API whether it runs locally (uvicorn) or on Vercel (serverless).

The `vercel.json` rewrite sends every /api/* request here; the static frontend
in public/ is served directly by Vercel's CDN. app.py's static-file mount is
skipped automatically in this environment because the public/ directory isn't
bundled with the function (see the FRONTEND_DIR.exists() guard in app.py).
"""

import os
import sys

# Make the backend package importable from this file's location.
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)

from app import app  # noqa: E402  (path setup must come first)

# `app` is the ASGI callable Vercel invokes for each request.
