"""Application settings and model-name normalization."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ModelName = Literal["english", "multilingual", "typed-decisions"]
DeviceName = Literal["auto", "cuda", "cpu", "mps"]
ModelSource = Literal["modelscope", "huggingface", "local"]
FallbackSource = Literal["huggingface", "none"]
MODEL_NAMES: tuple[ModelName, ...] = ("english", "multilingual", "typed-decisions")

MODEL_ALIASES: dict[str, ModelName] = {
    "english": "english",
    "en": "english",
    "laya": "english",
    "default": "english",
    "multilingual": "multilingual",
    "multi": "multilingual",
    "ml": "multilingual",
    "laya-multilingual": "multilingual",
    "typed-decisions": "typed-decisions",
    "typed": "typed-decisions",
    "typed_decisions": "typed-decisions",
    "laya-typed-decisions": "typed-decisions",
    "decisions": "typed-decisions",
}


def normalize_model_name(value: str) -> ModelName:
    """Return the canonical checkpoint name for a supported name or alias."""
    key = str(value).strip().lower()
    try:
        return MODEL_ALIASES[key]
    except KeyError as exc:
        choices = ", ".join(("auto", *MODEL_ALIASES))
        raise ValueError(f"unknown model {value!r}; choose one of: {choices}") from exc


def resolve_device(configured: DeviceName) -> Literal["cuda", "cpu", "mps"]:
    """Resolve a configured device and reject unavailable explicit devices."""
    import torch

    cuda_available = torch.cuda.is_available()
    mps_available = bool(
        hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    )
    if configured == "auto":
        if cuda_available:
            return "cuda"
        if mps_available:
            return "mps"
        return "cpu"
    if configured == "cuda" and not cuda_available:
        raise ValueError("CUDA is not available")
    if configured == "mps" and not mps_available:
        raise ValueError("MPS is not available")
    return configured


class Settings(BaseSettings):
    """WindLaya settings loaded from WINDLAYA_ environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="WINDLAYA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    device: DeviceName = "auto"
    preload_models: Annotated[tuple[ModelName, ...], NoDecode] = ("multilingual",)
    max_loaded: int = Field(default=2, ge=1)
    default_model: ModelName = "english"
    model_source: ModelSource = "modelscope"
    model_fallback_source: FallbackSource = "huggingface"
    model_root: Path = Path("models")
    hf_token: SecretStr | None = None
    ms_token: SecretStr | None = None
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    run_model_tests: bool = False
    serialize_inference: bool = True

    @field_validator("preload_models", mode="before")
    @classmethod
    def parse_preload_models(cls, value: object) -> tuple[ModelName, ...]:
        if value is None or value == "":
            return ()
        raw_values = value.split(",") if isinstance(value, str) else value
        if not isinstance(raw_values, (list, tuple, set)):
            raise ValueError("preload_models must be a comma-separated list")

        normalized: list[ModelName] = []
        for raw in raw_values:
            name = normalize_model_name(str(raw))
            if name not in normalized:
                normalized.append(name)
        return tuple(normalized)

    @field_validator("default_model", mode="before")
    @classmethod
    def normalize_default_model(cls, value: object) -> ModelName:
        name = normalize_model_name(str(value))
        if name == "typed-decisions":
            raise ValueError("default_model must be english or multilingual")
        return name

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        return str(value).strip().upper()

    @model_validator(mode="after")
    def validate_model_cache(self) -> "Settings":
        if self.max_loaded < len(self.preload_models):
            raise ValueError("max_loaded must be at least the number of preload_models")
        return self
