"""Console entry point for the local WindLaya server."""

import platform
import sys
from typing import Any

import uvicorn
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ModelLoadError
from app.core.model_manager import ModelManager

DESKTOP_SYSTEMS = {"Windows", "Darwin"}


class DesktopEnvironmentError(Exception):
    """A recoverable local ML runtime or checkpoint startup failure."""


def _environment_help(system: str, exc: Exception) -> str:
    platform_name = "Windows" if system == "Windows" else "macOS"
    device_hint = (
        "Verify the NVIDIA driver and PyTorch CUDA support, or set "
        "WINDLAYA_DEVICE=cpu."
        if system == "Windows"
        else "Use WINDLAYA_DEVICE=mps on Apple silicon when available, or set "
        "WINDLAYA_DEVICE=cpu."
    )
    return "\n".join(
        (
            f"WindLaya was not started: the {platform_name} environment is not ready.",
            f"Reason: {exc}",
            "Run `uv sync --frozen` with Python 3.12 and check the installed PyTorch runtime.",
            device_hint,
            "The process exited normally without starting the API server.",
        )
    )


def _create_preloaded_app(settings: Settings) -> Any:
    """Validate the desktop ML environment before Uvicorn takes ownership."""
    try:
        manager = ModelManager(settings)
        manager.startup()
    except (ImportError, OSError, RuntimeError, ValueError, ModelLoadError) as exc:
        if "manager" in locals():
            manager.shutdown()
        raise DesktopEnvironmentError(str(exc)) from exc

    from app.main import create_app

    return create_app(settings=settings, model_manager=manager)


def main() -> int:
    system = platform.system()
    if system not in DESKTOP_SYSTEMS:
        settings = Settings()
        uvicorn.run("app.main:app", host=settings.host, port=settings.port, workers=1)
        return 0

    try:
        settings = Settings()
        application = _create_preloaded_app(settings)
    except (ValidationError, DesktopEnvironmentError) as exc:
        print(_environment_help(system, exc), file=sys.stderr)
        return 0

    uvicorn.run(application, host=settings.host, port=settings.port, workers=1)
    return 0
