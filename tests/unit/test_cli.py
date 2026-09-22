from typing import Any

import pytest

from app import cli


@pytest.mark.parametrize(
    ("system", "expected_hint"),
    [
        ("Windows", "NVIDIA driver and PyTorch CUDA support"),
        ("Darwin", "WINDLAYA_DEVICE=mps on Apple silicon"),
    ],
)
def test_desktop_environment_failure_is_reported_as_a_normal_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    system: str,
    expected_hint: str,
) -> None:
    def fail_startup(settings: Any) -> Any:
        raise cli.DesktopEnvironmentError("requested accelerator is unavailable")

    monkeypatch.setattr(cli.platform, "system", lambda: system)
    monkeypatch.setattr(cli, "_create_preloaded_app", fail_startup)
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda *args, **kwargs: pytest.fail("Uvicorn must not start"),
    )

    assert cli.main() == 0
    message = capsys.readouterr().err
    platform_name = "Windows" if system == "Windows" else "macOS"
    assert f"the {platform_name} environment is not ready" in message
    assert "Reason: requested accelerator is unavailable" in message
    assert expected_hint in message
    assert "exited normally" in message


def test_desktop_environment_success_starts_the_preloaded_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = object()
    calls: list[tuple[Any, dict[str, Any]]] = []
    monkeypatch.setattr(cli.platform, "system", lambda: "Windows")
    monkeypatch.setattr(cli, "_create_preloaded_app", lambda settings: application)
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda target, **kwargs: calls.append((target, kwargs)),
    )

    assert cli.main() == 0
    assert calls == [
        (
            application,
            {"host": "127.0.0.1", "port": 8000, "workers": 1},
        )
    ]


def test_linux_keeps_the_standard_fail_fast_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, dict[str, Any]]] = []
    monkeypatch.setattr(cli.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda target, **kwargs: calls.append((target, kwargs)),
    )

    assert cli.main() == 0
    assert calls == [
        (
            "app.main:app",
            {"host": "127.0.0.1", "port": 8000, "workers": 1},
        )
    ]
