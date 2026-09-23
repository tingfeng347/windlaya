"""Process-level ownership of the Laya Router and its checkpoints."""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from threading import Lock
from typing import Any

from app.core.config import Settings, normalize_model_name, resolve_device
from app.core.errors import (
    InferenceError,
    InvalidModelError,
    ModelLoadError,
    ModelUnavailableError,
)
from app.core.model_artifacts import ArtifactProvider, ModelArtifactProvider

MODEL_CATALOG: tuple[dict[str, Any], ...] = (
    {"id": "auto", "description": "Automatically route by language"},
    {
        "id": "english",
        "repo": "convaiinnovations/laya",
        "language": "English",
    },
    {
        "id": "multilingual",
        "repo": "convaiinnovations/laya-multilingual",
        "language": "100+ languages, including Chinese",
    },
    {
        "id": "typed-decisions",
        "repo": "convaiinnovations/laya-typed-decisions",
        "language": "English",
        "specialized": True,
    },
)

logger = logging.getLogger(__name__)


def _laya_router_factory(**kwargs: Any) -> Any:
    from laya import Router

    return Router(**kwargs)


class ModelManager:
    """Own one Laya Router and expose stable routing and prediction operations."""

    def __init__(
        self,
        settings: Settings,
        router_factory: Callable[..., Any] = _laya_router_factory,
        artifact_provider: ArtifactProvider | None = None,
    ) -> None:
        self.settings = settings
        self.device = resolve_device(settings.device)
        self._router_factory = router_factory
        self._artifact_provider = artifact_provider or ModelArtifactProvider(settings)
        self._router: Any | None = None
        self._inference_lock = Lock()

    def startup(self) -> None:
        """Create the Router once and preload the configured checkpoints."""
        if self._router is not None:
            return
        token = self.settings.hf_token.get_secret_value() if self.settings.hf_token else None
        router = self._router_factory(
            models=self._artifact_provider.router_models(),
            device=self.device,
            token=token,
            max_loaded=self.settings.max_loaded,
            default=self.settings.default_model,
            auto_task_detection=False,
        )
        self._router = router
        if not self.settings.preload_models:
            return
        try:
            self._artifact_provider.require(self.settings.preload_models)
            router.preload(list(self.settings.preload_models))
            for name in self.settings.preload_models:
                self._verify_agent_device(name, router.load(name))
        except ModelLoadError:
            router.unload()
            self._router = None
            raise
        except Exception as exc:
            router.unload()
            self._router = None
            names = ", ".join(self.settings.preload_models)
            raise ModelLoadError(f"Failed to preload Laya checkpoints: {names}") from exc

    def shutdown(self) -> None:
        """Release every loaded checkpoint and discard the Router."""
        if self._router is not None:
            self._router.unload()
            self._router = None

    def route(
        self,
        state: Any,
        questions: dict[str, Any],
        model: str = "auto",
        lang: str | None = None,
    ) -> dict[str, Any]:
        """Select a checkpoint without loading or running it."""
        router = self._require_router()
        normalized = self._normalize_requested_model(model)
        try:
            if normalized == "auto":
                return dict(router.route(state, questions, lang=lang))
            return dict(router.route(state, questions, model=normalized, lang=lang))
        except Exception as exc:
            raise InferenceError("Model routing failed.") from exc

    def predict(
        self,
        state: Any,
        questions: dict[str, Any],
        model: str = "auto",
        lang: str | None = None,
    ) -> dict[str, Any]:
        """Load the selected checkpoint and execute one Laya forward pass."""
        router = self._require_router()
        normalized = self._normalize_requested_model(model)
        lock = self._inference_lock if self.settings.serialize_inference else nullcontext()
        with lock:
            decision = self.route(state, questions, model=normalized, lang=lang)
            selected = str(decision["model"])
            try:
                self._artifact_provider.require((selected,))
                agent = router.load(selected)
                self._verify_agent_device(selected, agent)
            except ModelLoadError:
                raise
            except Exception as exc:
                raise ModelLoadError(
                    f"Failed to load Laya checkpoint {selected!r}. "
                    "Check local artifact and device configuration."
                ) from exc

            try:
                if normalized == "auto":
                    result = dict(router.predict(state, questions, lang=lang))
                else:
                    result = dict(router.predict(state, questions, model=normalized, lang=lang))
            except Exception as exc:
                raise InferenceError(
                    f"Inference failed for Laya checkpoint {selected!r}."
                ) from exc
            self._verify_agent_device(selected, agent)
            return result

    def list_models(self) -> list[dict[str, Any]]:
        return [dict(model) for model in MODEL_CATALOG]

    @property
    def loaded_models(self) -> list[str]:
        if self._router is None:
            return []
        return list(self._router.loaded)

    @contextmanager
    def lifespan(self) -> Iterator["ModelManager"]:
        self.startup()
        try:
            yield self
        finally:
            self.shutdown()

    def _require_router(self) -> Any:
        if self._router is None:
            raise ModelUnavailableError("The Laya Router is not initialized.")
        return self._router

    @staticmethod
    def _normalize_requested_model(model: str) -> str:
        if model.strip().lower() == "auto":
            return "auto"
        try:
            return normalize_model_name(model)
        except ValueError as exc:
            raise InvalidModelError(str(exc)) from exc

    def _verify_agent_device(self, name: str, agent: Any) -> None:
        actual = str(agent.device).split(":", maxsplit=1)[0]
        if actual != self.device:
            if self.settings.device == "auto" and actual == "cpu":
                logger.warning(
                    "event=device_fallback model=%s preferred_device=%s "
                    "actual_device=cpu message=%r",
                    name,
                    self.device,
                    "GPU model loading failed; continuing on CPU",
                )
                self.device = "cpu"
                return
            if self._router is not None:
                self._router.unload(name)
            raise ModelLoadError(
                f"Laya checkpoint {name!r} loaded on {actual!r}, expected {self.device!r}. "
                "Configure WINDLAYA_DEVICE explicitly instead of relying on silent fallback."
            )
