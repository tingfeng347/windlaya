"""Small HTTP client used by the Streamlit playground."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass(slots=True)
class PlaygroundApiError(Exception):
    """A connection or API error safe to display in the playground."""

    message: str
    code: str = "CONNECTION_ERROR"
    request_id: str | None = None
    status_code: int | None = None

    def __str__(self) -> str:
        return self.message


def normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("API 地址必须是完整的 http:// 或 https:// URL。")
    return normalized


class WindLayaApiClient:
    """Call WindLaya without sharing implementation code with the API process."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 300.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.timeout = timeout
        self._transport = transport

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", timeout=10.0)

    def models(self) -> dict[str, Any]:
        return self._request("GET", "/v1/models", timeout=10.0)

    def route(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/route", json=payload, timeout=30.0)

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/predict", json=payload, timeout=self.timeout)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: float,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=timeout,
                transport=self._transport,
            ) as client:
                response = client.request(method, path, json=json)
        except httpx.TimeoutException as exc:
            raise PlaygroundApiError(
                f"请求超过 {timeout:g} 秒，后端可能仍在加载模型。",
                code="TIMEOUT",
            ) from exc
        except httpx.RequestError as exc:
            raise PlaygroundApiError(
                "无法连接 WindLaya API，请检查后端是否启动以及 API 地址是否正确。"
            ) from exc

        request_id = response.headers.get("X-Request-ID")
        try:
            body = response.json()
        except ValueError as exc:
            raise PlaygroundApiError(
                "WindLaya API 返回了非 JSON 响应。",
                code="INVALID_RESPONSE",
                request_id=request_id,
                status_code=response.status_code,
            ) from exc

        if response.is_error:
            error = body.get("error", {}) if isinstance(body, dict) else {}
            raise PlaygroundApiError(
                str(error.get("message") or f"API 请求失败（HTTP {response.status_code}）。"),
                code=str(error.get("code") or "HTTP_ERROR"),
                request_id=str(error.get("request_id") or request_id or "") or None,
                status_code=response.status_code,
            )
        if not isinstance(body, dict):
            raise PlaygroundApiError(
                "WindLaya API 返回了无法识别的数据结构。",
                code="INVALID_RESPONSE",
                request_id=request_id,
                status_code=response.status_code,
            )
        return body
