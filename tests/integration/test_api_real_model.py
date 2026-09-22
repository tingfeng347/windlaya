import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.model_manager import ModelManager
from app.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("WINDLAYA_RUN_MODEL_TESTS", "false").lower() != "true",
        reason="prepare checkpoints and set WINDLAYA_RUN_MODEL_TESTS=true",
    ),
]


def test_real_checkpoint_is_available_through_http(multilingual_questions: dict) -> None:
    settings = Settings(
        device=os.getenv("WINDLAYA_DEVICE", "cpu"),
        preload_models="multilingual",
        max_loaded=1,
        _env_file=None,
    )
    manager = ModelManager(settings)
    app = create_app(settings=settings, model_manager=manager)
    payload = {
        "state": "二重に請求されました。返金してください。",
        "questions": multilingual_questions,
        "model": "auto",
    }

    with TestClient(app) as client:
        response = client.post("/v1/predict", json=payload)

    assert response.status_code == 200
    assert response.json()["model"] == "multilingual"
