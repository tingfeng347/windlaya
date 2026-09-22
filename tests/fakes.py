from typing import Any


class FakeAgent:
    def __init__(self, device: str = "cpu") -> None:
        self.device = device


class FakeRouter:
    """Small Laya boundary fake; it never downloads or runs a model."""

    def __init__(self, *, device: str = "cpu", **_: Any) -> None:
        self.device = device
        self._agents: dict[str, FakeAgent] = {}
        self.loaded: list[str] = []
        self.forward_calls = 0

    def preload(self, names: list[str]) -> None:
        for name in names:
            self.load(name)

    def load(self, name: str) -> FakeAgent:
        if name not in self._agents:
            self._agents[name] = FakeAgent(self.device)
            self.loaded.append(name)
        return self._agents[name]

    def unload(self, name: str | None = None) -> None:
        if name is None:
            self._agents.clear()
            self.loaded.clear()
        elif name in self._agents:
            self._agents.pop(name)
            self.loaded.remove(name)

    def route(
        self,
        state: Any,
        questions: dict[str, Any],
        model: str | None = None,
        lang: str | None = None,
    ) -> dict[str, Any]:
        if model:
            selected = model
            reason = f"explicit model={model!r}"
            detection = None
        elif lang:
            selected = "english" if lang.lower().startswith("en") else "multilingual"
            reason = f"explicit lang={lang!r}"
            detection = None
        else:
            text = str(state)
            selected = "multilingual" if any(ord(char) > 127 for char in text) else "english"
            reason = "fake language detection"
            detection = {"language": "zh" if selected == "multilingual" else "en"}
        return {
            "model": selected,
            "repo": f"fake/{selected}",
            "reason": reason,
            "detection": detection,
            "workflow": None,
        }

    def predict(
        self,
        state: Any,
        questions: dict[str, Any],
        model: str | None = None,
        lang: str | None = None,
    ) -> dict[str, Any]:
        self.forward_calls += 1
        routing = self.route(state, questions, model=model, lang=lang)
        self.load(routing["model"])
        return {
            "model": "laya-rl-agent",
            "answers": {
                question_id: {"type": question["type"]}
                for question_id, question in questions.items()
            },
            "usage": {"input_tokens": 7, "output_tokens": 0},
            "routing": routing,
        }
