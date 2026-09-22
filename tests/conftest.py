"""Shared test fixtures intentionally contain no model-loading side effects."""

import pytest


@pytest.fixture
def multilingual_questions() -> dict:
    return {
        "intent": {
            "type": "choice",
            "instructions": "判断用户主要诉求",
            "criteria": {
                "refund": "退款",
                "technical": "技术支持",
                "sales": "销售咨询",
                "other": "其他",
            },
        },
        "urgency": {
            "type": "score",
            "instructions": "判断请求紧急程度",
            "criteria": ["不紧急", "一般", "比较紧急", "非常紧急"],
        },
        "refund_requested": {
            "type": "noul",
            "instructions": "用户是否明确要求退款？",
        },
    }
