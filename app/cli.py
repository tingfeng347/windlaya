"""Console entry point for the local WindLaya server."""

import uvicorn

from app.core.config import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, workers=1)
