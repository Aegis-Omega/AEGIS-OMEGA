"""Production entrypoint: wrap the AEGIS FastAPI app in the outer authority membrane."""
from __future__ import annotations

import os

import uvicorn

from authority_boundary import AuthorityBoundary
from serve import app as inner_app

app = AuthorityBoundary(inner_app)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
