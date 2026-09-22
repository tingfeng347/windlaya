import pytest
from pydantic import ValidationError

from app.schemas.decision import DecisionRequest


def test_decision_request_accepts_all_primitives_and_normalizes_identifiers() -> None:
    request = DecisionRequest.model_validate(
        {
            "state": {"message": "请退款"},
            "questions": {
                " intent ": {
                    "type": "choice",
                    "instructions": " 判断诉求 ",
                    "criteria": {" refund ": "退款", "other": "其他"},
                },
                "urgency": {
                    "type": "score",
                    "instructions": "判断紧急度",
                    "criteria": ["一般", "紧急"],
                },
                "refund": {
                    "type": "noul",
                    "instructions": "是否要求退款",
                    "criteria": {"false": "没有要求", "true": "明确要求"},
                },
            },
        }
    )

    assert tuple(request.questions) == ("intent", "urgency", "refund")
    assert request.questions["intent"].criteria == {"refund": "退款", "other": "其他"}
    assert request.questions["intent"].instructions == "判断诉求"

    with pytest.raises(ValidationError, match="at least 2"):
        DecisionRequest.model_validate(
            {
                "state": "hello",
                "questions": {
                    "intent": {
                        "type": "choice",
                        "instructions": "Choose",
                        "criteria": {"only": "one option"},
                    }
                },
            }
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"state": "hello", "questions": {}},
            "at least 1",
        ),
        (
            {
                "state": "hello",
                "questions": {
                    "urgency": {
                        "type": "score",
                        "instructions": "Urgency",
                        "criteria": [],
                    }
                },
            },
            "at least 2",
        ),
        (
            {
                "state": "hello",
                "questions": {
                    "refund": {"type": "noul", "instructions": "   "}
                },
            },
            "instructions must not be empty",
        ),
        (
            {
                "state": "hello",
                "questions": {
                    "refund": {
                        "type": "noul",
                        "instructions": "Refund?",
                        "criteria": {"maybe": "unknown"},
                    }
                },
            },
            "false",
        ),
    ],
)
def test_decision_request_rejects_invalid_public_shapes(
    payload: dict, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        DecisionRequest.model_validate(payload)
