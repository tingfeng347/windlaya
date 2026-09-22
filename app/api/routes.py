"""WindLaya HTTP endpoint definitions."""

from fastapi import APIRouter, Request

from app import __version__
from app.core.model_manager import ModelManager
from app.schemas.common import (
    HealthResponse,
    ModelsResponse,
    PredictResponse,
    RootResponse,
    RouteResponse,
)
from app.schemas.decision import DecisionRequest
from app.services.decision_service import DecisionService

router = APIRouter()


def _service(request: Request) -> DecisionService:
    return request.app.state.decision_service


def _manager(request: Request) -> ModelManager:
    return request.app.state.model_manager


@router.get(
    "/",
    response_model=RootResponse,
    summary="查看服务信息",
    description="返回 WindLaya 服务名称、版本和进程状态。",
)
def root() -> RootResponse:
    return RootResponse(version=__version__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="检查服务健康状态",
    description="报告实际设备和已加载 checkpoint，不触发模型加载。",
)
def health(request: Request) -> HealthResponse:
    manager = _manager(request)
    return HealthResponse(
        device=manager.device,
        loaded_models=manager.loaded_models,
        default_model=manager.settings.default_model,
    )


@router.get(
    "/v1/models",
    response_model=ModelsResponse,
    response_model_exclude_none=True,
    summary="列出可用模型",
    description="列出模型模式、checkpoint 元数据和当前已加载模型。",
)
def models(request: Request) -> ModelsResponse:
    manager = _manager(request)
    return ModelsResponse(models=manager.list_models(), loaded_models=manager.loaded_models)


@router.post(
    "/v1/route",
    response_model=RouteResponse,
    summary="选择决策模型",
    description="仅执行语言路由，不加载 checkpoint，也不运行神经网络推理。",
)
def route(payload: DecisionRequest, request: Request) -> dict:
    return _service(request).route(payload, request.state.request_id)


@router.post(
    "/v1/predict",
    response_model=PredictResponse,
    summary="执行 System-1 决策",
    description="自动或显式选择 Laya checkpoint，并执行 choice、score 或 noul 判断。",
)
def predict(payload: DecisionRequest, request: Request) -> dict:
    return _service(request).predict(payload, request.state.request_id)
