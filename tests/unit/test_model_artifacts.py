import hashlib
import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.errors import ModelLoadError
from app.core.model_artifacts import ModelArtifactProvider
from app.core.model_manifest import ArtifactFile, ModelArtifactSpec


def _spec(content: bytes = b"checkpoint") -> ModelArtifactSpec:
    return ModelArtifactSpec(
        name="multilingual",
        huggingface_repo="upstream/multilingual",
        huggingface_revision="hf-commit",
        modelscope_repo="mirror/multilingual",
        modelscope_revision="ms-commit",
        files=(
            ArtifactFile(
                path="model.safetensors",
                sha256=hashlib.sha256(content).hexdigest(),
                size=len(content),
            ),
        ),
    )


def test_download_uses_modelscope_then_huggingface_fallback_and_publishes(
    tmp_path: Path,
) -> None:
    attempts: list[tuple[str, str, str | None]] = []

    def fail_modelscope(spec: ModelArtifactSpec, destination: Path, token: str | None) -> None:
        attempts.append(("modelscope", spec.modelscope_revision, token))
        raise OSError("mirror unavailable")

    def download_huggingface(spec: ModelArtifactSpec, destination: Path, token: str | None) -> None:
        attempts.append(("huggingface", spec.huggingface_revision, token))
        (destination / "model.safetensors").write_bytes(b"checkpoint")

    settings = Settings(
        model_root=tmp_path,
        hf_token="hf-secret",
        ms_token="ms-secret",
        _env_file=None,
    )
    provider = ModelArtifactProvider(
        settings,
        specs={"multilingual": _spec()},
        downloaders={
            "modelscope": fail_modelscope,
            "huggingface": download_huggingface,
        },
    )

    [result] = provider.download(("multilingual",))

    assert result.source == "huggingface"
    assert result.revision == "hf-commit"
    assert result.path == tmp_path / "multilingual"
    assert attempts == [
        ("modelscope", "ms-commit", "ms-secret"),
        ("huggingface", "hf-commit", "hf-secret"),
    ]
    provider.require(("multilingual",))
    assert provider.router_models()["multilingual"] == str(tmp_path / "multilingual")


def test_download_rejects_a_hash_mismatch_without_publishing(tmp_path: Path) -> None:
    def corrupt_download(spec: ModelArtifactSpec, destination: Path, token: str | None) -> None:
        (destination / "model.safetensors").write_bytes(b"corrupted!")

    settings = Settings(
        model_root=tmp_path,
        model_fallback_source="none",
        _env_file=None,
    )
    provider = ModelArtifactProvider(
        settings,
        specs={"multilingual": _spec()},
        downloaders={"modelscope": corrupt_download},
    )

    with pytest.raises(ModelLoadError, match="wrong size|SHA256 mismatch"):
        provider.download(("multilingual",))

    assert not (tmp_path / "multilingual").exists()


def test_runtime_requires_a_prepared_local_artifact(tmp_path: Path) -> None:
    provider = ModelArtifactProvider(
        Settings(model_root=tmp_path, _env_file=None),
        specs={"multilingual": _spec()},
    )

    with pytest.raises(ModelLoadError, match="windlaya-models download"):
        provider.require(("multilingual",))


def test_download_normalizes_laya_mutable_tokenizer_config(tmp_path: Path) -> None:
    source = json.dumps(
        {"extra_special_tokens": ["<start>", "<end>"]},
        separators=(",", ":"),
    ).encode()
    runtime = json.dumps(
        {"extra_special_tokens": {"extra_0": "<start>", "extra_1": "<end>"}},
        indent=2,
    ).encode()
    spec = ModelArtifactSpec(
        name="multilingual",
        huggingface_repo="upstream/multilingual",
        huggingface_revision="hf-commit",
        modelscope_repo="mirror/multilingual",
        modelscope_revision="ms-commit",
        files=(
            ArtifactFile(
                path="tokenizer/tokenizer_config.json",
                sha256=hashlib.sha256(source).hexdigest(),
                size=len(source),
                runtime_sha256=hashlib.sha256(runtime).hexdigest(),
                runtime_size=len(runtime),
            ),
        ),
    )

    def download(spec: ModelArtifactSpec, destination: Path, token: str | None) -> None:
        tokenizer = destination / "tokenizer"
        tokenizer.mkdir()
        (tokenizer / "tokenizer_config.json").write_bytes(source)

    provider = ModelArtifactProvider(
        Settings(
            model_root=tmp_path,
            model_fallback_source="none",
            _env_file=None,
        ),
        specs={"multilingual": spec},
        downloaders={"modelscope": download},
    )

    provider.download(("multilingual",))

    config_path = tmp_path / "multilingual" / "tokenizer" / "tokenizer_config.json"
    assert config_path.read_bytes() == runtime
    provider.require(("multilingual",))
    provider.verify(("multilingual",))
