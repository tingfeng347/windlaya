import pytest
from pydantic import ValidationError

from app.core.config import Settings, resolve_device


def test_settings_normalize_model_aliases_and_reject_an_impossible_cache() -> None:
    settings = Settings(
        preload_models="en,ml,en",
        default_model="multi",
        max_loaded=2,
        _env_file=None,
    )

    assert settings.preload_models == ("english", "multilingual")
    assert settings.default_model == "multilingual"
    assert settings.model_source == "modelscope"
    assert settings.model_fallback_source == "huggingface"
    assert str(settings.model_root) == "models"

    with pytest.raises(ValidationError, match="max_loaded"):
        Settings(preload_models="english,multilingual", max_loaded=1, _env_file=None)


def test_auto_device_uses_cuda_mps_cpu_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert resolve_device("auto") == "mps"

    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    assert resolve_device("auto") == "cpu"

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert resolve_device("auto") == "cuda"


def test_explicit_unavailable_device_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(ValueError, match="CUDA is not available"):
        resolve_device("cuda")
