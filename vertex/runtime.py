#!/usr/bin/env python3
"""Production entrypoint: outer authority membrane around the FastAPI app."""
from __future__ import annotations

import os

import uvicorn

from authority_boundary import AuthorityBoundary
from serve import app as application

app = AuthorityBoundary(application)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
