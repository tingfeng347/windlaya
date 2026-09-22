from pathlib import Path
from typing import Any

from app import model_cli
from app.core.model_artifacts import DownloadedArtifact


def test_download_command_defaults_to_all_models_and_accepts_overrides(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    observed: dict[str, Any] = {}

    class FakeProvider:
        def __init__(self, settings: Any) -> None:
            observed["settings"] = settings

        def download(self, names: tuple[str, ...]) -> list[DownloadedArtifact]:
            observed["names"] = names
            return [DownloadedArtifact("english", tmp_path / "english", "huggingface", "abc")]

    monkeypatch.setattr(model_cli, "ModelArtifactProvider", FakeProvider)

    result = model_cli.main(
        [
            "download",
            "--root",
            str(tmp_path),
            "--source",
            "huggingface",
            "--fallback",
            "none",
        ]
    )

    assert result == 0
    assert observed["names"] == ("english", "multilingual", "typed-decisions")
    settings = observed["settings"]
    assert settings.model_root == tmp_path
    assert settings.model_source == "huggingface"
    assert settings.model_fallback_source == "none"
    assert "prepared english" in capsys.readouterr().out
