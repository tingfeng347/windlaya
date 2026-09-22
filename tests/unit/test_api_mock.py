from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.model_manager import ModelManager
from app.main import create_app
from tests.fakes import FakeArtifactProvider, FakeRouter


def test_http_api_exposes_the_complete_offline_success_path() -> None:
    fake_router = FakeRouter(device="cpu")
    settings = Settings(device="cpu", preload_models="", _env_file=None)
    manager = ModelManager(
        settings,
        router_factory=lambda **_: fake_router,
        artifact_provider=FakeArtifactProvider(),
    )
    app = create_app(settings=settings, model_manager=manager)
    payload = {
        "state": "我需要退款",
        "model": "auto",
        "questions": {
            "refund": {"type": "noul", "instructions": "用户是否要求退款？"}
        },
    }

    with TestClient(app) as client:
        root = client.get("/", headers={"X-Request-ID": "trace-123"})
        assert root.json() == {"name": "windlaya", "version": "0.1.0", "status": "ok"}
        assert root.headers["X-Request-ID"] == "trace-123"

        assert client.get("/health").json() == {
            "status": "ok",
            "device": "cpu",
            "loaded_models": [],
            "default_model": "english",
        }
        models = client.get("/v1/models").json()["models"]
        assert [model["id"] for model in models] == [
            "auto",
            "english",
            "multilingual",
            "typed-decisions",
        ]
        assert models[0] == {
            "id": "auto",
            "description": "Automatically route by language",
        }

        route = client.post("/v1/route", json=payload).json()
        assert route["selected_model"] == "multilingual"
        assert fake_router.forward_calls == 0

        prediction = client.post("/v1/predict", json=payload).json()
        assert prediction["model"] == "multilingual"
        assert prediction["meta"]["device"] == "cpu"


def test_http_api_uses_one_safe_error_envelope() -> None:
    class BrokenRouter(FakeRouter):
        def route(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if kwargs.get("model") == "english":
                raise RuntimeError("internal routing detail")
            return super().route(*args, **kwargs)

    settings = Settings(device="cpu", preload_models="", _env_file=None)
    manager = ModelManager(
        settings,
        router_factory=lambda **_: BrokenRouter(device="cpu"),
        artifact_provider=FakeArtifactProvider(),
    )
    app = create_app(settings=settings, model_manager=manager)
    payload = {
        "state": "hello",
        "questions": {
            "refund": {"type": "noul", "instructions": "Requesting refund?"}
        },
    }

    with TestClient(app, raise_server_exceptions=False) as client:
        unknown = client.post("/v1/route", json={**payload, "model": "missing"})
        assert unknown.status_code == 400
        assert unknown.json()["error"]["code"] == "INVALID_MODEL"

        invalid = client.post("/v1/predict", json={**payload, "unexpected": True})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "INVALID_REQUEST"

        missing = client.get("/does-not-exist")
        assert missing.status_code == 404
        assert missing.json()["error"]["request_id"] == missing.headers["X-Request-ID"]

        broken = client.post("/v1/route", json={**payload, "model": "english"})
        assert broken.status_code == 500
        assert broken.json()["error"] == {
            "code": "INFERENCE_ERROR",
            "message": "Model routing failed.",
            "request_id": broken.headers["X-Request-ID"],
        }

        unsafe_id = client.get("/", headers={"X-Request-ID": "contains whitespace"})
        assert unsafe_id.status_code == 400
        assert unsafe_id.json()["error"]["request_id"] != "contains whitespace"
