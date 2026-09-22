import os

import pytest

from app.core.config import Settings
from app.core.model_manager import ModelManager

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("WINDLAYA_RUN_MODEL_TESTS", "false").lower() != "true",
        reason="prepare checkpoints and set WINDLAYA_RUN_MODEL_TESTS=true",
    ),
]


def test_real_multilingual_checkpoint_returns_valid_decisions(
    multilingual_questions: dict,
) -> None:
    manager = ModelManager(
        Settings(
            device=os.getenv("WINDLAYA_DEVICE", "cpu"),
            preload_models="multilingual",
            max_loaded=1,
            _env_file=None,
        )
    )
    try:
        manager.startup()
        result = manager.predict(
            "我的账户昨天被扣了两次款，请尽快退款。",
            multilingual_questions,
            model="auto",
        )
    finally:
        manager.shutdown()

    assert result["routing"]["model"] == "multilingual"
    intent = result["answers"]["intent"]
    assert intent["choice"] in multilingual_questions["intent"]["criteria"]
    assert sum(intent["probabilities"].values()) == pytest.approx(1.0, abs=1e-3)
    assert 0 <= result["answers"]["refund_requested"]["noul"] <= 1
