from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.playground.api_client import PlaygroundApiError, WindLayaApiClient, normalize_base_url
from app.playground.presentation import (
    directional_conclusion,
    parse_choice_criteria,
    parse_score_criteria,
    parse_state,
    request_as_curl,
)
from app.playground.scenarios import scenario_payload


def test_playground_scenarios_are_independent_and_parseable() -> None:
    first = scenario_payload("support-triage")
    second = scenario_payload("support-triage")
    first["questions"]["intent"]["criteria"]["new"] = "new"

    assert "new" not in second["questions"]["intent"]["criteria"]
    assert isinstance(parse_state('{"message":"hello"}', True), dict)
    assert parse_state("hello", False) == "hello"


def test_content_moderation_scenario_matches_the_risk_in_its_state() -> None:
    questions = scenario_payload("content-moderation")["questions"]

    assert "privacy" in questions
    assert "threat" not in questions
    assert questions["privacy"]["instructions"] == "是否包含泄露私人信息的行为？"
    assert "泄露隐私" in questions["severity"]["criteria"][2]


def test_playground_editing_helpers_validate_structured_values() -> None:
    assert parse_choice_criteria("yes: 是\nno: 否") == {"yes": "是", "no": "否"}
    assert parse_score_criteria("low\nmedium\nhigh") == ["low", "medium", "high"]
    assert directional_conclusion(0.5) == "倾向成立"
    assert directional_conclusion(0.49) == "倾向不成立"
    assert "/v1/predict" in request_as_curl("http://localhost:8000/", {"state": "x"})

    with pytest.raises(ValueError, match="至少需要两个"):
        parse_choice_criteria("only: one")
    with pytest.raises(ValueError, match="JSON 无效"):
        parse_state("{bad", True)


def test_api_client_returns_stable_error_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            headers={"X-Request-ID": "trace-1"},
            json={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request validation failed.",
                    "request_id": "trace-1",
                }
            },
        )

    client = WindLayaApiClient(
        "http://localhost:8000",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(PlaygroundApiError) as raised:
        client.predict({"state": "x"})
    assert raised.value.code == "INVALID_REQUEST"
    assert raised.value.request_id == "trace-1"
    assert raised.value.status_code == 422
    assert normalize_base_url("http://localhost:8000/") == "http://localhost:8000"


def test_api_client_calls_health_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok", "device": "cpu"})

    client = WindLayaApiClient("http://localhost:8000", transport=httpx.MockTransport(handler))
    assert client.health()["device"] == "cpu"


def test_streamlit_playground_renders_and_switches_scenarios() -> None:
    entrypoint = Path(__file__).parents[2] / "streamlit_app.py"
    app = AppTest.from_file(entrypoint, default_timeout=15).run()
    assert not app.exception
    assert any(button.label == "执行决策" for button in app.button)
    assert any(text.value == "当前会话还没有执行记录。" for text in app.caption)

    scenario = next(select for select in app.selectbox if select.label == "示例场景")
    scenario.set_value("content-moderation")
    app.run()
    next(button for button in app.button if button.label == "载入场景").click().run()
    assert not app.exception
    assert any(text.value.startswith("判断内容风险") for text in app.caption)


def test_streamlit_playground_json_editor_applies_without_exception() -> None:
    entrypoint = Path(__file__).parents[2] / "streamlit_app.py"
    app = AppTest.from_file(entrypoint, default_timeout=15).run()
    app.segmented_control[0].set_value("JSON").run()
    next(button for button in app.button if button.label == "应用 JSON").click().run()
    assert not app.exception


def test_streamlit_type_switch_does_not_reuse_incompatible_criteria() -> None:
    entrypoint = Path(__file__).parents[2] / "streamlit_app.py"
    app = AppTest.from_file(entrypoint, default_timeout=15).run()
    first_question_type = next(select for select in app.selectbox if select.label == "决策原语")
    first_question_type.set_value("noul").run()
    assert not app.exception
    assert all(not button.disabled for button in app.button if button.label == "执行决策")
