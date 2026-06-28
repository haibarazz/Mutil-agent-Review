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


class SingleReviewerOutput(ReviewerOutput):
    """单 Agent 审稿可以给审稿决定，但不能代替入口节点判断文件是否合法。"""

    final_decision: FinalDecision

    @field_validator("final_decision", mode="before")
    @classmethod
    def reject_non_review_decisions(cls, value: Any) -> Any:
        if str(value) in {FinalDecision.DESK_REJECT.value, FinalDecision.INVALID_SUBMISSION.value}:
            raise ValueError("single_reviewer must not return DESK_REJECT or INVALID_SUBMISSION")
        return value


class RevisionRoadmapOutput(BaseModel):
    """AE final 里的返修路线图。"""

    model_config = ConfigDict(extra="allow")

    must_fix: list[Any]
    should_fix: list[Any]
    nice_to_fix: list[Any]


class AEDecisionOutput(BaseModel):
    """AE decision 节点只负责裁决，不允许混入报告正文。"""

    model_config = ConfigDict(extra="forbid")

    final_decision: FinalDecision
    decision_rationale: str = Field(min_length=1)
    consensus_disagreement: dict[str, Any]
    critical_issues: list[Any]

    @field_validator("final_decision", mode="before")
    @classmethod
    def reject_desk_reject_for_ae_decision(cls, value: Any) -> Any:
        if str(value) in {FinalDecision.DESK_REJECT.value, FinalDecision.INVALID_SUBMISSION.value}:
            raise ValueError("ae_decision must not return DESK_REJECT or INVALID_SUBMISSION")
        return value


class AEReportOutput(BaseModel):
    """AE report 节点只写作者反馈，不允许重新做最终决定。"""

    model_config = ConfigDict(extra="forbid")

    decision_letter: str = Field(min_length=1)
    revision_checklist: list[Any] = Field(min_length=3)
    rr_traceability_matrix: list[Any] = Field(min_length=1)
    revision_roadmap: RevisionRoadmapOutput


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
        if str(value) in {FinalDecision.DESK_REJECT.value, FinalDecision.INVALID_SUBMISSION.value}:
            raise ValueError("ae_final must not return DESK_REJECT or INVALID_SUBMISSION")
        return value


def validate_reviewer_output(value: dict[str, Any], *, context: ErrorContext | None = None) -> dict[str, Any]:
    """校验 reviewer 输出，不改变原始 dict，方便后续继续保留 raw_result。"""
    return _validate_output(ReviewerOutput, value, context=context)


def validate_single_reviewer_output(value: dict[str, Any], *, context: ErrorContext | None = None) -> dict[str, Any]:
    """校验单 Agent 审稿输出，避免模型把入口文件类型判断混进审稿决定。"""
    return _validate_output(SingleReviewerOutput, value, context=context)


def validate_ae_decision_output(value: dict[str, Any], *, context: ErrorContext | None = None) -> dict[str, Any]:
    """校验 AE decision 输出，确保裁决节点不会写报告字段。"""
    return _validate_output(AEDecisionOutput, value, context=context)


def validate_ae_report_output(value: dict[str, Any], *, context: ErrorContext | None = None) -> dict[str, Any]:
    """校验 AE report 输出，确保报告节点不会重新裁决。"""
    return _validate_output(AEReportOutput, value, context=context)


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
