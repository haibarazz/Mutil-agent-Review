export type VenueCatalogResponse = {
  count: number;
  catalog: Record<"CS" | "IS", Partial<Record<VenueCatalogItem["venue_collection"], VenueCatalogItemFromApi[]>>>;
};

export type VenueCatalogItem = {
  code: string;
  name: string;
  domain: "CS" | "IS";
  venue_collection: "CCFA" | "CCFB" | "CCFC" | "FT50" | "UTD24";
  source_path: string;
};

export type VenueCatalogItemFromApi = Omit<VenueCatalogItem, "domain" | "venue_collection">;

export type ReviewMode = "FULL_REVIEW" | "QUICK_REVIEW" | "SINGLE_AGENT_REVIEW";
export type OutputLanguage = "zh" | "en";
export type ReviewJobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELED";
export type ReviewJobsFilter = "ALL" | "ACTIVE" | ReviewJobStatus;

export type ReviewRunResponse = {
  run_id: string;
  request: {
    paper_path: string;
    review_mode: ReviewMode;
    output_language: OutputLanguage;
    venue_domain: VenueCatalogItem["domain"];
    venue_collection: VenueCatalogItem["venue_collection"];
    venue_code: string;
  };
  final_decision: string;
  decision_letter: string;
  artifact_dir: string;
  diagnostics: {
    status?: string;
    errors?: unknown[];
    fallback_events?: unknown[];
  };
};

export type CreateReviewUploadInput = {
  paper: File;
  review_mode: ReviewMode;
  output_language: OutputLanguage;
  venue_domain: VenueCatalogItem["domain"];
  venue_collection: VenueCatalogItem["venue_collection"];
  venue_code: string;
};

export type CreateReviewPathInput = Omit<CreateReviewUploadInput, "paper"> & {
  paper_path: string;
};

export type FetchedPaperResponse = {
  paper_path: string;
  filename: string;
  source_url: string;
  pdf_url: string;
  arxiv_id: string;
  size_bytes: number;
};

export type ReviewPresetInput = {
  name?: string;
  review_mode: ReviewMode;
  output_language: OutputLanguage;
  venue_domain: VenueCatalogItem["domain"];
  venue_collection: VenueCatalogItem["venue_collection"];
  venue_code: string;
};

export type ReviewPresetResponse = Required<ReviewPresetInput> & {
  preset_id: string;
  created_at: string;
  updated_at: string;
};

export type ReviewPresetsResponse = {
  count: number;
  presets: ReviewPresetResponse[];
};

export type ReviewJobResponse = {
  job_id: string;
  status: ReviewJobStatus;
  request: ReviewRunResponse["request"];
  created_at: string;
  updated_at: string;
  run_id: string;
  artifact_dir: string;
  final_decision: string | null;
  nodes: Record<string, ReviewNodeSnapshot>;
  node_events: ReviewNodeEvent[];
  progress: ReviewJobProgress;
  error: {
    error_type?: string;
    message?: string;
    [key: string]: unknown;
  } | null;
};

export type ReviewJobProgress = {
  percent: number;
  completed_nodes: number;
  total_nodes: number;
  active_nodes: string[];
  next_node: string | null;
  elapsed_ms: number | null;
};

export type ReviewNodeSnapshot = {
  node: string;
  status: "RUNNING" | "SUCCEEDED" | "FAILED" | "UNKNOWN";
  started_at?: string;
  finished_at?: string;
  updated_at?: string;
  elapsed_ms?: number;
  error_type?: string;
};

export type ReviewNodeEvent = {
  event: "start" | "done" | "error" | string;
  node: string;
  timestamp: string;
  elapsed_ms?: number;
  error_type?: string;
};

export type ReviewArtifact = {
  name: string;
  size_bytes: number;
  content_type: string;
};

export type ReviewArtifactsResponse = {
  job_id: string;
  artifacts: ReviewArtifact[];
};

export type ArtifactDeleteItem = {
  job_id: string;
  name: string;
};

