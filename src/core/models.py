from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# 目前我们这里支持这个快速审稿模式和这个完全审稿模式
class ReviewMode(str, Enum):
    FULL_REVIEW = "FULL_REVIEW"
    QUICK_REVIEW = "QUICK_REVIEW"


class VenueDomain(str, Enum):
    CS = "CS"
    IS = "IS"


class VenueCollection(str, Enum):
    CCFA = "CCFA"
    CCFB = "CCFB"
    CCFC = "CCFC"
    FT50 = "FT50"
    UTD24 = "UTD24"


class FinalDecision(str, Enum):
    ACCEPT = "ACCEPT"
    MINOR_REVISION = "MINOR_REVISION"
    MAJOR_REVISION = "MAJOR_REVISION"
    REJECT = "REJECT"
    DESK_REJECT = "DESK_REJECT"


@dataclass(frozen=True)
class ParsedSection:
    heading: str
    text: str
    start_line: int


@dataclass(frozen=True)
class ParsedPaper:
    source_path: str
    title: str
    abstract: str
    full_text: str
    sections: list[ParsedSection] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VenueProfile:
    code: str
    name: str
    source_path: str
    profile_text: str


@dataclass(frozen=True)
class VenueCatalogItem:
    code: str
    name: str
    domain: VenueDomain
    venue_collection: VenueCollection
    source_path: str


@dataclass(frozen=True)
class ReviewRequest:
    paper_path: str
    review_mode: ReviewMode = ReviewMode.FULL_REVIEW
    venue_domain: VenueDomain | None = None
    venue_collection: VenueCollection | None = None
    venue_code: str = ""
    journal_name: str = ""
    journal_requirements_path: str = ""


@dataclass(frozen=True)
class ReviewFinding:
    location: str
    issue: str
    severity: str = "medium"


@dataclass(frozen=True)
class ReviewerReport:
    reviewer_key: str
    role: str
    summary: str
    strengths: list[str]
    weaknesses: list[ReviewFinding]
    rating: int
    rating_justification: str = ""
    recommendation: str = "MAJOR_REVISION"
    evidence_citations: list[str] = field(default_factory=list)
    strategic_advice: dict[str, Any] = field(default_factory=dict)
    raw_result: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewRun:
    run_id: str
    request: ReviewRequest
    parsed_paper: ParsedPaper
    venue_profile: VenueProfile | None
    stage_outputs: dict[str, Any]
    reviewer_reports: list[ReviewerReport]
    final_decision: FinalDecision
    decision_letter: str
    artifact_dir: str


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return value
