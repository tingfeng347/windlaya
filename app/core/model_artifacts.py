"""Download, verify, and publish immutable local Laya checkpoints."""

import hashlib
import json
import shutil
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from filelock import FileLock

from app.core.config import ModelName, ModelSource, Settings
from app.core.errors import ModelLoadError
from app.core.model_manifest import MODEL_ARTIFACTS, ModelArtifactSpec

MARKER_NAME = ".windlaya-artifact.json"
Downloader = Callable[[ModelArtifactSpec, Path, str | None], None]


class ArtifactProvider(Protocol):
    def router_models(self) -> dict[str, str]: ...

    def require(self, names: Iterable[str]) -> None: ...


@dataclass(frozen=True)
class DownloadedArtifact:
    name: str
    path: Path
    source: ModelSource
    revision: str


class ModelArtifactProvider:
    """Own the disk boundary between remote hubs and Laya local paths."""

    def __init__(
        self,
        settings: Settings,
        *,
        specs: dict[str, ModelArtifactSpec] | None = None,
        downloaders: dict[ModelSource, Downloader] | None = None,
    ) -> None:
        self.settings = settings
        self.root = settings.model_root.expanduser().resolve()
        self.specs = specs or MODEL_ARTIFACTS
        self._downloaders = downloaders or {
            "modelscope": _download_from_modelscope,
            "huggingface": _download_from_huggingface,
        }

    def router_models(self) -> dict[str, str]:
        return {name: str(self._model_path(name)) for name in self.specs}

    def require(self, names: Iterable[str]) -> None:
        for name in names:
            spec = self.specs[name]
            path = self._model_path(name)
            try:
                self._validate_published(path, spec)
            except ModelLoadError as exc:
                raise ModelLoadError(
                    f"Laya checkpoint {name!r} is not prepared at {str(path)!r}. "
                    "Run `uv run windlaya-models download` during build or deployment."
                ) from exc

    def download(self, names: Iterable[ModelName]) -> list[DownloadedArtifact]:
        if self.settings.model_source == "local":
            raise ModelLoadError("The local model source cannot download checkpoints; use verify.")
        self.root.mkdir(parents=True, exist_ok=True)
        return [self._download_one(self.specs[name]) for name in names]

    def verify(self, names: Iterable[ModelName], *, publish_marker: bool = False) -> None:
        for name in names:
            spec = self.specs[name]
            path = self._model_path(name)
            marker_path = path / MARKER_NAME
            if marker_path.exists():
                self._validate_marker(path, spec)
                self._verify_files(path, spec, runtime=True)
            else:
                self._verify_files(path, spec)
                if publish_marker:
                    self._prepare_runtime_files(path, spec)
                    self._verify_files(path, spec, runtime=True)
                    self._write_marker(path, spec, source="local", revision="local")

    def _download_one(self, spec: ModelArtifactSpec) -> DownloadedArtifact:
        target = self._model_path(spec.name)
        lock_path = self.root / ".locks" / f"{spec.name}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(lock_path):
            if target.exists():
                self._validate_published(target, spec)
                marker = self._read_marker(target)
                return DownloadedArtifact(
                    spec.name,
                    target,
                    marker["source"],
                    marker["source_revision"],
                )

            sources = [self.settings.model_source]
            fallback = self.settings.model_fallback_source
            if fallback != "none" and fallback not in sources:
                sources.append(fallback)

            failures: list[str] = []
            for source in sources:
                if source == "local":
                    continue
                staging = self.root / ".staging" / f"{spec.name}-{uuid.uuid4().hex}"
                staging.mkdir(parents=True, exist_ok=False)
                try:
                    self._downloaders[source](spec, staging, self._token_for(source))
                    self._verify_files(staging, spec)
                    self._prepare_runtime_files(staging, spec)
                    self._verify_files(staging, spec, runtime=True)
                    revision = self._revision_for(spec, source)
                    self._write_marker(staging, spec, source=source, revision=revision)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    staging.replace(target)
                    return DownloadedArtifact(spec.name, target, source, revision)
                except Exception as exc:
                    failures.append(f"{source}: {exc}")
                    shutil.rmtree(staging, ignore_errors=True)

            detail = "; ".join(failures)
            raise ModelLoadError(
                f"Failed to download Laya checkpoint {spec.name!r} "
                f"from configured sources: {detail}"
            )

    def _model_path(self, name: str) -> Path:
        return self.root / name

    def _token_for(self, source: ModelSource) -> str | None:
        secret = self.settings.ms_token if source == "modelscope" else self.settings.hf_token
        return secret.get_secret_value() if secret else None

    @staticmethod
    def _revision_for(spec: ModelArtifactSpec, source: ModelSource) -> str:
        if source == "modelscope":
            return spec.modelscope_revision
        if source == "huggingface":
            return spec.huggingface_revision
        return "local"

    def _validate_published(self, path: Path, spec: ModelArtifactSpec) -> None:
        self._validate_marker(path, spec)
        for expected in spec.files:
            candidate = path / expected.path
            runtime_size = expected.runtime_size or expected.size
            if not candidate.is_file() or candidate.stat().st_size != runtime_size:
                raise ModelLoadError(f"Artifact file is missing or has the wrong size: {candidate}")

    def _validate_marker(self, path: Path, spec: ModelArtifactSpec) -> None:
        marker = self._read_marker(path)
        if marker.get("model") != spec.name or marker.get("manifest") != _manifest_digest(spec):
            raise ModelLoadError(
                f"Artifact marker does not match the pinned manifest for {spec.name!r}."
            )

    @staticmethod
    def _read_marker(path: Path) -> dict[str, str]:
        marker_path = path / MARKER_NAME
        try:
            value = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelLoadError(f"Missing or invalid artifact marker: {marker_path}") from exc
        if not isinstance(value, dict):
            raise ModelLoadError(f"Invalid artifact marker: {marker_path}")
        return value

    @staticmethod
    def _verify_files(
        path: Path,
        spec: ModelArtifactSpec,
        *,
        runtime: bool = False,
    ) -> None:
        for expected in spec.files:
            candidate = path / expected.path
            expected_size = (
                expected.runtime_size if runtime and expected.runtime_size else expected.size
            )
            expected_sha256 = (
                expected.runtime_sha256 if runtime and expected.runtime_sha256 else expected.sha256
            )
            if not candidate.is_file():
                raise ModelLoadError(f"Required artifact file is missing: {candidate}")
            if candidate.stat().st_size != expected_size:
                raise ModelLoadError(f"Artifact file has the wrong size: {candidate}")
            digest = hashlib.sha256()
            with candidate.open("rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected_sha256:
                raise ModelLoadError(f"Artifact SHA256 mismatch: {candidate}")

    @staticmethod
    def _prepare_runtime_files(path: Path, spec: ModelArtifactSpec) -> None:
        for expected in spec.files:
            if expected.runtime_sha256 is None:
                continue
            candidate = path / expected.path
            config = json.loads(candidate.read_text(encoding="utf-8"))
            extra = config.get("extra_special_tokens")
            if isinstance(extra, list):
                config["extra_special_tokens"] = {
                    f"extra_{index}": token for index, token in enumerate(extra)
                }
            encoded = json.dumps(config, indent=2).encode()
            if (
                len(encoded) != expected.runtime_size
                or hashlib.sha256(encoded).hexdigest() != expected.runtime_sha256
            ):
                raise ModelLoadError(
                    f"Runtime normalization does not match the pinned manifest: {candidate}"
                )
            temporary = candidate.with_name(f"{candidate.name}.windlaya.tmp")
            temporary.write_bytes(encoded)
            temporary.replace(candidate)

    @staticmethod
    def _write_marker(
        path: Path,
        spec: ModelArtifactSpec,
        *,
        source: ModelSource,
        revision: str,
    ) -> None:
        marker = {
            "schema": 1,
            "model": spec.name,
            "manifest": _manifest_digest(spec),
            "source": source,
            "source_revision": revision,
        }
        marker_path = path / MARKER_NAME
        temporary = path / f"{MARKER_NAME}.tmp"
        temporary.write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(marker_path)


def _manifest_digest(spec: ModelArtifactSpec) -> str:
    payload = [
        {
            "path": item.path,
            "sha256": item.sha256,
            "size": item.size,
            "runtime_sha256": item.runtime_sha256,
            "runtime_size": item.runtime_size,
        }
        for item in spec.files
    ]
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _download_from_modelscope(
    spec: ModelArtifactSpec,
    destination: Path,
    token: str | None,
) -> None:
    from modelscope_hub.compat import snapshot_download

    snapshot_download(
        model_id=spec.modelscope_repo,
        revision=spec.modelscope_revision,
        local_dir=str(destination),
        allow_patterns=[item.path for item in spec.files],
        token=token,
    )


def _download_from_huggingface(
    spec: ModelArtifactSpec,
    destination: Path,
    token: str | None,
) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=spec.huggingface_repo,
        revision=spec.huggingface_revision,
        local_dir=str(destination),
        allow_patterns=[item.path for item in spec.files],
        token=token,
    )
