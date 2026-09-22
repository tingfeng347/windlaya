"""Measure in-process Laya routing and inference latency."""

import argparse
import statistics
import time

from app.core.config import Settings
from app.core.model_manager import ModelManager

QUESTION = {
    "refund": {
        "type": "noul",
        "instructions": "Does the user explicitly ask for a refund?",
    }
}


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * quantile))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        choices=["english", "multilingual", "typed-decisions"],
        required=True,
    )
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1 or args.warmup < 0:
        parser.error("--runs must be positive and --warmup must not be negative")

    settings = Settings(
        device=args.device,
        preload_models="",
        max_loaded=1,
        _env_file=None,
    )
    manager = ModelManager(settings)
    state = "Please refund my duplicate payment."
    try:
        manager.startup()
        for _ in range(max(1, args.warmup)):
            manager.predict(state, QUESTION, model=args.model)

        latencies: list[float] = []
        for _ in range(args.runs):
            started = time.perf_counter()
            manager.predict(state, QUESTION, model=args.model)
            latencies.append((time.perf_counter() - started) * 1000)
    finally:
        manager.shutdown()

    print(f"device: {manager.device}")
    print(f"model: {args.model}")
    print(f"runs: {args.runs}")
    print(f"mean latency: {statistics.mean(latencies):.3f} ms")
    print(f"p50: {percentile(latencies, 0.50):.3f} ms")
    print(f"p95: {percentile(latencies, 0.95):.3f} ms")
    print(f"min: {min(latencies):.3f} ms")
    print(f"max: {max(latencies):.3f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
