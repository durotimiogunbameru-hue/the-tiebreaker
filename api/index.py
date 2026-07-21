"""
api/index.py — Vercel serverless entry point (also the local uvicorn target).

Everything the function needs lives in this same `api/` directory, so Vercel
bundles it automatically with no cross-directory imports or include-file globs
to get wrong. Vercel serves the ASGI `app` exported here for every /api/*
request (see vercel.json); the static frontend in public/ is served straight
from Vercel's CDN.
"""

from main import app  # noqa: F401  — `app` is the ASGI callable Vercel invokes
