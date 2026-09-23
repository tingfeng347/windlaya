"""Pure presentation helpers shared by the Streamlit page and tests."""

from __future__ import annotations

import json
from typing import Any


def parse_state(value: str, structured: bool) -> str | dict[str, Any] | list[Any]:
    if not structured:
        if not value.strip():
            raise ValueError("状态不能为空。")
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"状态 JSON 无效：第 {exc.lineno} 行第 {exc.colno} 列。") from exc
    if not isinstance(parsed, (dict, list)):
        raise ValueError("结构化状态必须是 JSON 对象或数组。")
    return parsed


def parse_choice_criteria(value: str) -> dict[str, str | None]:
    criteria: dict[str, str | None] = {}
    for line_number, raw_line in enumerate(value.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        label, separator, description = line.partition(":")
        label = label.strip()
        if not separator or not label:
            raise ValueError(f"选项第 {line_number} 行应使用“标识: 说明”格式。")
        if label in criteria:
            raise ValueError(f"选项标识“{label}”重复。")
        criteria[label] = description.strip() or None
    if len(criteria) < 2:
        raise ValueError("choice 至少需要两个选项。")
    return criteria


def parse_score_criteria(value: str) -> list[str]:
    criteria = [line.strip() for line in value.splitlines() if line.strip()]
    if len(criteria) < 2:
        raise ValueError("score 至少需要两个等级。")
    return criteria


def request_as_curl(base_url: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, indent=2).replace("'", "'\"'\"'")
    return (
        f"curl -X POST '{base_url.rstrip('/')}/v1/predict' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        f"  -d '{body}'"
    )


def request_as_python(base_url: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, indent=4)
    return (
        "import httpx\n\n"
        f"payload = {body}\n\n"
        f"response = httpx.post(\"{base_url.rstrip('/')}/v1/predict\", "
        "json=payload, timeout=300.0)\n"
        "response.raise_for_status()\n"
        "print(response.json())"
    )


def directional_conclusion(probability: float) -> str:
    return "倾向成立" if probability >= 0.5 else "倾向不成立"
