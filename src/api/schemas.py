from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.core.models import FinalDecision, OutputLanguage, ReviewMode, VenueCollection, VenueDomain
from src.services.review_jobs import ReviewJobStatus


class HealthResponse(BaseModel):
    status: str


class AppConfigResponse(BaseModel):
    supported_upload_extensions: list[str]
    max_upload_bytes: int
    default_output_language: OutputLanguage
    default_review_mode: ReviewMode


class LLMProviderConfigResponse(BaseModel):
    name: str
    type: str
    base_url_env: str
    api_key_env: str
    base_url_configured: bool
    api_key_configured: bool


class LLMModelConfigResponse(BaseModel):
    model_id: str
    provider: str
    provider_model_id: str
    max_attempts: int
    fallback_models: list[str] = Field(default_factory=list)


class LLMNodeConfigResponse(BaseModel):
    name: str
    primary_model: str
    max_attempts: int
    fallback_models: list[str] = Field(default_factory=list)


class LLMPromptRouteResponse(BaseModel):
    name: str
    model: str
    registered: bool
    provider: str = ""
    provider_model_id: str = ""


class LLMRuntimeConfigResponse(BaseModel):
    status: str
    mode: str
    config_path: str
    default_model: str = ""
    providers: list[LLMProviderConfigResponse] = Field(default_factory=list)
    models: list[LLMModelConfigResponse] = Field(default_factory=list)
    nodes: list[LLMNodeConfigResponse] = Field(default_factory=list)
    prompts: list[LLMPromptRouteResponse] = Field(default_factory=list)
    error_type: str = ""
    error_message: str = ""


class VenueCodesResponse(BaseModel):
    count: int
    codes: list[str]


class VenueCatalogEntry(BaseModel):
    code: str
    name: str
    source_path: str


class VenueCatalogResponse(BaseModel):
    count: int
    catalog: dict[VenueDomain, dict[VenueCollection, list[VenueCatalogEntry]]]


class ReviewCreate(BaseModel):
    paper_path: str
    review_mode: ReviewMode = ReviewMode.FULL_REVIEW
    output_language: OutputLanguage = OutputLanguage.ZH
    venue_domain: VenueDomain
    venue_collection: VenueCollection
    venue_code: str


class ArxivFetchCreate(BaseModel):
    arxiv_id: str


class FetchedPaperResponse(BaseModel):
    paper_path: str
    filename: str
    source_url: str
    pdf_url: str
    arxiv_id: str
    size_bytes: int


class ReviewPresetCreate(BaseModel):
    name: str = ""
    review_mode: ReviewMode
    output_language: OutputLanguage = OutputLanguage.ZH
    venue_domain: VenueDomain
    venue_collection: VenueCollection
    venue_code: str


class ReviewPresetResponse(BaseModel):
    preset_id: str
    name: str
    review_mode: ReviewMode
    output_language: OutputLanguage
    venue_domain: VenueDomain
    venue_collection: VenueCollection
    venue_code: str
    created_at: str
    updated_at: str


class ReviewPresetsResponse(BaseModel):
    count: int
    presets: list[ReviewPresetResponse]


class ReviewRequestResponse(BaseModel):
    paper_path: str
    review_mode: ReviewMode
    output_language: OutputLanguage
    venue_domain: VenueDomain | None = None
    venue_collection: VenueCollection | None = None
    venue_code: str


class ReviewRunResponse(BaseModel):
    run_id: str
    request: ReviewRequestResponse
    final_decision: FinalDecision
    decision_letter: str
    artifact_dir: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ReviewNodeSnapshotResponse(BaseModel):
    node: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str | None = None
    elapsed_ms: float | None = None
    error_type: str | None = None


class ReviewNodeEventResponse(BaseModel):
    event: str
    node: str
    timestamp: str
    elapsed_ms: float | None = None
    error_type: str | None = None


class ReviewJobProgressResponse(BaseModel):
    percent: int = 0
    completed_nodes: int = 0
    total_nodes: int = 0
    active_nodes: list[str] = Field(default_factory=list)
    next_node: str | None = None
    elapsed_ms: float | None = None