export type ArtifactDeleteResponse = {
  deleted_count: number;
  error_count: number;
  deleted: Array<ArtifactDeleteItem & { deleted: boolean }>;
  errors: Array<ArtifactDeleteItem & { error_type: string; message: string }>;
};

export type ReviewReportResponse = {
  job_id: string;
  name: string;
  content_type: string;
  content: string;
};

export type ReviewDiagnostics = {
  status?: string;
  errors?: Array<Record<string, unknown>>;
  fallback_events?: unknown[];
  llm_calls?: {
    event_count?: number;
    call_count?: number;
    error_count?: number;
    fallback_count?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type ReviewDiagnosticsResponse = {
  job_id: string;
  diagnostics: ReviewDiagnostics;
};

export type ReviewLLMCallEvent = {
  timestamp?: string;
  event: string;
  kind?: string | null;
  prompt?: string | null;
  requested_model?: string | null;
  model?: string | null;
  provider?: string | null;
  provider_model?: string | null;
  attempt?: number | null;
  max_attempts?: number | null;
  fallback?: string | null;
  from_model?: string | null;
  to_model?: string | null;
  reason?: string | null;
  elapsed_ms?: number | null;
  error_type?: string | null;
  error_message?: string | null;
  retryable?: string | null;
  next_action?: string | null;
  model_output_error_kind?: string | null;
  model_output_error_ref?: string | null;
  model_output_preview?: string | null;
  system_chars?: number | null;
  user_chars?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  estimated_cost_usd?: number | null;
  pricing_source?: string | null;
};

export type ReviewLLMCallsResponse = {
  job_id: string;
  count: number;
  events: ReviewLLMCallEvent[];
};

export type ReviewUsageGroup = {
  calls?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  estimated_cost_usd?: number;
  elapsed_ms?: number;
  provider?: string;
  models?: string[];
};

export type ReviewUsageCall = {
  prompt?: string;
  provider?: string;
  model?: string;
  provider_model?: string;
  attempt?: number | null;
  elapsed_ms?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  estimated_cost_usd?: number;
  pricing_source?: string;
};

export type ReviewUsageSummary = {
  schema: string;
  run_id: string;
  currency: string;
  known_usage: boolean;
  total_calls: number;
  successful_calls: number;
  error_calls: number;
  fallback_count: number;
  retry_error_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  elapsed_ms: number;
  by_provider: Record<string, ReviewUsageGroup>;
  by_model: Record<string, ReviewUsageGroup>;
  by_prompt: Record<string, ReviewUsageGroup>;
  slowest_call?: {
    prompt?: string;
    provider?: string;
    model?: string;
    provider_model?: string;
    elapsed_ms?: number;
  };
  missing_usage_count: number;
  missing_pricing_count: number;
  calls: ReviewUsageCall[];
};

export type ReviewUsageSummaryResponse = {
  job_id: string;
  usage: ReviewUsageSummary;
};

export type ReviewJobsResponse = {
  count: number;
  jobs: ReviewJobResponse[];
};

export type ReviewJobsSummaryResponse = {
  count: number;
  active_count: number;
  queued_count: number;
  running_count: number;
  succeeded_count: number;
  failed_count: number;
  canceled_count: number;
  latest_job_id: string;
  latest_status: ReviewJobStatus | null;
  updated_at: string;
};

export type LibraryArtifact = ReviewArtifact & {
  job_id: string;
  job_status: ReviewJobStatus;
  run_id: string;
  paper_path: string;
  venue_domain: VenueCatalogItem["domain"];
  venue_collection: VenueCatalogItem["venue_collection"];
  venue_code: string;
  review_mode: ReviewMode;
  output_language: OutputLanguage;
  final_decision: string | null;
  updated_at: string;
  download_url: string;
};

export type LibraryResponse = {
  count: number;
  artifacts: LibraryArtifact[];
};

export type LibraryRunArtifact = ReviewArtifact & {
  download_url: string;
};

export type LibraryRun = {
  job_id: string;
  job_status: ReviewJobStatus;
  run_id: string;
  paper_path: string;
  venue_domain: VenueCatalogItem["domain"];
  venue_collection: VenueCatalogItem["venue_collection"];
  venue_code: string;
  review_mode: ReviewMode;
  output_language: OutputLanguage;
  final_decision: string | null;
  created_at: string;
  updated_at: string;
  artifact_count: number;
  report_count: number;
  total_size_bytes: number;
  primary_report_name: string;
  primary_report_download_url: string;
  artifacts: LibraryRunArtifact[];
};

export type LibraryRunsResponse = {
  count: number;
  artifact_count: number;
  runs: LibraryRun[];
};

export type RunDeleteResponse = {
  deleted_count: number;
  error_count: number;
  deleted: Array<{ job_id: string; deleted: boolean; artifact_count: number }>;
  errors: Array<{ job_id: string; error_type: string; message: string }>;
};

export type AppConfigResponse = {
  supported_upload_extensions: string[];
  max_upload_bytes: number;
  default_output_language: OutputLanguage;
  default_review_mode: ReviewMode;
};

export type LLMProviderConfig = {
  name: string;
  type: string;
  base_url_env: string;
  api_key_env: string;
  base_url_configured: boolean;
  api_key_configured: boolean;
};

export type LLMModelConfig = {
  model_id: string;
  provider: string;
  provider_model_id: string;
  max_attempts: number;
  fallback_models: string[];
};

export type LLMPromptRoute = {
  name: string;
  model: string;
  registered: boolean;
  provider: string;
  provider_model_id: string;
};

export type LLMRuntimeConfigResponse = {
  status: "loaded" | "error" | string;
  mode: string;
  config_path: string;
  default_model: string;
  providers: LLMProviderConfig[];
  models: LLMModelConfig[];
  prompts: LLMPromptRoute[];
  error_type: string;
  error_message: string;
};

export type OpenApiSummary = {
  title: string;
  version: string;
  path_count: number;
  schema_count: number;
};

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export async function getHealth(): Promise<{ status: string }> {
  return fetchJson("/health");
}

export async function getVenueCatalog(): Promise<VenueCatalogResponse> {
  return fetchJson("/api/venue-catalog");
}

export async function getAppConfig(): Promise<AppConfigResponse> {
  return fetchJson("/api/config");
}

export async function getLLMConfig(): Promise<LLMRuntimeConfigResponse> {
  return fetchJson("/api/llm-config");
}

export async function getOpenApiSummary(): Promise<OpenApiSummary> {
  const document = await fetchJson<{
    info?: { title?: string; version?: string };
    paths?: Record<string, unknown>;
    components?: { schemas?: Record<string, unknown> };
  }>("/openapi.json");
  return {
    title: document.info?.title || "OpenAPI",
    version: document.info?.version || "unknown",
    path_count: Object.keys(document.paths || {}).length,
    schema_count: Object.keys(document.components?.schemas || {}).length,
  };
}

export async function createReviewFromUpload(input: CreateReviewUploadInput): Promise<ReviewRunResponse> {
  const response = await fetch(apiUrl("/api/reviews"), {
    method: "POST",
    body: reviewUploadForm(input),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<ReviewRunResponse>;
}

export async function createReviewJobFromUpload(input: CreateReviewUploadInput): Promise<ReviewJobResponse> {
  const response = await fetch(apiUrl("/api/jobs"), {
    method: "POST",
    body: reviewUploadForm(input),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<ReviewJobResponse>;
}

export async function createReviewJobFromPath(input: CreateReviewPathInput): Promise<ReviewJobResponse> {
  const response = await fetch(apiUrl("/api/jobs"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<ReviewJobResponse>;
}

export async function fetchArxivPaper(arxivId: string): Promise<FetchedPaperResponse> {
  const response = await fetch(apiUrl("/api/paper-sources/arxiv"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ arxiv_id: arxivId }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<FetchedPaperResponse>;
}

export async function createReviewPreset(input: ReviewPresetInput): Promise<ReviewPresetResponse> {
  const response = await fetch(apiUrl("/api/presets"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<ReviewPresetResponse>;
}

export async function getReviewPresets(limit = 50): Promise<ReviewPresetsResponse> {
  return fetchJson(`/api/presets?limit=${encodeURIComponent(String(limit))}`);
}

export async function getReviewJob(jobId: string): Promise<ReviewJobResponse> {
  return fetchJson(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export async function cancelReviewJob(jobId: string): Promise<ReviewJobResponse> {
  const response = await fetch(apiUrl(`/api/jobs/${encodeURIComponent(jobId)}/cancel`), {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<ReviewJobResponse>;
}

export async function retryReviewJob(jobId: string): Promise<ReviewJobResponse> {
  const response = await fetch(apiUrl(`/api/jobs/${encodeURIComponent(jobId)}/retry`), {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<ReviewJobResponse>;
}

export async function getReviewJobs(limit = 50, status: ReviewJobsFilter = "ALL", query = ""): Promise<ReviewJobsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    status,
  });
  if (query.trim()) {
    params.set("q", query.trim());
  }
  return fetchJson(`/api/jobs?${params.toString()}`);
}

export async function getReviewJobsSummary(): Promise<ReviewJobsSummaryResponse> {
  return fetchJson("/api/jobs/summary");
}

export async function getLibraryArtifacts(limit = 100): Promise<LibraryResponse> {
  return fetchJson(`/api/library?limit=${encodeURIComponent(String(limit))}`);
}

export async function getLibraryRuns(limit = 100): Promise<LibraryRunsResponse> {
  return fetchJson(`/api/library/runs?limit=${encodeURIComponent(String(limit))}`);
}

export async function deleteLibraryArtifacts(artifacts: ArtifactDeleteItem[]): Promise<ArtifactDeleteResponse> {
  const response = await fetch(apiUrl("/api/library/artifacts"), {
    method: "DELETE",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ artifacts }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<ArtifactDeleteResponse>;
}

export async function deleteLibraryRuns(jobIds: string[]): Promise<RunDeleteResponse> {
  const response = await fetch(apiUrl("/api/library/runs"), {
    method: "DELETE",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<RunDeleteResponse>;
}

export async function getReviewJobArtifacts(jobId: string): Promise<ReviewArtifactsResponse> {
  return fetchJson(`/api/jobs/${encodeURIComponent(jobId)}/artifacts`);
}

export async function getReviewJobReport(jobId: string): Promise<ReviewReportResponse> {
  return fetchJson(`/api/jobs/${encodeURIComponent(jobId)}/report`);
}

export async function getReviewJobDiagnostics(jobId: string): Promise<ReviewDiagnosticsResponse> {
  return fetchJson(`/api/jobs/${encodeURIComponent(jobId)}/diagnostics`);
}

export async function getReviewJobLLMCalls(jobId: string): Promise<ReviewLLMCallsResponse> {
  return fetchJson(`/api/jobs/${encodeURIComponent(jobId)}/llm-calls`);
}

export async function getReviewJobUsage(jobId: string): Promise<ReviewUsageSummaryResponse> {
  return fetchJson(`/api/jobs/${encodeURIComponent(jobId)}/usage`);
}

export function getReviewArtifactDownloadUrl(jobId: string, artifactName: string): string {
  return apiUrl(`/api/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(artifactName)}`);
}

export function getApiDownloadUrl(path: string): string {
  return apiUrl(path);
}

export function getOpenApiDownloadUrl(): string {
  return apiUrl("/openapi.json");
}

export function getApiBaseUrlLabel(): string {
  return API_BASE_URL || "same-origin / Vite proxy";
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(apiUrl(url));
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.json() as Promise<T>;
}

function apiUrl(path: string): string {
  if (!API_BASE_URL) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function normalizeApiBaseUrl(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim().replace(/\/+$/, "");
}

function reviewUploadForm(input: CreateReviewUploadInput): FormData {
  const form = new FormData();
  form.append("paper", input.paper);
  form.append("review_mode", input.review_mode);
  form.append("output_language", input.output_language);
  form.append("venue_domain", input.venue_domain);
  form.append("venue_collection", input.venue_collection);
  form.append("venue_code", input.venue_code);
  return form;
}

async function responseErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      return body.detail;
    }
    return `${response.status} ${response.statusText}`;
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}
