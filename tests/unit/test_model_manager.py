import pytest

from app.core.config import Settings
from app.core.errors import ModelLoadError
from app.core.model_manager import ModelManager
from tests.fakes import FakeArtifactProvider, FakeRouter


def test_default_startup_preloads_multilingual_and_hot_loads_an_explicit_model() -> None:
    router = FakeRouter(device="cpu")
    artifacts = FakeArtifactProvider()

    def create_router(**kwargs: object) -> FakeRouter:
        assert kwargs["models"] == artifacts.router_models()
        return router

    manager = ModelManager(
        Settings(device="cpu", _env_file=None),
        router_factory=create_router,
        artifact_provider=artifacts,
    )
    manager.startup()

    assert manager.loaded_models == ["multilingual"]
    assert artifacts.required == [("multilingual",)]

    manager.predict(
        "Please refund me.",
        {"refund": {"type": "noul", "instructions": "Refund requested?"}},
        model="english",
    )

    assert manager.loaded_models == ["multilingual", "english"]
    assert artifacts.required[-1] == ("english",)


def test_manager_routes_without_inference_and_predicts_with_canonical_models() -> None:
    router = FakeRouter(device="cpu")
    settings = Settings(device="cpu", preload_models="", _env_file=None)
    manager = ModelManager(
        settings,
        router_factory=lambda **_: router,
        artifact_provider=FakeArtifactProvider(),
    )
    manager.startup()

    questions = {"refund": {"type": "noul", "instructions": "是否退款"}}
    route = manager.route("我需要退款", questions)
    assert route["model"] == "multilingual"
    assert router.forward_calls == 0
    assert manager.loaded_models == []

    result = manager.predict("hello", questions, model="ml")
    assert result["routing"]["model"] == "multilingual"
    assert manager.loaded_models == ["multilingual"]

    manager.shutdown()
    assert manager.loaded_models == []


def test_manager_rejects_a_device_fallback_during_inference() -> None:
    class FallbackRouter(FakeRouter):
        def predict(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = super().predict(*args, **kwargs)
            selected = result["routing"]["model"]
            self._agents[selected].device = "cuda"
            return result

    router = FallbackRouter(device="cpu")
    settings = Settings(device="cpu", preload_models="", _env_file=None)
    manager = ModelManager(
        settings,
        router_factory=lambda **_: router,
        artifact_provider=FakeArtifactProvider(),
    )
    manager.startup()

    with pytest.raises(ModelLoadError, match="loaded on 'cuda', expected 'cpu'"):
        manager.predict(
            "hello",
            {"refund": {"type": "noul", "instructions": "Refund?"}},
            model="english",
        )
