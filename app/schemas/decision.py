"""Validated decision request types."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    """Base model that rejects misspelled public fields."""

    model_config = ConfigDict(extra="forbid")


class QuestionBase(ApiModel):
    instructions: str

    @field_validator("instructions")
    @classmethod
    def validate_instructions(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("instructions must not be empty")
        return value


class ChoiceQuestion(QuestionBase):
    type: Literal["choice"]
    criteria: dict[str, Any] = Field(min_length=2)

    @field_validator("criteria", mode="before")
    @classmethod
    def normalize_labels(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized: dict[str, Any] = {}
        for raw_label, criterion in value.items():
            if not isinstance(raw_label, str) or not raw_label.strip():
                raise ValueError("choice labels must be non-empty strings")
            label = raw_label.strip()
            if label in normalized:
                raise ValueError("choice labels must be unique after trimming")
            normalized[label] = criterion
        return normalized


class ScoreQuestion(QuestionBase):
    type: Literal["score"]
    criteria: list[Any] = Field(min_length=2)


class NoulQuestion(QuestionBase):
    type: Literal["noul"]
    criteria: dict[Literal["false", "true"], Any] | None = None


Question = Annotated[
    ChoiceQuestion | ScoreQuestion | NoulQuestion,
    Field(discriminator="type"),
]
State = str | dict[str, Any] | list[Any]


class DecisionRequest(ApiModel):
    """A state and one or more typed questions to route or predict."""

    state: State
    questions: dict[str, Question] = Field(min_length=1)
    model: str = "auto"
    lang: str | None = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: State) -> State:
        if isinstance(value, str) and not value.strip():
            raise ValueError("state must not be an empty string")
        return value

    @field_validator("questions", mode="before")
    @classmethod
    def normalize_question_ids(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized: dict[str, object] = {}
        for raw_id, question in value.items():
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise ValueError("question IDs must be non-empty strings")
            question_id = raw_id.strip()
            if question_id in normalized:
                raise ValueError("question IDs must be unique after trimming")
            normalized[question_id] = question
        return normalized

    @field_validator("model")
    @classmethod
    def validate_model_text(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("model must not be empty")
        return value

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or any(character.isspace() for character in value):
            raise ValueError("lang must be a non-empty language hint without whitespace")
        return value

    def laya_questions(self) -> dict[str, dict[str, Any]]:
        """Render questions in the dictionary shape accepted by Laya."""
        return {
            question_id: question.model_dump(exclude_none=True)
            for question_id, question in self.questions.items()
        }
