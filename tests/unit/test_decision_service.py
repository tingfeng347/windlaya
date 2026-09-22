from app.core.config import Settings
from app.core.model_manager import ModelManager
from app.schemas.decision import DecisionRequest
from app.services.decision_service import DecisionService
from tests.fakes import FakeRouter


def test_predict_publishes_the_stable_windlaya_envelope() -> None:
    router = FakeRouter(device="cpu")
    manager = ModelManager(
        Settings(device="cpu", preload_models="", _env_file=None),
        router_factory=lambda **_: router,
    )
    manager.startup()
    times = iter((10.0, 10.025))
    service = DecisionService(manager, clock=lambda: next(times))
    request = DecisionRequest.model_validate(
        {
            "state": "hello",
            "model": "en",
            "questions": {
                "refund": {"type": "noul", "instructions": "Requesting refund?"}
            },
        }
    )

    response = service.predict(request, request_id="trace-123")

    assert response == {
        "request_id": "trace-123",
        "model": "english",
        "routing": {
            "model": "english",
            "repo": "fake/english",
            "reason": "explicit model='english'",
            "detection": None,
            "workflow": None,
        },
        "answers": {"refund": {"type": "noul"}},
        "usage": {"input_tokens": 7, "output_tokens": 0},
        "meta": {"api_version": "v1", "device": "cpu", "elapsed_ms": 25.0},
    }
