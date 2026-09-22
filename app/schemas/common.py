"""Response models shared by the WindLaya API."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RootResponse(ResponseModel):
    name: Literal["windlaya"] = "windlaya"
    version: str
    status: Literal["ok"] = "ok"


class HealthResponse(ResponseModel):
    status: Literal["ok"] = "ok"
    device: str
    loaded_models: list[str]
    default_model: str


class ModelInfo(ResponseModel):
    id: str
    description: str | None = None
    repo: str | None = None
    language: str | None = None
    specialized: bool | None = None


class ModelsResponse(ResponseModel):
    models: list[ModelInfo]
    loaded_models: list[str]


class RouteResponse(ResponseModel):
    request_id: str
    requested_model: str
    selected_model: str
    reason: str | None
    workflow: str | None
    detection: Any = None


class PredictionMeta(ResponseModel):
    api_version: Literal["v1"] = "v1"
    device: str
    elapsed_ms: float


class PredictResponse(ResponseModel):
    request_id: str
    model: str
    routing: dict[str, Any]
    answers: dict[str, Any]
    usage: dict[str, Any]
    meta: PredictionMeta


class ErrorBody(ResponseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(ResponseModel):
    error: ErrorBody
