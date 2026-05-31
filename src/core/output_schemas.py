from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from src.core.errors import ErrorContext, ModelOutputValidationError
from src.core.models import FinalDecision


class ReviewCommentOutput(BaseModel):
    """LLM 返回的单条 reviewer comment。"""

    model_config = ConfigDict(extra="allow")

    title: str = Field(min_length=1)
    comment: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    suggested_fix: str = Field(min_length=1)


class ReviewerScoresOutput(BaseModel):
    """Reviewer 评分字段；rating 是最终汇总最依赖的硬约束。"""

    model_config = ConfigDict(extra="allow")

    rating: int | float | str


class ReviewerOutput(BaseModel):
    """Reviewer / Devil's Advocate 的结构化输出协议。"""

    model_config = ConfigDict(extra="allow")

    summary: str = Field(min_length=1)
    strengths: list[str] = Field(min_length=2)
    major_comments: list[ReviewCommentOutput] = Field(min_length=3)
    minor_comments: list[ReviewCommentOutput] = Field(min_length=2)
    questions_for_authors: list[str] = Field(min_length=2)
    scores: ReviewerScoresOutput

    @model_validator(mode="after")
    def validate_total_comment_count(self) -> "ReviewerOutput":
        if len(self.major_comments) + len(self.minor_comments) < 5:
            raise ValueError("major_comments + minor_comments must contain at least 5 items")
        return self


class RevisionRoadmapOutput(BaseModel):
    """AE final 里的返修路线图。"""

    model_config = ConfigDict(extra="allow")

    must_fix: list[Any]
    should_fix: list[Any]
    nice_to_fix: list[Any]


class AEFinalOutput(BaseModel):
    """AE final 的结构化输出协议。"""

    model_config = ConfigDict(extra="allow")

    final_decision: FinalDecision
    decision_letter: str = Field(min_length=1)
    revision_checklist: list[Any] = Field(min_length=1)
    rr_traceability_matrix: list[Any]
    revision_roadmap: RevisionRoadmapOutput

    @field_validator("final_decision", mode="before")
    @classmethod
    def reject_desk_reject_for_ae_final(cls, value: Any) -> Any:
        if str(value) == FinalDecision.DESK_REJECT.value:
            raise ValueError("ae_final must not return DESK_REJECT")
        return value


def validate_reviewer_output(value: dict[str, Any], *, context: ErrorContext | None = None) -> dict[str, Any]:
    """校验 reviewer 输出，不改变原始 dict，方便后续继续保留 raw_result。"""
    return _validate_output(ReviewerOutput, value, context=context)


def validate_ae_final_output(value: dict[str, Any], *, context: ErrorContext | None = None) -> dict[str, Any]:
    """校验 AE final 输出，不改变原始 dict。"""
    return _validate_output(AEFinalOutput, value, context=context)


def _validate_output(
    schema: type[BaseModel],
    value: dict[str, Any],
    *,
    context: ErrorContext | None,
) -> dict[str, Any]:
    try:
        schema.model_validate(value)
    except ValidationError as exc:
        raise ModelOutputValidationError(
            _validation_message(exc),
            context=context or ErrorContext(),
        ) from exc
    return value


def _validation_message(exc: ValidationError) -> str:
    errors = []
    for item in exc.errors():
        loc = ".".join(str(part) for part in item.get("loc", ()))
        message = item.get("msg", "validation failed")
        errors.append(f"{loc}: {message}" if loc else str(message))
    return "; ".join(errors) or "model output validation failed"
