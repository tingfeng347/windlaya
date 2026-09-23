"""WindLaya Playground Streamlit application entry point."""
# ruff: noqa: E501

from __future__ import annotations

import html
import json
import os
from copy import deepcopy
from datetime import datetime
from typing import Any

import streamlit as st

from app.playground.api_client import PlaygroundApiError, WindLayaApiClient
from app.playground.presentation import (
    directional_conclusion,
    parse_choice_criteria,
    parse_score_criteria,
    parse_state,
    request_as_curl,
    request_as_python,
)
from app.playground.scenarios import SCENARIOS, SCENARIOS_BY_ID, scenario_payload

DEFAULT_API_URL = os.getenv("WINDLAYA_API_BASE_URL", "http://127.0.0.1:8000")
MODEL_OPTIONS = ("auto", "english", "multilingual", "typed-decisions")
QUESTION_TYPES = ("choice", "score", "noul")

st.set_page_config(
    page_title="WindLaya Playground",
    page_icon=":material/route:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _initialize_state() -> None:
    defaults = {
        "api_url": DEFAULT_API_URL,
        "scenario_id": "support-triage",
        "payload": scenario_payload("support-triage"),
        "editor_version": 0,
        "editor_mode": "可视化",
        "response": None,
        "response_kind": None,
        "last_error": None,
        "editor_error": None,
        "health": None,
        "health_error": None,
        "history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _client() -> WindLayaApiClient:
    return WindLayaApiClient(st.session_state.api_url)


def _refresh_health() -> None:
    try:
        client = _client()
        st.session_state.health = client.health()
        st.session_state.health_error = None
    except (PlaygroundApiError, ValueError) as exc:
        st.session_state.health = None
        st.session_state.health_error = str(exc)


def _load_payload(payload: dict[str, Any], *, scenario_id: str | None = None) -> None:
    st.session_state.payload = deepcopy(payload)
    st.session_state.editor_version += 1
    st.session_state.response = None
    st.session_state.response_kind = None
    st.session_state.last_error = None
    if scenario_id is not None:
        st.session_state.scenario_id = scenario_id


def _criteria_text(question: dict[str, Any]) -> str:
    criteria = question.get("criteria")
    if question.get("type") == "choice" and isinstance(criteria, dict):
        return "\n".join(
            f"{label}: {description or ''}" for label, description in criteria.items()
        )
    if question.get("type") == "score" and isinstance(criteria, list):
        return "\n".join(str(level) for level in criteria)
    return ""


def _visual_editor(payload: dict[str, Any]) -> dict[str, Any]:
    st.session_state.editor_error = None
    version = st.session_state.editor_version
    state = payload.get("state", "")
    structured = isinstance(state, (dict, list))

    top_a, top_b = st.columns([3, 2])
    with top_a:
        model = st.selectbox(
            "模型模式",
            MODEL_OPTIONS,
            index=MODEL_OPTIONS.index(payload.get("model", "auto")),
            key=f"model_{version}",
        )
    with top_b:
        lang = st.text_input(
            "语言提示（可选）",
            value=payload.get("lang") or "",
            placeholder="例如 zh、en、ja",
            key=f"lang_{version}",
        )

    state_format = st.segmented_control(
        "状态格式",
        ("文本", "JSON"),
        default="JSON" if structured else "文本",
        key=f"state_format_{version}",
    )
    state_value = (
        json.dumps(state, ensure_ascii=False, indent=2) if structured else str(state)
    )
    state_text = st.text_area(
        "状态",
        value=state_value,
        height=132,
        placeholder="输入需要判断的上下文",
        key=f"state_{version}",
    )

    st.markdown("#### 问题")
    questions = payload.get("questions", {})
    draft_questions: dict[str, Any] = {}
    remove_index: int | None = None
    validation_messages: list[str] = []

    for index, (question_id, question) in enumerate(questions.items()):
        with st.container(border=True):
            header_a, header_b, header_c = st.columns([3, 2, 0.7])
            with header_a:
                current_id = st.text_input(
                    "问题标识",
                    value=question_id,
                    key=f"qid_{version}_{index}",
                ).strip()
            with header_b:
                current_type = st.selectbox(
                    "决策原语",
                    QUESTION_TYPES,
                    index=QUESTION_TYPES.index(question.get("type", "noul")),
                    key=f"qtype_{version}_{index}",
                )
            with header_c:
                st.write("")
                st.write("")
                if st.button(
                    "删除",
                    icon=":material/delete:",
                    key=f"remove_{version}_{index}",
                    type="tertiary",
                ):
                    remove_index = index

            instructions = st.text_input(
                "判断说明",
                value=str(question.get("instructions", "")),
                key=f"instructions_{version}_{index}",
            )
            criteria_text = ""
            if current_type == "choice":
                criteria_text = st.text_area(
                    "选项（每行“标识: 说明”）",
                    value=_criteria_text(question),
                    height=112,
                    key=f"criteria_{version}_{index}",
                )
            elif current_type == "score":
                criteria_text = st.text_area(
                    "等级（由低到高，每行一个）",
                    value=_criteria_text(question),
                    height=112,
                    key=f"criteria_{version}_{index}",
                )

            if not current_id:
                validation_messages.append(f"第 {index + 1} 个问题缺少标识。")
                current_id = f"question_{index + 1}"
            elif current_id in draft_questions:
                validation_messages.append(f"问题标识“{current_id}”重复。")

            draft: dict[str, Any] = {
                "type": current_type,
                "instructions": instructions,
            }
            try:
                if current_type == "choice":
                    draft["criteria"] = parse_choice_criteria(criteria_text)
                elif current_type == "score":
                    draft["criteria"] = parse_score_criteria(criteria_text)
                elif current_type == "noul":
                    old_criteria = question.get("criteria")
                    if isinstance(old_criteria, dict) and set(old_criteria) <= {"false", "true"}:
                        draft["criteria"] = old_criteria
            except ValueError as exc:
                validation_messages.append(f"{current_id}：{exc}")
                if current_type == "choice":
                    draft["criteria"] = {"option_a": "选项 A", "option_b": "选项 B"}
                elif current_type == "score":
                    draft["criteria"] = ["低", "高"]
            draft_questions[current_id] = draft

    controls_a, controls_b = st.columns([2, 5])
    with controls_a:
        add_type = st.selectbox(
            "新增类型",
            QUESTION_TYPES,
            label_visibility="collapsed",
            key=f"add_type_{version}",
        )
    with controls_b:
        add_question = st.button(
            "添加问题",
            icon=":material/add:",
            key=f"add_{version}",
            use_container_width=True,
        )

    try:
        parsed_state = parse_state(state_text, state_format == "JSON")
    except ValueError as exc:
        validation_messages.append(str(exc))
        parsed_state = state_text

    draft_payload: dict[str, Any] = {
        "state": parsed_state,
        "questions": draft_questions,
        "model": model,
    }
    if lang.strip():
        draft_payload["lang"] = lang.strip()

    if remove_index is not None:
        kept = {
            key: value
            for idx, (key, value) in enumerate(draft_questions.items())
            if idx != remove_index
        }
        draft_payload["questions"] = kept
        _load_payload(draft_payload)
        st.rerun()

    if add_question:
        next_number = len(draft_questions) + 1
        new_id = f"question_{next_number}"
        while new_id in draft_questions:
            next_number += 1
            new_id = f"question_{next_number}"
        new_question: dict[str, Any] = {
            "type": add_type,
            "instructions": "请输入判断说明",
        }
        if add_type == "choice":
            new_question["criteria"] = {"option_a": "选项 A", "option_b": "选项 B"}
        elif add_type == "score":
            new_question["criteria"] = ["低", "高"]
        draft_payload["questions"][new_id] = new_question
        _load_payload(draft_payload)
        st.rerun()

    st.session_state.payload = deepcopy(draft_payload)
    if validation_messages:
        st.session_state.editor_error = validation_messages[0]
        with st.expander("编辑器校验", expanded=False):
            for message in validation_messages:
                st.warning(message)
    return draft_payload


def _json_editor(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    version = st.session_state.editor_version
    raw = st.text_area(
        "完整请求 JSON",
        value=json.dumps(payload, ensure_ascii=False, indent=2),
        height=560,
        key=f"json_payload_{version}",
    )
    parsed: dict[str, Any] | None = None
    error: str | None = None
    try:
        candidate = json.loads(raw)
        if not isinstance(candidate, dict):
            raise ValueError("请求必须是 JSON 对象。")
        parsed = candidate
    except (json.JSONDecodeError, ValueError) as exc:
        error = f"JSON 无效：{exc}"

    if st.button(
        "应用 JSON",
        icon=":material/check:",
        use_container_width=True,
        disabled=parsed is None,
    ):
        _load_payload(parsed or payload)
        st.rerun()
    if error:
        st.error(error)
    return parsed, error


def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _probability_rows(probabilities: dict[str, Any], highlight: str | None = None) -> str:
    rows = []
    for label, raw_value in probabilities.items():
        probability = min(max(_safe_number(raw_value), 0.0), 1.0)
        active = " active" if label == highlight else ""
        rows.append(
            '<div class="wl-prob-row">'
            f'<div class="wl-prob-label{active}">{html.escape(str(label))}</div>'
            '<div class="wl-prob-track">'
            f'<span style="width:{probability * 100:.2f}%"></span></div>'
            f'<div class="wl-prob-value">{probability * 100:.1f}%</div></div>'
        )
    return "".join(rows)


def _answer_card(question_id: str, answer: dict[str, Any]) -> None:
    answer_type = str(answer.get("type", "unknown"))
    confidence = _safe_number(answer.get("confidence"))
    if answer_type == "choice":
        choice = str(answer.get("choice", "—"))
        headline = html.escape(choice)
        detail = _probability_rows(answer.get("probabilities", {}), choice)
    elif answer_type == "score":
        score = _safe_number(answer.get("score"))
        legend = answer.get("legend", {})
        maximum = max(len(legend) - 1, 1)
        headline = f"{score:.2f} / {maximum}"
        detail = _probability_rows(answer.get("probabilities", {}))
    elif answer_type == "noul":
        probability = min(max(_safe_number(answer.get("noul")), 0.0), 1.0)
        headline = f"{directional_conclusion(probability)} · {probability * 100:.1f}%"
        detail = (
            '<div class="wl-binary-track">'
            f'<span style="width:{probability * 100:.2f}%"></span></div>'
            '<div class="wl-binary-scale"><span>不成立</span><span>成立</span></div>'
        )
    else:
        headline = "无法识别的结果"
        detail = ""

    st.html(
        '<section class="wl-answer">'
        '<div class="wl-answer-head">'
        f'<div><div class="wl-answer-id">{html.escape(question_id)}</div>'
        f'<div class="wl-answer-value">{headline}</div></div>'
        f'<div class="wl-confidence">置信度<br><strong>{confidence * 100:.1f}%</strong></div>'
        f"</div>{detail}</section>"
    )


def _render_result(payload: dict[str, Any]) -> None:
    response = st.session_state.response
    response_kind = st.session_state.response_kind
    error = st.session_state.last_error

    st.markdown("### 结果")
    if error:
        st.error(error.message)
        meta = [error.code]
        if error.status_code:
            meta.append(f"HTTP {error.status_code}")
        if error.request_id:
            meta.append(f"Request ID: {error.request_id}")
        st.caption(" · ".join(meta))
        st.info("输入已保留。检查服务状态后可以直接重试。")
        return

    if not response:
        st.html(
            '<div class="wl-empty"><div class="wl-empty-mark">◎</div>'
            '<strong>等待一次决策</strong><p>预览模型路由，或执行完整推理。</p></div>'
        )
        return

    result_tab, route_tab, json_tab, code_tab = st.tabs(("结果", "路由", "JSON", "代码"))
    with result_tab:
        if response_kind == "route":
            selected = html.escape(str(response.get("selected_model", "—")))
            reason = html.escape(str(response.get("reason") or "未提供选择依据"))
            st.html(
                '<section class="wl-route-result"><span>已选模型</span>'
                f"<strong>{selected}</strong><p>{reason}</p></section>"
            )
        else:
            answers = response.get("answers", {})
            for question_id, answer in answers.items():
                if isinstance(answer, dict):
                    _answer_card(str(question_id), answer)
            meta = response.get("meta", {})
            metrics = st.columns(3)
            metrics[0].metric("模型", response.get("model", "—"))
            metrics[1].metric("设备", meta.get("device", "—"))
            metrics[2].metric("耗时", f"{_safe_number(meta.get('elapsed_ms')):.1f} ms")
    with route_tab:
        route_data = response if response_kind == "route" else response.get("routing", {})
        st.json(route_data)
    with json_tab:
        request_col, response_col = st.columns(2)
        with request_col:
            st.caption("请求")
            st.json(payload)
        with response_col:
            st.caption("响应")
            st.json(response)
    with code_tab:
        curl_tab, python_tab = st.tabs(("curl", "Python"))
        with curl_tab:
            st.code(request_as_curl(st.session_state.api_url, payload), language="bash")
        with python_tab:
            st.code(request_as_python(st.session_state.api_url, payload), language="python")


def _record_history(kind: str, payload: dict[str, Any], response: dict[str, Any]) -> None:
    selected_model = response.get("selected_model") or response.get("model") or "—"
    elapsed = response.get("meta", {}).get("elapsed_ms") if kind == "predict" else None
    entry = {
        "id": datetime.now().strftime("%H:%M:%S.%f"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "kind": kind,
        "scenario": SCENARIOS_BY_ID[st.session_state.scenario_id].name,
        "model": selected_model,
        "elapsed_ms": elapsed,
        "payload": deepcopy(payload),
        "response": deepcopy(response),
    }
    st.session_state.history = [entry, *st.session_state.history][:10]


def _execute(kind: str, payload: dict[str, Any]) -> None:
    st.session_state.last_error = None
    try:
        with st.status(
            "正在预览路由…" if kind == "route" else "正在执行决策…",
            expanded=True,
        ) as status:
            st.write("连接 WindLaya API")
            client = _client()
            if kind == "route":
                st.write("分析语言与模型选择")
                response = client.route(payload)
            else:
                st.write("加载模型并执行推理，首次运行可能需要更长时间")
                response = client.predict(payload)
            status.update(label="请求完成", state="complete", expanded=False)
        st.session_state.response = response
        st.session_state.response_kind = kind
        _record_history(kind, payload, response)
    except (PlaygroundApiError, ValueError) as exc:
        if isinstance(exc, PlaygroundApiError):
            st.session_state.last_error = exc
        else:
            st.session_state.last_error = PlaygroundApiError(str(exc), code="INVALID_REQUEST")
        st.session_state.response = None
        st.session_state.response_kind = None
    _refresh_health()


def _render_styles() -> None:
    st.html(
        """
        <style>
        .wl-brand {display:flex;align-items:center;gap:14px;margin:2px 0 18px;padding-bottom:16px;
          border-bottom:1px solid var(--border-color,rgba(128,128,128,.28));}
        .wl-mark {display:grid;place-items:center;width:42px;height:42px;border-radius:8px;
          background:var(--primary-color,#087e6a);color:white;font-weight:800;font-size:22px;}
        .wl-brand h1 {font-size:1.42rem;margin:0;letter-spacing:0;line-height:1.15;}
        .wl-brand p {margin:3px 0 0;opacity:.66;font-size:.86rem;}
        .wl-status {display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 14px;margin-bottom:18px;
          border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:7px;
          background:var(--secondary-background-color,rgba(128,128,128,.06));font-size:.85rem;}
        .wl-dot {width:8px;height:8px;border-radius:50%;background:#d25547;box-shadow:0 0 0 4px rgba(210,85,71,.12);}
        .wl-dot.ok {background:#159a7f;box-shadow:0 0 0 4px rgba(21,154,127,.14);}
        .wl-status strong {font-weight:700}.wl-status span {opacity:.76}
        .wl-empty {min-height:340px;display:flex;flex-direction:column;align-items:center;justify-content:center;
          text-align:center;border:1px dashed var(--border-color,rgba(128,128,128,.4));border-radius:8px;}
        .wl-empty-mark {font-size:3rem;color:var(--primary-color,#087e6a);line-height:1;margin-bottom:16px;}
        .wl-empty p {margin:6px 0;opacity:.62}
        .wl-answer {border:1px solid var(--border-color,rgba(128,128,128,.28));border-radius:8px;
          padding:16px;margin:0 0 12px;background:var(--background-color,transparent);}
        .wl-answer-head {display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:16px;}
        .wl-answer-id {font-family:var(--font,"sans-serif");font-size:.82rem;opacity:.62;margin-bottom:4px;}
        .wl-answer-value {font-size:1.25rem;font-weight:750;line-height:1.3;overflow-wrap:anywhere;}
        .wl-confidence {font-size:.72rem;text-align:right;opacity:.66;white-space:nowrap;}
        .wl-confidence strong {font-size:.92rem;opacity:1;}
        .wl-prob-row {display:grid;grid-template-columns:minmax(70px,1fr) 3fr 52px;gap:10px;align-items:center;
          margin:8px 0;font-size:.8rem;}.wl-prob-label {overflow-wrap:anywhere;opacity:.72}
        .wl-prob-label.active {font-weight:750;opacity:1;color:var(--primary-color,#087e6a)}
        .wl-prob-track,.wl-binary-track {height:8px;border-radius:3px;background:var(--secondary-background-color,#e7ebe8);overflow:hidden;}
        .wl-prob-track span,.wl-binary-track span {display:block;height:100%;background:var(--primary-color,#087e6a);}
        .wl-prob-value {font-variant-numeric:tabular-nums;text-align:right;}
        .wl-binary-track {height:12px;background:linear-gradient(90deg,rgba(232,101,74,.18),rgba(8,126,106,.18));}
        .wl-binary-track span {background:#e8654a;}.wl-binary-scale {display:flex;justify-content:space-between;
          font-size:.72rem;opacity:.58;margin-top:5px;}
        .wl-route-result {border-left:4px solid var(--primary-color,#087e6a);padding:14px 18px;
          background:var(--secondary-background-color,rgba(128,128,128,.06));border-radius:0 7px 7px 0;}
        .wl-route-result span {display:block;font-size:.78rem;opacity:.62}.wl-route-result strong {font-size:1.45rem;}
        .wl-route-result p {margin:8px 0 0;opacity:.72;overflow-wrap:anywhere;}
        @media (max-width: 700px) {.wl-prob-row {grid-template-columns:80px 1fr 48px}.wl-status {gap:8px}}
        @media (prefers-reduced-motion: reduce) {* {scroll-behavior:auto!important;transition:none!important}}
        </style>
        """
    )


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 场景")
        scenario_names = {scenario.id: scenario.name for scenario in SCENARIOS}
        selected = st.selectbox(
            "示例场景",
            scenario_names,
            index=list(scenario_names).index(st.session_state.scenario_id),
            format_func=scenario_names.get,
        )
        st.caption(SCENARIOS_BY_ID[selected].description)
        if st.button("载入场景", icon=":material/file_open:", use_container_width=True):
            _load_payload(scenario_payload(selected), scenario_id=selected)
            st.rerun()

        st.divider()
        st.markdown("### 连接")
        api_url = st.text_input("API 地址", value=st.session_state.api_url)
        if api_url != st.session_state.api_url:
            st.session_state.api_url = api_url
            st.session_state.health = None
        if st.button("测试连接", icon=":material/refresh:", use_container_width=True):
            _refresh_health()
            st.rerun()

        st.divider()
        st.markdown("### 最近执行")
        history = st.session_state.history
        if not history:
            st.caption("当前会话还没有执行记录。")
        else:
            labels = {
                entry["id"]: (
                    f"{entry['time']} · {'推理' if entry['kind'] == 'predict' else '路由'} · "
                    f"{entry['model']}"
                )
                for entry in history
            }
            selected_history = st.selectbox(
                "执行记录",
                labels,
                format_func=labels.get,
                label_visibility="collapsed",
            )
            if st.button("重新载入", icon=":material/history:", use_container_width=True):
                entry = next(item for item in history if item["id"] == selected_history)
                _load_payload(entry["payload"])
                st.session_state.response = deepcopy(entry["response"])
                st.session_state.response_kind = entry["kind"]
                st.rerun()


_initialize_state()
_render_styles()
if st.session_state.health is None and st.session_state.health_error is None:
    _refresh_health()
_render_sidebar()

st.html(
    '<header class="wl-brand"><div class="wl-mark">W</div><div>'
    '<h1>WindLaya Playground</h1><p>把上下文转化为可解释的即时决策</p></div></header>'
)

health = st.session_state.health
if health:
    loaded = ", ".join(health.get("loaded_models", [])) or "暂无"
    status_html = (
        '<div class="wl-status"><i class="wl-dot ok"></i><strong>服务在线</strong>'
        f'<span>设备 {html.escape(str(health.get("device", "—")))}</span>'
        f'<span>默认模型 {html.escape(str(health.get("default_model", "—")))}</span>'
        f'<span>已加载 {html.escape(loaded)}</span></div>'
    )
else:
    status_html = (
        '<div class="wl-status"><i class="wl-dot"></i><strong>服务离线</strong>'
        f'<span>{html.escape(str(st.session_state.health_error or "等待连接"))}</span></div>'
    )
st.html(status_html)

request_column, result_column = st.columns([5, 6], gap="large")
with request_column:
    st.markdown("### 决策请求")
    mode = st.segmented_control(
        "编辑模式",
        ("可视化", "JSON"),
        key="editor_mode",
        label_visibility="collapsed",
    )
    current_payload = deepcopy(st.session_state.payload)
    editor_error: str | None = None
    if mode == "JSON":
        parsed_payload, editor_error = _json_editor(current_payload)
        if parsed_payload is not None:
            current_payload = parsed_payload
    else:
        current_payload = _visual_editor(current_payload)
        editor_error = st.session_state.editor_error

    action_a, action_b = st.columns(2)
    preview = action_a.button(
        "预览路由",
        icon=":material/alt_route:",
        use_container_width=True,
        disabled=editor_error is not None,
    )
    predict = action_b.button(
        "执行决策",
        icon=":material/play_arrow:",
        type="primary",
        use_container_width=True,
        disabled=editor_error is not None,
    )
    if preview or predict:
        _execute("route" if preview else "predict", current_payload)
        st.rerun()

with result_column:
    _render_result(current_payload)
