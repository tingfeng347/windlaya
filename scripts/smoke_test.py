"""Run real Laya checkpoint smoke tests without starting an HTTP server."""

import argparse
import json
import sys
import time
from typing import Any

from app.core.config import Settings
from app.core.model_manager import ModelManager

QUESTIONS = {
    "intent": {
        "type": "choice",
        "instructions": "判断用户主要诉求",
        "criteria": {
            "refund": "退款、退钱或撤销扣款",
            "technical": "软件、系统或网络问题",
            "sales": "价格、套餐或采购咨询",
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


def _cases(model: str | None) -> list[tuple[str, Any, str]]:
    if model:
        state = (
            "我的账户昨天被扣了两次款，请尽快退款。"
            if model in {"auto", "multilingual"}
            else "I was charged twice. Please refund the duplicate payment."
        )
        expected = "multilingual" if model == "auto" else model
        return [(model, state, expected)]
    return [
        ("auto", "我的账户昨天被扣了两次款，请尽快退款。", "multilingual"),
        ("auto", "I was charged twice. Please refund the duplicate payment.", "english"),
        ("multilingual", "我的账户昨天被扣了两次款，请尽快退款。", "multilingual"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["auto", "english", "multilingual", "typed-decisions"])
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    args = parser.parse_args()

    preload = "" if args.model in (None, "auto") else args.model
    settings = Settings(
        device=args.device,
        preload_models=preload,
        max_loaded=2,
        _env_file=None,
    )
    manager = ModelManager(settings)
    failures = 0
    try:
        manager.startup()
        for model, state, expected in _cases(args.model):
            started = time.perf_counter()
            result = manager.predict(state, QUESTIONS, model=model)
            elapsed_ms = (time.perf_counter() - started) * 1000
            selected = result["routing"]["model"]
            passed = selected == expected or args.model == "typed-decisions"
            failures += int(not passed)
            print("PASS" if passed else "FAIL")
            print(f"selected model: {selected}")
            print(f"elapsed_ms: {elapsed_ms:.3f}")
            print("answers:", json.dumps(result["answers"], ensure_ascii=False))
    except Exception as exc:
        failures += 1
        print(f"FAIL: {exc}", file=sys.stderr)
    finally:
        manager.shutdown()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
