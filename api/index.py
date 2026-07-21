"""
api/index.py — Vercel serverless entry point (also the local uvicorn target).

Everything the function needs lives in this same `api/` directory. Vercel does
NOT put a serverless function's own directory on sys.path, so sibling imports
like `from main import app` fail with ModuleNotFoundError at invocation (the
cause of a FUNCTION_INVOCATION_FAILED / 500). We add this directory to the path
explicitly first, which makes the imports resolve on both Vercel and locally.

Vercel serves the ASGI `app` exported here for every /api/* request (see
vercel.json); the static frontend in public/ is served from Vercel's CDN.
"""

import os
import sys

# Put this file's directory (api/) on the import path so `main`, `analysis`,
# `llm`, and `prompts` resolve regardless of the process working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _main import app  # noqa: E402, F401  — `app` is the ASGI callable Vercel invokes
