"""Prepare and verify local Laya model artifacts."""

import argparse
import sys
from pathlib import Path

from app.core.config import MODEL_NAMES, ModelName, Settings
from app.core.errors import ModelLoadError
from app.core.model_artifacts import ModelArtifactProvider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="download and verify pinned checkpoints")
    download.add_argument("--model", action="append", choices=MODEL_NAMES, dest="models")
    download.add_argument("--source", choices=["modelscope", "huggingface"])
    download.add_argument("--fallback", choices=["huggingface", "none"])
    download.add_argument("--root")

    verify = subparsers.add_parser("verify", help="fully verify local checkpoint hashes")
    verify.add_argument("--model", action="append", choices=MODEL_NAMES, dest="models")
    verify.add_argument("--root")
    verify.add_argument(
        "--publish-marker",
        action="store_true",
        help="mark verified local directories as runnable artifacts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings()
    updates: dict[str, object] = {}
    if args.root:
        updates["model_root"] = Path(args.root)
    if args.command == "download":
        if args.source:
            updates["model_source"] = args.source
        if args.fallback:
            updates["model_fallback_source"] = args.fallback
    if updates:
        settings = settings.model_copy(update=updates)

    names: tuple[ModelName, ...] = tuple(args.models or MODEL_NAMES)
    provider = ModelArtifactProvider(settings)
    try:
        if args.command == "download":
            for result in provider.download(names):
                print(
                    f"prepared {result.name}: {result.path} "
                    f"source={result.source} revision={result.revision}"
                )
        else:
            provider.verify(names, publish_marker=args.publish_marker)
            for name in names:
                print(f"verified {name}: {provider.router_models()[name]}")
    except (ModelLoadError, OSError, ValueError) as exc:
        print(f"windlaya-models: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
