"""Application service for routing and executing decision requests."""

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any

from app.core.errors import InferenceError
from app.core.model_manager import ModelManager
from app.schemas.decision import ChoiceQuestion, DecisionRequest

logger = logging.getLogger(__name__)


class DecisionService:
    """Translate validated API requests into stable WindLaya responses."""

    def __init__(
        self,
        model_manager: ModelManager,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self.model_manager = model_manager
        self._clock = clock

    def route(self, request: DecisionRequest, request_id: str) -> dict[str, Any]:
        started = self._clock()
        questions = request.laya_questions()
        routing = self.model_manager.route(
            request.state,
            questions,
            model=request.model,
            lang=request.lang,
        )
        elapsed_ms = round((self._clock() - started) * 1000, 3)
        requested = "auto" if request.model == "auto" else str(routing["model"])
        self._log_result(request_id, "/v1/route", requested, routing, elapsed_ms, True)
        return {
            "request_id": request_id,
            "requested_model": requested,
            "selected_model": routing["model"],
            "reason": routing.get("reason"),
            "workflow": routing.get("workflow"),
            "detection": routing.get("detection"),
        }

    def predict(self, request: DecisionRequest, request_id: str) -> dict[str, Any]:
        started = self._clock()
        self._warn_high_cardinality_choices(request)
        raw = self.model_manager.predict(
            request.state,
            request.laya_questions(),
            model=request.model,
            lang=request.lang,
        )
        elapsed_ms = round((self._clock() - started) * 1000, 3)
        routing = raw.get("routing")
        answers = raw.get("answers")
        usage = raw.get("usage")
        valid_payload = (
            isinstance(routing, dict)
            and isinstance(answers, dict)
            and isinstance(usage, dict)
        )
        if not valid_payload:
            raise InferenceError("Laya returned an invalid prediction payload.")

        selected = str(routing.get("model", ""))
        self._log_result(
            request_id,
            "/v1/predict",
            request.model,
            routing,
            elapsed_ms,
            True,
        )
        return {
            "request_id": request_id,
            "model": selected,
            "routing": routing,
            "answers": answers,
            "usage": usage,
            "meta": {
                "api_version": "v1",
                "device": self.model_manager.device,
                "elapsed_ms": elapsed_ms,
            },
        }

    @staticmethod
    def _warn_high_cardinality_choices(request: DecisionRequest) -> None:
        for question_id, question in request.questions.items():
            if isinstance(question, ChoiceQuestion) and len(question.criteria) > 20:
                logger.warning(
                    "event=high_cardinality_choice question_id=%s option_count=%d message=%r",
                    question_id,
                    len(question.criteria),
                    "Laya accuracy may degrade with high-cardinality choices",
                )

    def _log_result(
        self,
        request_id: str,
        endpoint: str,
        requested_model: str,
        routing: dict[str, Any],
        elapsed_ms: float,
        success: bool,
    ) -> None:
        logger.info(
            "request_id=%s endpoint=%s requested_model=%s selected_model=%s "
            "device=%s elapsed_ms=%.3f success=%s",
            request_id,
            endpoint,
            requested_model,
            routing.get("model"),
            self.model_manager.device,
            elapsed_ms,
            str(success).lower(),
        )