class ReviewJobResponse(BaseModel):
    job_id: str
    status: ReviewJobStatus
    request: ReviewRequestResponse
    created_at: str
    updated_at: str
    run_id: str = ""
    artifact_dir: str = ""
    final_decision: FinalDecision | None = None
    nodes: dict[str, ReviewNodeSnapshotResponse] = Field(default_factory=dict)
    node_events: list[ReviewNodeEventResponse] = Field(default_factory=list)
    progress: ReviewJobProgressResponse = Field(default_factory=ReviewJobProgressResponse)
    error: dict[str, Any] | None = None


class ReviewJobsResponse(BaseModel):
    count: int
    jobs: list[ReviewJobResponse]


class ReviewJobsSummaryResponse(BaseModel):
    count: int
    active_count: int
    queued_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    canceled_count: int
    latest_job_id: str = ""
    latest_status: ReviewJobStatus | None = None
    updated_at: str = ""


class ReviewArtifactResponse(BaseModel):
    name: str
    size_bytes: int
    content_type: str


class ReviewArtifactsResponse(BaseModel):
    job_id: str
    artifacts: list[ReviewArtifactResponse]


class ArtifactDeleteItem(BaseModel):
    job_id: str
    name: str


class ArtifactDeleteCreate(BaseModel):
    artifacts: list[ArtifactDeleteItem]


class ArtifactDeleteResult(BaseModel):
    job_id: str
    name: str
    deleted: bool


class ArtifactDeleteError(BaseModel):
    job_id: str
    name: str
    error_type: str
    message: str


class ArtifactDeleteResponse(BaseModel):
    deleted_count: int
    error_count: int
    deleted: list[ArtifactDeleteResult] = Field(default_factory=list)
    errors: list[ArtifactDeleteError] = Field(default_factory=list)


class RunDeleteCreate(BaseModel):
    job_ids: list[str]


class RunDeleteResult(BaseModel):
    job_id: str
    deleted: bool
    artifact_count: int


class RunDeleteError(BaseModel):
    job_id: str
    error_type: str
    message: str


class RunDeleteResponse(BaseModel):
    deleted_count: int
    error_count: int
    deleted: list[RunDeleteResult] = Field(default_factory=list)
    errors: list[RunDeleteError] = Field(default_factory=list)


class ReviewReportResponse(BaseModel):
    job_id: str
    name: str
    content_type: str
    content: str


class ReviewDiagnosticsResponse(BaseModel):
    job_id: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ReviewLLMCallEventResponse(BaseModel):
    timestamp: str = ""
    event: str
    kind: str | None = None
    prompt: str | None = None
    requested_model: str | None = None
    model: str | None = None
    provider: str | None = None
    provider_model: str | None = None
    attempt: int | None = None
    max_attempts: int | None = None
    fallback: str | None = None
    from_model: str | None = None
    to_model: str | None = None
    reason: str | None = None
    elapsed_ms: int | None = None
    error_type: str | None = None
    retryable: str | None = None
    system_chars: int | None = None
    user_chars: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    pricing_source: str | None = None


class ReviewLLMCallsResponse(BaseModel):
    job_id: str
    count: int
    events: list[ReviewLLMCallEventResponse]


class ReviewUsageSummaryResponse(BaseModel):
    job_id: str
    usage: dict[str, Any] = Field(default_factory=dict)


class LibraryArtifactResponse(ReviewArtifactResponse):
    job_id: str
    job_status: ReviewJobStatus
    run_id: str
    paper_path: str
    venue_domain: VenueDomain | None = None
    venue_collection: VenueCollection | None = None
    venue_code: str
    review_mode: ReviewMode
    output_language: OutputLanguage
    final_decision: FinalDecision | None = None
    updated_at: str
    download_url: str


class LibraryResponse(BaseModel):
    count: int
    artifacts: list[LibraryArtifactResponse]


class LibraryRunArtifactResponse(ReviewArtifactResponse):
    download_url: str


class LibraryRunResponse(BaseModel):
    job_id: str
    job_status: ReviewJobStatus
    run_id: str
    paper_path: str
    venue_domain: VenueDomain | None = None
    venue_collection: VenueCollection | None = None
    venue_code: str
    review_mode: ReviewMode
    output_language: OutputLanguage
    final_decision: FinalDecision | None = None
    created_at: str
    updated_at: str
    artifact_count: int
    report_count: int
    total_size_bytes: int
    primary_report_name: str = ""
    primary_report_download_url: str = ""
    artifacts: list[LibraryRunArtifactResponse] = Field(default_factory=list)


class LibraryRunsResponse(BaseModel):
    count: int
    artifact_count: int
    runs: list[LibraryRunResponse]
