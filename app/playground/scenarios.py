"""Editable request scenarios for the WindLaya playground."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExampleScenario:
    id: str
    name: str
    description: str
    payload: dict[str, Any]


SCENARIOS = (
    ExampleScenario(
        id="support-triage",
        name="客服分流",
        description="识别重复扣款诉求、紧急度与退款意向。",
        payload={
            "state": {"message": "我的账户昨天被扣了两次款，请尽快帮我退款。"},
            "model": "auto",
            "questions": {
                "intent": {
                    "type": "choice",
                    "instructions": "判断用户的主要诉求",
                    "criteria": {
                        "refund": "退款、退钱或撤销重复扣款",
                        "technical": "软件、系统或网络问题",
                        "sales": "价格、套餐或采购咨询",
                        "other": "其他诉求",
                    },
                },
                "urgency": {
                    "type": "score",
                    "instructions": "判断请求的紧急程度",
                    "criteria": ["不紧急", "一般", "比较紧急", "非常紧急"],
                },
                "refund_requested": {
                    "type": "noul",
                    "instructions": "用户是否明确要求退款？",
                },
            },
        },
    ),
    ExampleScenario(
        id="content-moderation",
        name="内容审核",
        description="判断内容风险、严重程度与是否需要人工处置。",
        payload={
            "state": {"post": "你们再不处理，我就把所有人的私人信息发到公开论坛。"},
            "model": "auto",
            "questions": {
                "privacy": {
                    "type": "noul",
                    "instructions": "是否包含泄露私人信息的行为？",
                },
                "severity": {
                    "type": "score",
                    "instructions": "判断内容违规风险的严重程度",
                    "criteria": [
                        "无风险：普通内容",
                        "轻微：不当但影响有限",
                        "明显违规：泄露隐私、骚扰或针对他人",
                        "严重风险：暴力威胁、仇恨或煽动伤害",
                    ],
                },
                "action": {
                    "type": "choice",
                    "instructions": "选择适合的处置方式",
                    "criteria": {
                        "allow": "正常放行",
                        "review": "交由人工复核",
                        "block": "阻止发布并记录",
                    },
                },
            },
        },
    ),
    ExampleScenario(
        id="multilingual-routing",
        name="多语言路由",
        description="用日文请求验证 auto 模式的 checkpoint 选择。",
        payload={
            "state": "昨日二重に請求されました。重複分を返金してください。",
            "model": "auto",
            "questions": {
                "intent": {
                    "type": "choice",
                    "instructions": "ユーザーの主な要望を分類してください",
                    "criteria": {
                        "refund": "返金または重複請求の取消",
                        "technical": "技術的な問題",
                        "other": "その他",
                    },
                },
                "refund_requested": {
                    "type": "noul",
                    "instructions": "ユーザーは返金を求めていますか？",
                },
            },
        },
    ),
    ExampleScenario(
        id="blank",
        name="空白请求",
        description="从一个最小的二元判断请求开始。",
        payload={
            "state": "",
            "model": "auto",
            "questions": {
                "decision": {
                    "type": "noul",
                    "instructions": "这个命题是否成立？",
                }
            },
        },
    ),
)

SCENARIOS_BY_ID = {scenario.id: scenario for scenario in SCENARIOS}


def scenario_payload(scenario_id: str) -> dict[str, Any]:
    return deepcopy(SCENARIOS_BY_ID[scenario_id].payload)
