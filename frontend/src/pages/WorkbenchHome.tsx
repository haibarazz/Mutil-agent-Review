import { type DragEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  Command,
  Download,
  FileText,
  Play,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";

import {
  createReviewJobFromPath,
  createReviewJobFromUpload,
  createReviewPreset,
  cancelReviewJob,
  deleteLibraryRuns,
  fetchArxivPaper,
  getApiDownloadUrl,
  getReviewJobArtifacts,
  getReviewJobDiagnostics,
  getReviewJobLLMCalls,
  getReviewArtifactDownloadUrl,
  getReviewJobReport,
  getReviewJob,
  getReviewJobs,
  getReviewJobsSummary,
  getReviewPresets,
  getLibraryRuns,
  getAppConfig,
  getApiBaseUrlLabel,
  getHealth,
  getLLMConfig,
  getOpenApiDownloadUrl,
  getOpenApiSummary,
  getVenueCatalog,
  retryReviewJob,
  type AppConfigResponse,
  type FetchedPaperResponse,
  type LibraryRun,
  type LLMRuntimeConfigResponse,
  type OpenApiSummary,
  type ReviewArtifact,
  type ReviewDiagnosticsResponse,
  type ReviewLLMCallEvent,
  type ReviewLLMCallsResponse,
  type ReviewJobsSummaryResponse,
  type ReviewJobsFilter,
  type ReviewJobResponse,
  type ReviewPresetResponse,
  type ReviewReportResponse,
  type VenueCatalogItem,
} from "../api/client";
import { ReviewTheater } from "../components/ReviewTheater";

type ReviewMode = "FULL_REVIEW" | "QUICK_REVIEW";
type Domain = "CS" | "IS";
type OutputLanguage = "zh" | "en";
type RunStatus = "idle" | "queued" | "running" | "succeeded" | "failed" | "canceled";
type AgentNodeStatus = "pending" | "running" | "done" | "failed";
type ViewMode = "workbench" | "runs" | "library" | "report" | "venues" | "settings";
type VenueCollectionFilter = "ALL" | VenueCatalogItem["venue_collection"];
type VenueCollection = VenueCatalogItem["venue_collection"];
type AsyncViewStatus = "idle" | "loading" | "ready" | "failed";
type LoadReportDetailOptions = { silent?: boolean };
type CommandPaletteItem = {
  id: string;
  title: string;
  description: string;
  shortcut: string;
  active: boolean;
  run: () => void | Promise<void>;
};

const fallbackVenues: Record<Domain, VenueCatalogItem[]> = {
  CS: [
    { code: "AAAI", name: "AAAI", domain: "CS", venue_collection: "CCFA", source_path: "" },
    { code: "NeurIPS", name: "NeurIPS", domain: "CS", venue_collection: "CCFA", source_path: "" },
    { code: "ICML", name: "ICML", domain: "CS", venue_collection: "CCFA", source_path: "" },
    { code: "ICLR", name: "ICLR", domain: "CS", venue_collection: "CCFA", source_path: "" },
    { code: "SIGMOD", name: "SIGMOD", domain: "CS", venue_collection: "CCFA", source_path: "" },
    { code: "VLDB", name: "VLDB", domain: "CS", venue_collection: "CCFA", source_path: "" },
  ],
  IS: [
    { code: "MISQ", name: "MIS Quarterly", domain: "IS", venue_collection: "UTD24", source_path: "" },
    { code: "ISR", name: "Information Systems Research", domain: "IS", venue_collection: "UTD24", source_path: "" },
    { code: "JMIS", name: "Journal of Management Information Systems", domain: "IS", venue_collection: "FT50", source_path: "" },
  ],
};

const fallbackAppConfig: AppConfigResponse = {
  supported_upload_extensions: [".pdf", ".md", ".tex"],
  max_upload_bytes: 80 * 1024 * 1024,
  default_output_language: "zh",
  default_review_mode: "FULL_REVIEW",
};

const defaultVenueCollectionByDomain: Record<Domain, VenueCollection> = {
  CS: "CCFA",
  IS: "FT50",
};

const venueCollectionOrder: VenueCollection[] = ["CCFA", "CCFB", "CCFC", "FT50", "UTD24"];

const quickVenueCodes: Partial<Record<VenueCollection, string[]>> = {
  CCFA: ["AAAI", "ACL", "NeurIPS", "ICML", "ICLR", "CVPR", "SIGMOD", "VLDB"],
  CCFB: ["EMNLP", "ECAI", "COLING", "CIKM", "ICDM", "WSDM", "PODS", "ICRA"],
  CCFC: ["AAMAS", "COLT", "PAKDD", "DASFAA", "ECIR", "IJCNN", "PRICAI", "MMM"],
  FT50: ["AER", "AMJ", "AMR", "MISQ", "MS", "POM", "SMJ", "JMR"],
  UTD24: ["MISQ", "ISR", "JMIS", "MS", "POM", "JOM", "JMR", "TAR"],
};

const emptyJobsSummary: ReviewJobsSummaryResponse = {
  count: 0,
  active_count: 0,
  queued_count: 0,
  running_count: 0,
  succeeded_count: 0,
  failed_count: 0,
  canceled_count: 0,
  latest_job_id: "",
  latest_status: null,
  updated_at: "",
};

const runFilters: Array<{ value: ReviewJobsFilter; label: string }> = [
  { value: "ALL", label: "All" },
  { value: "ACTIVE", label: "Active" },
  { value: "SUCCEEDED", label: "Done" },
  { value: "FAILED", label: "Failed" },
  { value: "CANCELED", label: "Canceled" },
];

const agents = [
  {
    group: "Pre-processing · 预处理 -> Context",
    items: [
      ["parser", "Parser", "文档解析员", "Title · authors · sections · refs."],
      ["checker", "Content Checker", "内容检查员", "Manuscript sanity and paper intent."],
      ["collector", "Journal Collector", "期刊收集员", "Scope · guidelines · venue profile."],
      ["analyst", "Field Analyst", "领域分析员", "Positions paper in current literature."],
    ],
  },
  {
    group: "Editorial triage · 编辑初筛",
    items: [
      ["se", "Senior Editor · SE", "主编", "Scope · novelty · desk-reject threshold."],
      ["ae", "Associate Editor · AE", "责编", "Review focus and reviewer rubric."],
    ],
  },
  {
    group: "External review · 外审",
    items: [
      ["r1", "Reviewer 1", "方法与实验", "Methods · baselines · ablations."],
      ["r2", "Reviewer 2", "领域贡献", "Contribution · positioning · related work."],
      ["r3", "Reviewer 3", "跨学科读者", "Clarity · assumptions · transferability."],
      ["da", "Devil's Advocate", "反方辩护人", "Strongest objections and failure cases."],
      ["final", "AE Final", "终审编辑", "Decision letter · roadmap · artifacts."],
    ],
  },
] as const;

const agentNodeMap: Record<string, string[]> = {
  parser: ["doc_parse"],
  checker: ["content_check"],
  collector: ["journal_req_collector"],
  analyst: ["field_analyst"],
  se: ["se_check"],
  ae: ["ae_check", "review_dispatch"],
  r1: ["reviewer1"],
  r2: ["reviewer2"],
  r3: ["reviewer3"],
  da: ["devils_advocate"],
  final: ["ae_final", "final_artifact_render", "desk_reject_output", "parse_fail_output", "invalid_file"],
};

export function WorkbenchHome() {
  const [mode, setMode] = useState<ReviewMode>("FULL_REVIEW");
  const [domain, setDomain] = useState<Domain>("CS");
  const [venueCode, setVenueCode] = useState("AAAI");
  const [venueCollection, setVenueCollection] = useState<VenueCollection>("CCFA");
  const [venuePickerOpen, setVenuePickerOpen] = useState(false);
  const [outputLanguage, setOutputLanguage] = useState<OutputLanguage>("zh");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fetchedPaper, setFetchedPaper] = useState<FetchedPaperResponse | null>(null);
  const [arxivInput, setArxivInput] = useState("");
  const [arxivStatus, setArxivStatus] = useState<AsyncViewStatus>("idle");
  const [arxivError, setArxivError] = useState("");
  const [presetStatus, setPresetStatus] = useState<AsyncViewStatus>("idle");
  const [presetMessage, setPresetMessage] = useState("");
  const [presets, setPresets] = useState<ReviewPresetResponse[]>([]);
  const [presetsStatus, setPresetsStatus] = useState<AsyncViewStatus>("idle");
  const [health, setHealth] = useState<"checking" | "ok" | "offline">("checking");
  const [catalog, setCatalog] = useState<VenueCatalogItem[]>(fallbackVenues.CS);
  const [appConfig, setAppConfig] = useState<AppConfigResponse>(fallbackAppConfig);
  const [llmConfig, setLlmConfig] = useState<LLMRuntimeConfigResponse | null>(null);
  const [llmConfigStatus, setLlmConfigStatus] = useState<AsyncViewStatus>("idle");
  const [openApiSummary, setOpenApiSummary] = useState<OpenApiSummary | null>(null);
  const [openApiStatus, setOpenApiStatus] = useState<AsyncViewStatus>("idle");
  const [jobsSummary, setJobsSummary] = useState<ReviewJobsSummaryResponse>(emptyJobsSummary);
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [runResult, setRunResult] = useState<ReviewJobResponse | null>(null);
  const [runError, setRunError] = useState("");
  const [artifactCount, setArtifactCount] = useState<number | null>(null);
  const [reportPreview, setReportPreview] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>(() => initialViewMode());
  const [historyJobs, setHistoryJobs] = useState<ReviewJobResponse[]>([]);
  const [historyStatus, setHistoryStatus] = useState<AsyncViewStatus>("idle");
  const [historyFilter, setHistoryFilter] = useState<ReviewJobsFilter>("ALL");
  const [historyQuery, setHistoryQuery] = useState("");
  const [selectedHistoryReport, setSelectedHistoryReport] = useState<ReviewReportResponse | null>(null);
  const [libraryRuns, setLibraryRuns] = useState<LibraryRun[]>([]);
  const [selectedLibraryRunIds, setSelectedLibraryRunIds] = useState<Set<string>>(() => new Set());
  const [expandedLibraryRunIds, setExpandedLibraryRunIds] = useState<Set<string>>(() => new Set());
  const [pendingDeleteRuns, setPendingDeleteRuns] = useState<LibraryRun[]>([]);
  const [libraryDeleteStatus, setLibraryDeleteStatus] = useState<AsyncViewStatus>("idle");
  const [libraryDeleteMessage, setLibraryDeleteMessage] = useState("");
  const [libraryStatus, setLibraryStatus] = useState<AsyncViewStatus>("idle");
  const [reportDetailJob, setReportDetailJob] = useState<ReviewJobResponse | null>(null);
  const [reportDetailArtifacts, setReportDetailArtifacts] = useState<ReviewArtifact[]>([]);
  const [reportDetailReport, setReportDetailReport] = useState<ReviewReportResponse | null>(null);
  const [reportDetailDiagnostics, setReportDetailDiagnostics] = useState<ReviewDiagnosticsResponse | null>(null);
  const [reportDetailLLMCalls, setReportDetailLLMCalls] = useState<ReviewLLMCallsResponse | null>(null);
  const [reportDetailStatus, setReportDetailStatus] = useState<AsyncViewStatus>("idle");
  const [reportDetailError, setReportDetailError] = useState("");
  const [commandOpen, setCommandOpen] = useState(false);
  const [dropActive, setDropActive] = useState(false);
  const activeJobRef = useRef<string | null>(null);

  useEffect(() => {
    function handleGlobalShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((current) => !current);
      }
      if (event.key === "Escape") {
        setCommandOpen(false);
      }
    }

    window.addEventListener("keydown", handleGlobalShortcut);
    return () => window.removeEventListener("keydown", handleGlobalShortcut);
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([getHealth(), getVenueCatalog(), getAppConfig()])
      .then(([, venueCatalog, remoteConfig]) => {
        if (!active) return;
        const items = flattenCatalog(venueCatalog.catalog);
        setCatalog(items.length ? items : fallbackVenues.CS);
        setAppConfig(remoteConfig);
        setHealth("ok");
      })
      .catch(() => {
        if (!active) return;
        setHealth("offline");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    void loadJobsSummary();
  }, []);

  useEffect(() => {
    let active = true;
    setOpenApiStatus("loading");
    getOpenApiSummary()
      .then((summary) => {
        if (!active) return;
        setOpenApiSummary(summary);
        setOpenApiStatus("ready");
      })
      .catch(() => {
        if (!active) return;
        setOpenApiSummary(null);
        setOpenApiStatus("failed");
      });
    return () => {
      active = false;
    };
  }, []);

  const domainVenues = useMemo(() => {
    const filtered = catalog.filter((item) => item.domain === domain);
    return filtered.length ? filtered : fallbackVenues[domain];
  }, [catalog, domain]);

  const domainCollections = useMemo(() => venueCollections(domainVenues), [domainVenues]);
  const collectionVenues = useMemo(
    () => domainVenues.filter((item) => item.venue_collection === venueCollection),
    [domainVenues, venueCollection],
  );
  const selectedVenueMemberships = useMemo(
    () => venueMembershipsForCode(domainVenues, venueCode),
    [domainVenues, venueCode],
  );
  const quickVenueItems = useMemo(
    () => preferredVenueItems(collectionVenues, venueCollection),
    [collectionVenues, venueCollection],
  );

  useEffect(() => {
    const fallbackCollection = domainCollections[0] ?? defaultVenueCollectionByDomain[domain];
    if (!domainCollections.includes(venueCollection)) {
      setVenueCollection(fallbackCollection);
      setVenuePickerOpen(false);
      return;
    }
    const venuesInCollection = domainVenues.filter((item) => item.venue_collection === venueCollection);
    if (!venuesInCollection.some((item) => item.code === venueCode)) {
      setVenueCode(venuesInCollection[0]?.code ?? domainVenues[0]?.code ?? "");
      setVenuePickerOpen(false);
    }
  }, [domain, domainCollections, domainVenues, venueCode, venueCollection]);

  useEffect(() => {
    if (viewMode === "runs" && historyStatus === "idle") {
      void loadHistoryJobs();
    }
  }, [viewMode, historyStatus]);

  useEffect(() => {
    if (viewMode === "library" && libraryStatus === "idle") {
      void loadLibraryRuns();
    }
  }, [viewMode, libraryStatus]);

  useEffect(() => {
    if (viewMode === "settings" && presetsStatus === "idle") {
      void loadPresets();
    }
    if (viewMode === "settings" && llmConfigStatus === "idle") {
      void loadLLMConfig();
    }
  }, [viewMode, presetsStatus, llmConfigStatus]);

  useEffect(() => {
    const jobId = reportJobIdFromHash();
    if (viewMode === "report" && reportDetailStatus === "idle" && jobId) {
      void loadReportDetail(jobId);
    }
  }, [viewMode, reportDetailStatus]);

  useEffect(() => {
    if (viewMode !== "report" || !reportDetailJob || !isLiveJobStatus(reportDetailJob.status)) {
      return undefined;
    }
    const jobId = reportDetailJob.job_id;
    const timer = window.setInterval(() => {
      void loadReportDetail(jobId, { silent: true });
    }, 2200);
    return () => window.clearInterval(timer);
  }, [viewMode, reportDetailJob?.job_id, reportDetailJob?.status]);

  const selectedVenue =
    domainVenues.find((item) => item.code === venueCode && item.venue_collection === venueCollection)
    ?? domainVenues.find((item) => item.code === venueCode)
    ?? collectionVenues[0]
    ?? domainVenues[0];
  const reviewLabel = mode === "FULL_REVIEW" ? "Full Review" : "Quick Review";
  const agentCount = mode === "FULL_REVIEW" ? "11 agents" : "7 agents";
  const estimate = mode === "FULL_REVIEW" ? "~7 min" : "~4 min";
  const supportedUploadLabels = appConfig.supported_upload_extensions.map((item) => item.replace(/^\./, "").toUpperCase());
  const uploadAccept = appConfig.supported_upload_extensions.join(",");
  const uploadRules = `${supportedUploadLabels.join(" · ")} · ≤ ${formatBytes(appConfig.max_upload_bytes)}`;
  const isActiveRun = runStatus === "queued" || runStatus === "running";
  const stagedPaperLabel = selectedFile?.name || fetchedPaper?.filename || "";
  const canBeginReview = Boolean((selectedFile || fetchedPaper) && selectedVenue && health === "ok" && !isActiveRun && arxivStatus !== "loading");
  const selectedHistoryJob = selectedHistoryReport ? historyJobs.find((job) => job.job_id === selectedHistoryReport.job_id) ?? null : null;
  const displayJob = currentDisplayJob({
    viewMode,
    runResult,
    selectedHistoryJob,
    reportDetailJob,
  });
  const displayReviewMode = displayJob?.request.review_mode ?? mode;
  const displayNodeStatuses = displayJob?.nodes ?? {};
  const displayStatusLabel = displayJob ? runStatusLabel(toRunStatus(displayJob.status)) : transientStatusLabel(viewMode, runStatus, reportDetailStatus);
  const queueStatusLabel = jobSummaryLabel(jobsSummary);
  const railAgentLabel = displayReviewMode === "FULL_REVIEW" ? "FULL REVIEW · 11 AGENTS" : "QUICK REVIEW · 7 AGENTS";
  const railEditorCount = displayReviewMode === "FULL_REVIEW" ? 3 : 1;
  const railSelectedVenue = displayJob?.request.venue_code || selectedVenue?.code || "None";
  const reportDetailAutoRefreshing = viewMode === "report" && isLiveJobStatus(reportDetailJob?.status);

  async function loadJobsSummary() {
    try {
      setJobsSummary(await getReviewJobsSummary());
    } catch {
      setJobsSummary(emptyJobsSummary);
    }
  }

  async function loadHistoryJobs(filter: ReviewJobsFilter = historyFilter, query: string = historyQuery) {
    setHistoryStatus("loading");
    try {
      const response = await getReviewJobs(50, filter, query);
      setHistoryJobs(response.jobs);
      void loadJobsSummary();
      setHistoryStatus("ready");
    } catch {
      setHistoryJobs([]);
      setHistoryStatus("failed");
    }
  }

  async function loadLibraryRuns() {
    setLibraryStatus("loading");
    try {
      const response = await getLibraryRuns(100);
      setLibraryRuns(response.runs);
      setSelectedLibraryRunIds((current) => pruneRunSelection(current, response.runs));
      setExpandedLibraryRunIds((current) => pruneRunSelection(current, response.runs));
      setLibraryStatus("ready");
    } catch {
      setLibraryRuns([]);
      setSelectedLibraryRunIds(new Set());
      setExpandedLibraryRunIds(new Set());
      setLibraryStatus("failed");
    }
  }

  function requestDeleteLibraryRuns(runs: LibraryRun[]) {
    if (runs.length === 0) return;
    setPendingDeleteRuns(runs);
    setLibraryDeleteStatus("idle");
    setLibraryDeleteMessage("");
  }

  async function confirmDeleteLibraryRuns() {
    if (pendingDeleteRuns.length === 0) return;
    setLibraryDeleteStatus("loading");
    setLibraryDeleteMessage("");
    try {
      const response = await deleteLibraryRuns(pendingDeleteRuns.map((run) => run.job_id));
      setSelectedLibraryRunIds(new Set());
      setExpandedLibraryRunIds(new Set());
      setLibraryDeleteStatus(response.error_count > 0 ? "failed" : "ready");
      setLibraryDeleteMessage(
        response.error_count > 0
          ? `Deleted ${response.deleted_count}; ${response.error_count} failed.`
          : `Deleted ${response.deleted_count} review run${response.deleted_count === 1 ? "" : "s"}.`,
      );
      setPendingDeleteRuns([]);
      await loadLibraryRuns();
      if (historyStatus === "ready") {
        await loadHistoryJobs(historyFilter, historyQuery);
      }
    } catch (error) {
      setLibraryDeleteStatus("failed");
      setLibraryDeleteMessage(error instanceof Error ? error.message : "Failed to delete review runs.");
    }
  }

  function toggleLibraryRun(run: LibraryRun) {
    setSelectedLibraryRunIds((current) => {
      const next = new Set(current);
      if (next.has(run.job_id)) {
        next.delete(run.job_id);
      } else {
        next.add(run.job_id);
      }
      return next;
    });
  }

  function toggleAllLibraryRuns() {
    setSelectedLibraryRunIds((current) => {
      if (libraryRuns.length > 0 && current.size === libraryRuns.length) {
        return new Set();
      }
      return new Set(libraryRuns.map((run) => run.job_id));
    });
  }

  function toggleLibraryRunExpanded(run: LibraryRun) {
    setExpandedLibraryRunIds((current) => {
      const next = new Set(current);
      if (next.has(run.job_id)) {
        next.delete(run.job_id);
      } else {
        next.add(run.job_id);
      }
      return next;
    });
  }

  async function loadPresets() {
    setPresetsStatus("loading");
    try {
      const response = await getReviewPresets(20);
      setPresets(response.presets);
      setPresetsStatus("ready");
    } catch {
      setPresets([]);
      setPresetsStatus("failed");
    }
  }

  async function loadLLMConfig() {
    setLlmConfigStatus("loading");
    try {
      setLlmConfig(await getLLMConfig());
      setLlmConfigStatus("ready");
    } catch {
      setLlmConfig(null);
      setLlmConfigStatus("failed");
    }
  }

  async function loadReportDetail(jobId: string, options: LoadReportDetailOptions = {}) {
    if (!options.silent) {
      setReportDetailStatus("loading");
      setReportDetailError("");
      setReportDetailJob(null);
      setReportDetailArtifacts([]);
      setReportDetailReport(null);
      setReportDetailDiagnostics(null);
      setReportDetailLLMCalls(null);
    }
    try {
      const job = await getReviewJob(jobId);
      setReportDetailJob(job);
      if (job.status !== "SUCCEEDED" && job.status !== "FAILED") {
        if (!options.silent) {
          setReportDetailArtifacts([]);
          setReportDetailReport(null);
          setReportDetailDiagnostics(null);
          setReportDetailLLMCalls(null);
        }
        setReportDetailStatus("ready");
        return;
      }
      try {
        const [artifacts, report, diagnostics, llmCalls] = await Promise.all([
          getReviewJobArtifacts(jobId),
          getReviewJobReport(jobId),
          getReviewJobDiagnostics(jobId),
          getReviewJobLLMCalls(jobId),
        ]);
        setReportDetailArtifacts(artifacts.artifacts);
        setReportDetailReport(report);
        setReportDetailDiagnostics(diagnostics);
        setReportDetailLLMCalls(llmCalls);
      } catch (artifactError) {
        if (job.status === "SUCCEEDED") {
          throw artifactError;
        }
        // 失败任务可能发生在 workflow 创建 run 之前；这种情况只展示错误面板。
        setReportDetailArtifacts([]);
        setReportDetailReport(null);
        setReportDetailDiagnostics(null);
        setReportDetailLLMCalls(null);
      }
      setReportDetailStatus("ready");
    } catch (error) {
      setReportDetailError(error instanceof Error ? error.message : "Failed to load report detail.");
      setReportDetailStatus("failed");
    }
  }

  async function openRunsView() {
    setViewMode("runs");
    setSelectedHistoryReport(null);
    window.history.replaceState(null, "", "#runs");
    await loadHistoryJobs(historyFilter, historyQuery);
  }

  async function applyHistoryFilter(filter: ReviewJobsFilter) {
    setHistoryFilter(filter);
    setSelectedHistoryReport(null);
    if (viewMode === "runs") {
      await loadHistoryJobs(filter, historyQuery);
    }
  }

  async function applyHistoryQuery(query: string) {
    setHistoryQuery(query);
    setSelectedHistoryReport(null);
    if (viewMode === "runs") {
      await loadHistoryJobs(historyFilter, query);
    }
  }

  async function openLibraryView() {
    setViewMode("library");
    window.history.replaceState(null, "", "#library");
    await loadLibraryRuns();
  }

  async function openReportDetail(jobId: string) {
    setViewMode("report");
    window.history.replaceState(null, "", `#report=${encodeURIComponent(jobId)}`);
    await loadReportDetail(jobId);
  }

  function openWorkbenchView() {
    setViewMode("workbench");
    window.history.replaceState(null, "", "#workbench");
  }

  function openVenuesView() {
    setViewMode("venues");
    window.history.replaceState(null, "", "#venues");
  }

  function openSettingsView() {
    setViewMode("settings");
    window.history.replaceState(null, "", "#settings");
    void loadPresets();
    void loadLLMConfig();
  }

  const commandItems: CommandPaletteItem[] = [
    {
      id: "workbench",
      title: "Workbench",
      description: "新建审稿与参数配置",
      shortcut: "W",
      active: viewMode === "workbench",
      run: openWorkbenchView,
    },
    {
      id: "runs",
      title: "Runs",
      description: "审稿任务历史与报告入口",
      shortcut: "R",
      active: viewMode === "runs" || viewMode === "report",
      run: openRunsView,
    },
    {
      id: "library",
      title: "Library",
      description: "本地产物与 Markdown 报告",
      shortcut: "L",
      active: viewMode === "library",
      run: openLibraryView,
    },
    {
      id: "venues",
      title: "Venues",
      description: "期刊与会议 venue catalog",
      shortcut: "V",
      active: viewMode === "venues",
      run: openVenuesView,
    },
    {
      id: "settings",
      title: "Settings",
      description: "API、OpenAPI 与 preset",
      shortcut: "S",
      active: viewMode === "settings",
      run: openSettingsView,
    },
  ];

  function runCommand(item: CommandPaletteItem) {
    setCommandOpen(false);
    void item.run();
  }

  function useVenueFromCatalog(item: VenueCatalogItem) {
    setDomain(item.domain);
    setVenueCollection(item.venue_collection);
    setVenueCode(item.code);
    setViewMode("workbench");
    window.history.replaceState(null, "", "#workbench");
  }

  function handleFileSelection(file: File | null) {
    setDropActive(false);
    activeJobRef.current = null;
    setRunResult(null);
    setArtifactCount(null);
    setReportPreview("");
    setFetchedPaper(null);
    setArxivStatus("idle");
    setArxivError("");

    if (!file) {
      setSelectedFile(null);
      setRunStatus("idle");
      setRunError("");
      return;
    }

    const extension = fileExtension(file.name);
    if (!appConfig.supported_upload_extensions.includes(extension)) {
      setSelectedFile(null);
      setRunStatus("failed");
      setRunError(`Unsupported file type: ${extension || "(none)"}.`);
      return;
    }
    if (file.size > appConfig.max_upload_bytes) {
      setSelectedFile(null);
      setRunStatus("failed");
      setRunError(`File is too large. Max ${formatBytes(appConfig.max_upload_bytes)}.`);
      return;
    }

    setSelectedFile(file);
    setRunStatus("idle");
    setRunError("");
  }

  function handleManuscriptDrag(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDropActive(true);
  }

  function handleManuscriptDragLeave(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setDropActive(false);
  }

  function handleManuscriptDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    event.stopPropagation();
    handleFileSelection(event.dataTransfer.files?.[0] ?? null);
  }

  async function handleFetchArxiv() {
    const source = arxivInput.trim();
    if (!source) {
      setArxivStatus("failed");
      setArxivError("请输入 arXiv ID 或完整 URL。");
      return;
    }
    activeJobRef.current = null;
    setArxivStatus("loading");
    setArxivError("");
    setRunResult(null);
    setArtifactCount(null);
    setReportPreview("");
    try {
      const paper = await fetchArxivPaper(source);
      setFetchedPaper(paper);
      setSelectedFile(null);
      setRunStatus("idle");
      setRunError("");
      setArxivStatus("ready");
    } catch (error) {
      setFetchedPaper(null);
      setArxivStatus("failed");
      setArxivError(error instanceof Error ? error.message : "arXiv fetch failed.");
    }
  }

  async function handleBeginReview() {
    if ((!selectedFile && !fetchedPaper) || !selectedVenue) {
      setRunStatus("failed");
      setRunError("请先选择稿件和目标 venue。");
      return;
    }
    setRunStatus("queued");
    setRunError("");
    setRunResult(null);
    setArtifactCount(null);
    setReportPreview("");
    try {
      const reviewOptions = {
        review_mode: mode,
        output_language: outputLanguage,
        venue_domain: domain,
        venue_collection: selectedVenue.venue_collection,
        venue_code: selectedVenue.code,
      };
      const created = selectedFile
        ? await createReviewJobFromUpload({ paper: selectedFile, ...reviewOptions })
        : await createReviewJobFromPath({ paper_path: fetchedPaper?.paper_path || "", ...reviewOptions });
      setRunResult(created);
      setRunStatus(toRunStatus(created.status));
      void loadJobsSummary();
      activeJobRef.current = created.job_id;
      await pollJob(created.job_id);
    } catch (error) {
      setRunStatus("failed");
      setRunError(error instanceof Error ? error.message : "Review request failed.");
    }
  }

  async function pollJob(jobId: string) {
    for (let attempt = 0; attempt < 600; attempt += 1) {
      await delay(1200);
      if (activeJobRef.current !== jobId) {
        return;
      }
      const job = await getReviewJob(jobId);
      setRunResult(job);
      const nextStatus = toRunStatus(job.status);
      setRunStatus(nextStatus);
      if (nextStatus === "succeeded") {
        await loadJobOutputs(jobId);
        await loadHistoryJobs();
        void loadJobsSummary();
        return;
      }
      if (nextStatus === "failed") {
        setRunError(job.error?.message || job.error?.error_type || "Review job failed.");
        await loadHistoryJobs();
        void loadJobsSummary();
        return;
      }
      if (nextStatus === "canceled") {
        setRunError(job.error?.message || "Review job canceled.");
        await loadHistoryJobs();
        void loadJobsSummary();
        return;
      }
    }
    setRunStatus("failed");
    setRunError("Review job polling timed out.");
  }

  async function handleCancelJob(jobId: string) {
    try {
      const canceled = await cancelReviewJob(jobId);
      setRunResult((current) => (current?.job_id === jobId ? canceled : current));
      setReportDetailJob((current) => (current?.job_id === jobId ? canceled : current));
      setHistoryJobs((current) => current.map((job) => (job.job_id === jobId ? canceled : job)));
      if (activeJobRef.current === jobId) {
        activeJobRef.current = null;
        setRunStatus("canceled");
        setRunError(canceled.error?.message || "Review job canceled.");
      }
      void loadJobsSummary();
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Failed to cancel review job.");
    }
  }

  async function handleRetryJob(jobId: string) {
    try {
      setRunError("");
      const retried = await retryReviewJob(jobId);
      activeJobRef.current = retried.job_id;
      setRunResult(retried);
      setRunStatus(toRunStatus(retried.status));
      setHistoryJobs((current) => [retried, ...current.filter((job) => job.job_id !== retried.job_id)]);
      void loadJobsSummary();
      await pollJob(retried.job_id);
    } catch (error) {
      setRunStatus("failed");
      setRunError(error instanceof Error ? error.message : "Failed to retry review job.");
    }
  }

  async function handleSavePreset() {
    if (!selectedVenue) {
      setPresetStatus("failed");
      setPresetMessage("请先选择一个 venue。");
      return;
    }
    setPresetStatus("loading");
    setPresetMessage("");
    try {
      const preset = await createReviewPreset({
        name: `${humanReviewMode(mode)} · ${domain} · ${selectedVenue.code}`,
        review_mode: mode,
        output_language: outputLanguage,
        venue_domain: domain,
        venue_collection: selectedVenue.venue_collection,
        venue_code: selectedVenue.code,
      });
      setPresetStatus("ready");
      setPresetMessage(`Saved ${preset.name}`);
      setPresets((current) => [preset, ...current.filter((item) => item.preset_id !== preset.preset_id)].slice(0, 20));
      setPresetsStatus("ready");
    } catch (error) {
      setPresetStatus("failed");
      setPresetMessage(error instanceof Error ? error.message : "Preset save failed.");
    }
  }

  function applyPreset(preset: ReviewPresetResponse) {
    setMode(preset.review_mode);
    setDomain(preset.venue_domain);
    setVenueCollection(preset.venue_collection);
    setVenueCode(preset.venue_code);
    setOutputLanguage(preset.output_language);
    setPresetStatus("ready");
    setPresetMessage(`Using ${preset.name}`);
    setViewMode("workbench");
    window.history.replaceState(null, "", "#workbench");
  }

  async function openHistoryReport(job: ReviewJobResponse) {
    if (!canOpenJobReport(job)) {
      setSelectedHistoryReport(null);
      return;
    }
    try {
      setSelectedHistoryReport(await getReviewJobReport(job.job_id));
    } catch {
      setSelectedHistoryReport(null);
    }
  }

  async function loadJobOutputs(jobId: string) {
    try {
      const [artifacts, report] = await Promise.all([
        getReviewJobArtifacts(jobId),
        getReviewJobReport(jobId),
      ]);
      if (activeJobRef.current !== jobId) return;
      setArtifactCount(artifacts.artifacts.length);
      setReportPreview(compactReportPreview(report.content));
    } catch {
      // 报告预览只是前端增强；读取失败不应该把已完成的审稿 job 改成失败。
      setArtifactCount(null);
      setReportPreview("");
    }
  }

  return (
    <div className="workbench-shell">
      <header className="topbar">
        <div className="brand">
          <div className="crest">M</div>
          <span>Multi-Agent Paper Review</span>
          <small>v0.4 · workbench</small>
        </div>
        <nav aria-label="Primary">
          <button type="button" className={viewMode === "workbench" ? "active" : ""} onClick={openWorkbenchView}>Workbench</button>
          <button type="button" className={viewMode === "runs" || viewMode === "report" ? "active" : ""} onClick={openRunsView}>Runs</button>
          <button type="button" className={viewMode === "library" ? "active" : ""} onClick={openLibraryView}>Library</button>
          <button type="button" className={viewMode === "venues" ? "active" : ""} onClick={openVenuesView}>Venues</button>
          <button type="button" className={viewMode === "settings" ? "active" : ""} onClick={openSettingsView}>Settings</button>
        </nav>
        <div className="util">
          <button
            type="button"
            className="cmd cmd-button"
            aria-label="Open command palette"
            aria-expanded={commandOpen}
            onClick={() => setCommandOpen((current) => !current)}
          >
            <Command size={12} />K
          </button>
          <div className="who">
            <span className="avatar">YL</span>
            <span>yi.liu@lab</span>
          </div>
        </div>
      </header>
      <CommandPalette
        open={commandOpen}
        items={commandItems}
        onClose={() => setCommandOpen(false)}
        onRun={runCommand}
      />
      <DeleteRunsDialog
        open={pendingDeleteRuns.length > 0}
        runs={pendingDeleteRuns}
        status={libraryDeleteStatus}
        message={libraryDeleteMessage}
        onCancel={() => {
          if (libraryDeleteStatus !== "loading") {
            setPendingDeleteRuns([]);
          }
        }}
        onConfirm={confirmDeleteLibraryRuns}
      />

      <div className="substrip">
        <div className="l">
          <a href="#">{viewPrimaryLabel(viewMode)}</a>
          <span className="sep">/</span>
          <a href="#" className="active">{viewSecondaryLabel(viewMode)}</a>
        </div>
        <div className="r">
          <span><i>RUN</i>{displayJob ? displayJob.job_id.slice(0, 8) : "RUN-LOCAL-DRAFT"}</span>
          <span><i>API</i>{health.toUpperCase()}</span>
          <span><i>QUEUE</i>{queueStatusLabel}</span>
          <span><i>STATUS</i>{displayStatusLabel}</span>
        </div>
      </div>

      <div className="workbench-page">
        {viewMode === "runs" ? (
          <RunsView
            jobs={historyJobs}
            status={historyStatus}
            filter={historyFilter}
            query={historyQuery}
            selectedReport={selectedHistoryReport}
            onRefresh={openRunsView}
            onFilterChange={applyHistoryFilter}
            onQueryChange={applyHistoryQuery}
            onCancel={handleCancelJob}
            onRetry={handleRetryJob}
            onOpenReport={openHistoryReport}
            onOpenDetail={openReportDetail}
          />
        ) : viewMode === "library" ? (
          <LibraryView
            expandedKeys={expandedLibraryRunIds}
            deleteMessage={libraryDeleteMessage}
            deleteStatus={libraryDeleteStatus}
            runs={libraryRuns}
            selectedKeys={selectedLibraryRunIds}
            status={libraryStatus}
            onDeleteSelected={requestDeleteLibraryRuns}
            onRefresh={openLibraryView}
            onOpenRun={openReportDetail}
            onToggleAll={toggleAllLibraryRuns}
            onToggleExpanded={toggleLibraryRunExpanded}
            onToggleRun={toggleLibraryRun}
          />
        ) : viewMode === "report" ? (
          <ReportDetailView
            job={reportDetailJob}
            artifacts={reportDetailArtifacts}
            report={reportDetailReport}
            diagnostics={reportDetailDiagnostics}
            llmCalls={reportDetailLLMCalls}
            status={reportDetailStatus}
            error={reportDetailError}
            autoRefreshing={reportDetailAutoRefreshing}
            onBackToRuns={openRunsView}
            onCancel={handleCancelJob}
            onRetry={handleRetryJob}
            onRefresh={(jobId) => loadReportDetail(jobId)}
          />
        ) : viewMode === "venues" ? (
          <VenuesView
            catalog={catalog}
            selectedVenue={selectedVenue}
            onUseVenue={useVenueFromCatalog}
          />
        ) : viewMode === "settings" ? (
          <SettingsView
            appConfig={appConfig}
            apiBaseUrl={getApiBaseUrlLabel()}
            catalogCount={catalog.length}
            health={health}
            llmConfig={llmConfig}
            llmConfigStatus={llmConfigStatus}
            openApiSummary={openApiSummary}
            openApiStatus={openApiStatus}
            outputLanguage={outputLanguage}
            presets={presets}
            presetsStatus={presetsStatus}
            reviewMode={mode}
            onRefreshLLMConfig={loadLLMConfig}
            onRefreshPresets={loadPresets}
            onUsePreset={applyPreset}
          />
        ) : (
        <main className="hero">
          <div className="h-head">
            <div className="eyebrow">NEW SUBMISSION · 新建审稿</div>
            <h1>
              Submit a manuscript for review.
              <span className="zh">提交一份稿件，让审稿智能体走一遍真实期刊审稿流程。</span>
            </h1>
          </div>

          <section className="ms" aria-label="Manuscript source">
            <div className="ms-h">
              <div className="meta">
                <span className="file"><b>① Source</b></span>
                <span className="file-rule">{uploadRules}</span>
              </div>
              <div className="crest">Manuscript intake</div>
            </div>

            <label
              className={`ms-drop ${selectedFile ? "has-file" : ""} ${dropActive ? "drag-over" : ""}`}
              onDragEnter={handleManuscriptDrag}
              onDragOver={handleManuscriptDrag}
              onDragLeave={handleManuscriptDragLeave}
              onDrop={handleManuscriptDrop}
            >
              <input
                type="file"
                accept={uploadAccept}
                onChange={(event) => {
                  handleFileSelection(event.currentTarget.files?.[0] ?? null);
                  event.currentTarget.value = "";
                }}
              />
              <div className="info">
                <div className="upload-mark"><Upload size={16} /> Manuscript file</div>
                <h3>
                  {stagedPaperLabel || "拖入稿件 · 或点击选择文件"}
                  <span className="zh">
                    {stagedPaperLabel ? "Paper is staged locally for the next review run." : `Drop a manuscript, or choose ${supportedUploadLabels.join(" / ")}.`}
                  </span>
                </h3>
                <p>系统会先解析结构（标题 · 摘要 · 章节 · 引用），生成 manuscript card，然后进入审稿流程。</p>
                <div className="ftypes">
                  {supportedUploadLabels.map((item) => <span key={item}>{item}</span>)}
                  <span className="quiet-dot">·</span>
                  <span>AAAI</span><span>CCF-A</span><span>FT50</span>
                </div>
              </div>
              <PaperSpecimen />
            </label>

            <form className="ms-paste" onSubmit={(event) => {
              event.preventDefault();
              void handleFetchArxiv();
            }}>
              <span className="or">— OR PASTE —</span>
              <div className={`url ${arxivStatus === "failed" ? "error" : ""}`}>
                <span className="prefix">https://arxiv.org/abs/</span>
                <input
                  aria-label="arXiv id or URL"
                  value={arxivInput}
                  onChange={(event) => setArxivInput(event.currentTarget.value)}
                  placeholder="2406.12345"
                  disabled={arxivStatus === "loading" || isActiveRun}
                />
                {arxivInput ? <span className="cursor" /> : null}
                <button className="url-action" type="submit" disabled={arxivStatus === "loading" || isActiveRun}>
                  {arxivStatus === "loading" ? "Fetching..." : "Enter to fetch"}
                </button>
              </div>
              {arxivStatus === "ready" && fetchedPaper ? <span className="arxiv-note">Fetched {fetchedPaper.arxiv_id} · {formatBytes(fetchedPaper.size_bytes)}</span> : null}
              {arxivStatus === "failed" && arxivError ? <span className="arxiv-note error">{arxivError}</span> : null}
            </form>
          </section>

          <section className="cfg" aria-label="Review configuration">
            <ConfigBlock title="② Review mode · 审稿模式" meta="SELECT 1">
              <div className="modes">
                <ModeOption
                  active={mode === "FULL_REVIEW"}
                  title="Full Review"
                  subtitle="SE / AE 初筛 -> 4 reviewers in parallel -> 终审"
                  estimate="~7 min"
                  onClick={() => setMode("FULL_REVIEW")}
                />
                <ModeOption
                  active={mode === "QUICK_REVIEW"}
                  title="Quick Review"
                  subtitle="跳过 SE / AE 初筛，直接进入外审"
                  estimate="~4 min"
                  onClick={() => setMode("QUICK_REVIEW")}
                />
              </div>
            </ConfigBlock>

            <ConfigBlock title="③ Domain · 领域大类" meta="SELECT 1">
              <div className="dom-tabs">
                <DomainOption
                  active={domain === "CS"}
                  abbr="CS"
                  name="Computer Science"
                  detail="CCF-A / B / C"
                  onClick={() => {
                    setDomain("CS");
                    setVenueCollection(defaultVenueCollectionByDomain.CS);
                    setVenuePickerOpen(false);
                  }}
                />
                <DomainOption
                  active={domain === "IS"}
                  abbr="IS"
                  name="Information Systems"
                  detail="FT50 / UTD24"
                  onClick={() => {
                    setDomain("IS");
                    setVenueCollection(defaultVenueCollectionByDomain.IS);
                    setVenuePickerOpen(false);
                  }}
                />
              </div>
            </ConfigBlock>

            <ConfigBlock title="④ Venue · 期刊 · 会议" meta={`${domain} · ${venueCollection}`}>
              <div className="venue-collection-tabs" role="group" aria-label="Venue collection">
                {domainCollections.map((item) => (
                  <button
                    key={item}
                    className={item === venueCollection ? "on" : ""}
                    type="button"
                    onClick={() => {
                      setVenueCollection(item);
                      setVenuePickerOpen(false);
                    }}
                  >
                    {item}
                  </button>
                ))}
              </div>
              <button
                className={`ven-input ${venuePickerOpen ? "open" : ""}`}
                type="button"
                aria-expanded={venuePickerOpen}
                aria-haspopup="listbox"
                onClick={() => setVenuePickerOpen((current) => !current)}
              >
                <Search size={14} className="ic" />
                <span className="v">{selectedVenue?.code || "Select venue"}</span>
                <span className="yr">'26</span>
                <span className="venue-memberships" aria-label="Venue memberships">
                  {(selectedVenueMemberships.length ? selectedVenueMemberships : selectedVenue ? [selectedVenue.venue_collection] : ["CATALOG"]).map((item) => (
                    <span className={`tag ${item === venueCollection ? "primary" : ""}`} key={item}>{item}</span>
                  ))}
                </span>
                <ChevronDown size={14} className="chev" />
              </button>
              {venuePickerOpen ? (
                <div className="ven-menu" role="listbox" aria-label="Venue picker">
                  {collectionVenues.map((item) => (
                    <button
                      key={`${item.venue_collection}-${item.code}`}
                      className={item.code === venueCode && item.venue_collection === venueCollection ? "on" : ""}
                      type="button"
                      role="option"
                      aria-selected={item.code === venueCode && item.venue_collection === venueCollection}
                      onClick={() => {
                        setVenueCode(item.code);
                        setVenuePickerOpen(false);
                      }}
                    >
                      <span>{item.code}</span>
                      <small>{venueMembershipsForCode(domainVenues, item.code).join(" · ") || item.venue_collection}</small>
                    </button>
                  ))}
                </div>
              ) : null}
              <div className="ven-suggest">
                {quickVenueItems.map((item) => (
                  <button
                    key={`${item.venue_collection}-${item.code}`}
                    className={item.code === venueCode && item.venue_collection === venueCollection ? "on" : ""}
                    type="button"
                    onClick={() => {
                      setVenueCode(item.code);
                      setVenuePickerOpen(false);
                    }}
                  >
                    {item.code}
                  </button>
                ))}
              </div>
            </ConfigBlock>
          </section>

          <section className="footer" aria-label="Review summary">
            <div className="sum">
              <div className="s">
                <div className="l">Plan</div>
                <div className="v">
                  {reviewLabel} · {domain} · {selectedVenue?.code || "Venue"} <small>· {agentCount} · {estimate} · {selectedVenue?.venue_collection}</small>
                </div>
              </div>
              <div className="s">
                <div className="l">Output language</div>
                <div className="language-toggle" role="group" aria-label="Output language">
                  <button className={outputLanguage === "zh" ? "on" : ""} onClick={() => setOutputLanguage("zh")}>中文</button>
                  <button className={outputLanguage === "en" ? "on" : ""} onClick={() => setOutputLanguage("en")}>EN</button>
                </div>
              </div>
            </div>
            <div className="actions">
              <button className="btn" type="button" disabled={presetStatus === "loading"} onClick={handleSavePreset}>
                <Save size={15} /> {presetStatus === "loading" ? "Saving..." : "Save preset"}
              </button>
              <button className="btn primary lg" type="button" disabled={!canBeginReview} onClick={handleBeginReview}>
                <Play size={15} /> {isActiveRun ? "Running..." : "Begin Review"} <span className="k">↵</span>
              </button>
            </div>
            {presetMessage ? <div className={`preset-feedback ${presetStatus}`}>{presetMessage}</div> : null}
            {runStatus !== "idle" ? (
              <div className={`run-feedback ${runStatus}`} role="status">
                {runStatus === "queued" ? (
                  <>
                    <b>Job queued</b>
                    <span>任务已创建，正在等待本地审稿流程启动。</span>
                    {runResult ? (
                      <div className="run-feedback-actions">
                        <button className="run-feedback-action danger" type="button" onClick={() => handleCancelJob(runResult.job_id)}>
                          <XCircle size={13} /> Cancel run
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : null}
                {runStatus === "running" ? (
                  <>
                    <b>Running workflow</b>
                    <span>正在运行 LangGraph 审稿流程，前端会持续刷新 job 状态。</span>
                    {runResult ? (
                      <div className="run-feedback-actions">
                        <button className="run-feedback-action danger" type="button" onClick={() => handleCancelJob(runResult.job_id)}>
                          <XCircle size={13} /> Cancel run
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : null}
                {runStatus === "succeeded" && runResult ? (
                  <>
                    <b>{runResult.final_decision || "SUCCEEDED"}</b>
                    <span>
                      Run {runResult.run_id.slice(0, 8)}
                      {artifactCount !== null ? ` · ${artifactCount} artifacts` : ""}
                      {" · "}{runResult.artifact_dir}
                    </span>
                    {reportPreview ? <span className="report-preview">{reportPreview}</span> : null}
                    <div className="run-feedback-actions">
                      <button className="run-feedback-action" type="button" onClick={() => handleRetryJob(runResult.job_id)}>
                        <RotateCcw size={13} /> Run again
                      </button>
                      <button className="run-feedback-action" type="button" onClick={() => openReportDetail(runResult.job_id)}>
                        <FileText size={13} /> Open report
                      </button>
                      <a
                        className="run-feedback-action"
                        href={getReviewArtifactDownloadUrl(runResult.job_id, "final_report.md")}
                        download="final_report.md"
                      >
                        <Download size={13} /> Download final_report.md
                      </a>
                    </div>
                  </>
                ) : null}
                {runStatus === "failed" ? (
                  <>
                    <b>Review failed</b>
                    <span>{runError}</span>
                    {runResult ? (
                      <div className="run-feedback-actions">
                        <button className="run-feedback-action" type="button" onClick={() => handleRetryJob(runResult.job_id)}>
                          <RotateCcw size={13} /> Retry run
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : null}
                {runStatus === "canceled" ? (
                  <>
                    <b>Review canceled</b>
                    <span>{runError || "This job was stopped before completion."}</span>
                    {runResult ? (
                      <div className="run-feedback-actions">
                        <button className="run-feedback-action" type="button" onClick={() => handleRetryJob(runResult.job_id)}>
                          <RotateCcw size={13} /> Retry run
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}
          </section>

          {runResult ? <ReviewTheater job={runResult} /> : null}
        </main>
        )}

        <aside className="rail" aria-label="Agent panel">
          <div className="rail-h">
            <div className="eb">
              <span className="n">PANEL</span>
              <span className="n strong">{railAgentLabel}</span>
            </div>
            <h2>
              The panel awaits.
              <span className="zh">本次审稿团队 · 拟人化智能体 · 各司其职</span>
            </h2>
            <div className="stat">
              <span className="x"><b>4</b> Reviewers · ‖</span>
              <span className="x"><b>{railEditorCount}</b> Editors</span>
              <span className="x"><b>4</b> Pre-proc + Context</span>
            </div>
          </div>

          <div className="roster">
            {agents.map((group) => (
              <div key={group.group} className="role-section">
                <div className="role-grouph">{group.group}</div>
                {group.items.map(([id, name, zh, brief], index) => (
                  <AgentRole
                    key={id}
                    id={id}
                    name={name}
                    zh={zh}
                    brief={brief}
                    index={index}
                    status={agentStatus(id, displayNodeStatuses)}
                    skipped={displayReviewMode === "QUICK_REVIEW" && ["se", "ae"].includes(id)}
                  />
                ))}
              </div>
            ))}
          </div>

          <div className="rail-stat-foot">
            <div className="row"><span>Catalog</span><b>{catalog.length} venues</b></div>
            <div className="row"><span>Selected</span><b>{railSelectedVenue}</b></div>
            <div className="row"><span>API</span><b>{health}</b></div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function CommandPalette(props: {
  open: boolean;
  items: CommandPaletteItem[];
  onClose: () => void;
  onRun: (item: CommandPaletteItem) => void;
}) {
  if (!props.open) {
    return null;
  }

  return (
    <div className="command-backdrop" role="presentation" onMouseDown={props.onClose}>
      <section
        className="command-palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="command-head">
          <div>
            <Command size={15} />
            <span>Command Palette</span>
          </div>
          <kbd>Esc</kbd>
        </div>
        <div className="command-list">
          {props.items.map((item) => (
            <button
              type="button"
              className={item.active ? "command-item active" : "command-item"}
              key={item.id}
              onClick={() => props.onRun(item)}
            >
              <span>
                <b>{item.title}</b>
                <small>{item.description}</small>
              </span>
              <em>{item.active ? "CURRENT" : item.shortcut}</em>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function DeleteRunsDialog(props: {
  open: boolean;
  runs: LibraryRun[];
  status: AsyncViewStatus;
  message: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!props.open) {
    return null;
  }

  const artifactCount = props.runs.reduce((total, run) => total + run.artifact_count, 0);
  const sizeBytes = props.runs.reduce((total, run) => total + run.total_size_bytes, 0);
  const title = props.runs.length === 1 ? "确认删除这 1 次审稿任务？" : `确认删除这 ${props.runs.length} 次审稿任务？`;
  const loading = props.status === "loading";

  return (
    <div className="confirm-backdrop" role="presentation" onMouseDown={loading ? undefined : props.onCancel}>
      <section
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Delete review run"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="confirm-mark"><Trash2 size={18} /></div>
        <div className="confirm-copy">
          <h2>{title}</h2>
          <p>会删除本次审稿生成的报告、诊断文件和中间 JSON。</p>
          <div className="confirm-meta">
            <span>{artifactCount} artifacts</span>
            <span>{formatBytes(sizeBytes)}</span>
          </div>
        </div>
        <div className="confirm-run-list">
          {props.runs.slice(0, 4).map((run) => (
            <div key={run.job_id}>
              <span>{paperBasename(run.paper_path)}</span>
              <small>{run.job_id.slice(0, 8)} · {run.venue_collection} · {run.venue_code}</small>
            </div>
          ))}
          {props.runs.length > 4 ? <em>+ {props.runs.length - 4} more runs</em> : null}
        </div>
        {props.message ? <div className={`confirm-error ${props.status}`}>{props.message}</div> : null}
        <div className="confirm-actions">
          <button className="report-link" type="button" onClick={props.onCancel} disabled={loading}>
            Cancel
          </button>
          <button className="confirm-delete" type="button" onClick={props.onConfirm} disabled={loading}>
            <Trash2 size={13} /> {loading ? "Deleting..." : props.runs.length === 1 ? "Delete run" : "Delete runs"}
          </button>
        </div>
      </section>
    </div>
  );
}

function AgentRole(props: {
  id: string;
  name: string;
  zh: string;
  brief: string;
  index: number;
  status: AgentNodeStatus;
  skipped: boolean;
}) {
  return (
    <div className={`role ${props.id === "da" ? "da" : ""} ${props.skipped ? "skipped" : ""} ${props.status}`}>
      <agent-px id={props.id} size="48" />
      <div className="nm">
        {props.name} <span className="zh">{props.zh}</span>
        <span className="brief">{props.brief}</span>
      </div>
      <span className="tag">{agentStatusLabel(props.status, props.index)}</span>
    </div>
  );
}

function ConfigBlock({ title, meta, children }: { title: string; meta: string; children: React.ReactNode }) {
  return (
    <div className="block">
      <div className="bh"><span className="lbl">{title}</span><span className="num">{meta}</span></div>
      {children}
    </div>
  );
}

function ModeOption(props: { active: boolean; title: string; subtitle: string; estimate: string; onClick: () => void }) {
  return (
    <button className={`mode ${props.active ? "on" : ""}`} type="button" onClick={props.onClick}>
      <span className="r" />
      <span className="nm">{props.title}<small>{props.subtitle}</small></span>
      <span className="est">{props.estimate}</span>
    </button>
  );
}

function DomainOption(props: { active: boolean; abbr: Domain; name: string; detail: string; onClick: () => void }) {
  return (
    <button className={`dom-tab ${props.active ? "on" : ""}`} type="button" onClick={props.onClick}>
      <div className="ab">{props.abbr} <span className="ck">{props.active ? <Check size={12} /> : "○"}</span></div>
      <div className="nm">{props.name}</div>
      <div className="ven">{props.detail}</div>
    </button>
  );
}

function PaperSpecimen() {
  const rows = [
    ["head", "", "30%"],
    ["t", "1", undefined],
    ["t", "", "70%"],
    ["", "3", undefined],
    ["short", "4", undefined],
    ["", "5", undefined],
    ["", "6", undefined],
    ["short", "7", undefined],
    ["", "8", undefined],
    ["", "9", undefined],
    ["shorter", "10", undefined],
    ["", "11", undefined],
    ["short", "12", undefined],
  ] as const;
  return (
    <div className="specimen" aria-hidden="true">
      {rows.map(([kind, number, width], index) => (
        <div className={`ln ${kind}`} key={index}>
          <span className="gut">{number}</span>
          <span className="bar" style={width ? { maxWidth: width } : undefined} />
        </div>
      ))}
      <div className="stamp">DRAFT</div>
    </div>
  );
}

function flattenCatalog(catalog: Record<string, Record<string, Omit<VenueCatalogItem, "domain" | "venue_collection">[]>>): VenueCatalogItem[] {
  return Object.entries(catalog).flatMap(([domain, collections]) =>
    Object.entries(collections).flatMap(([venueCollection, items]) =>
      items.map((item) => ({
        ...item,
        domain: domain as Domain,
        venue_collection: venueCollection as VenueCatalogItem["venue_collection"],
      })),
    ),
  );
}

function venueCollections(items: VenueCatalogItem[]): VenueCollection[] {
  const values = new Set(items.map((item) => item.venue_collection));
  return venueCollectionOrder.filter((item) => values.has(item));
}

function venueMembershipsForCode(items: VenueCatalogItem[], code: string): VenueCollection[] {
  const values = new Set(items.filter((item) => item.code === code).map((item) => item.venue_collection));
  return venueCollectionOrder.filter((item) => values.has(item));
}

function preferredVenueItems(items: VenueCatalogItem[], collection: VenueCollection): VenueCatalogItem[] {
  const byCode = new Map(items.map((item) => [item.code, item]));
  const preferred = (quickVenueCodes[collection] ?? [])
    .map((code) => byCode.get(code))
    .filter((item): item is VenueCatalogItem => Boolean(item));
  const used = new Set(preferred.map((item) => item.code));
  return [
    ...preferred,
    ...items.filter((item) => !used.has(item.code)).slice(0, Math.max(0, 8 - preferred.length)),
  ].slice(0, 8);
}

function pruneRunSelection(selection: Set<string>, runs: LibraryRun[]): Set<string> {
  const valid = new Set(runs.map((run) => run.job_id));
  return new Set([...selection].filter((key) => valid.has(key)));
}

function toRunStatus(status: ReviewJobResponse["status"]): RunStatus {
  if (status === "QUEUED") return "queued";
  if (status === "RUNNING") return "running";
  if (status === "SUCCEEDED") return "succeeded";
  if (status === "FAILED") return "failed";
  return "canceled";
}

function isLiveJobStatus(status: ReviewJobResponse["status"] | undefined): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

function canOpenJobReport(job: ReviewJobResponse): boolean {
  return (job.status === "SUCCEEDED" || job.status === "FAILED") && Boolean(job.artifact_dir);
}

function canRetryJob(job: ReviewJobResponse): boolean {
  return !isLiveJobStatus(job.status);
}

function currentDisplayJob(input: {
  viewMode: ViewMode;
  runResult: ReviewJobResponse | null;
  selectedHistoryJob: ReviewJobResponse | null;
  reportDetailJob: ReviewJobResponse | null;
}): ReviewJobResponse | null {
  if (input.viewMode === "report") return input.reportDetailJob;
  if (input.viewMode === "runs" && input.selectedHistoryJob) return input.selectedHistoryJob;
  return input.runResult;
}

function runStatusLabel(status: RunStatus): string {
  if (status === "queued") return "QUEUED";
  if (status === "running") return "RUNNING";
  if (status === "succeeded") return "DONE";
  if (status === "failed") return "ERROR";
  if (status === "canceled") return "CANCELED";
  return "READY";
}

function transientStatusLabel(viewMode: ViewMode, runStatus: RunStatus, reportDetailStatus: AsyncViewStatus): string {
  if (viewMode === "report" && reportDetailStatus === "loading") return "LOADING";
  if (viewMode === "report" && reportDetailStatus === "failed") return "ERROR";
  return runStatusLabel(runStatus);
}

function jobSummaryLabel(summary: ReviewJobsSummaryResponse): string {
  if (summary.active_count > 0) return `${summary.active_count} active`;
  if (summary.failed_count > 0) return `${summary.failed_count} failed`;
  return `${summary.count} total`;
}

function runProgressNextLabel(job: ReviewJobResponse): string {
  if (job.status === "SUCCEEDED") return "Done";
  if (job.status === "FAILED") return "Diagnostics";
  if (job.status === "CANCELED") return "Canceled";
  if (job.progress.active_nodes.length > 0) return job.progress.active_nodes.map(nodeDisplayName).join(" · ");
  if (job.progress.next_node) return nodeDisplayName(job.progress.next_node);
  return "Waiting";
}

function agentStatus(
  agentId: string,
  nodes: ReviewJobResponse["nodes"],
): AgentNodeStatus {
  const nodeNames = agentNodeMap[agentId] || [];
  const seenNodes = nodeNames.map((nodeName) => nodes[nodeName]).filter(Boolean);
  if (seenNodes.some((node) => node.status === "FAILED")) return "failed";
  if (seenNodes.some((node) => node.status === "RUNNING")) return "running";
  if (seenNodes.length > 0 && seenNodes.every((node) => node.status === "SUCCEEDED")) return "done";
  return "pending";
}

function agentStatusLabel(status: AgentNodeStatus, index: number): string {
  if (status === "running") return "RUN";
  if (status === "done") return "OK";
  if (status === "failed") return "ERR";
  return String(index + 1).padStart(2, "0");
}

function compactReportPreview(content: string): string {
  const text = content.replace(/\s+/g, " ").trim();
  if (text.length <= 280) return text;
  return `${text.slice(0, 280)}...`;
}

type WorkflowTimelineItem = {
  key: string;
  label: string;
  meta: string;
  badge: string;
  status: "running" | "done" | "failed" | "pending";
};

function workflowTimelineItems(job: ReviewJobResponse): WorkflowTimelineItem[] {
  if (job.node_events.length > 0) {
    return job.node_events.slice(-18).map((event, index) => ({
      key: `${event.timestamp}-${event.node}-${event.event}-${index}`,
      label: nodeDisplayName(event.node),
      meta: `${nodeEventLabel(event.event)} · ${formatRunTime(event.timestamp)}`,
      badge: event.elapsed_ms === undefined ? event.error_type || "" : formatElapsedMs(event.elapsed_ms),
      status: nodeEventStatus(event.event),
    }));
  }

  return Object.values(job.nodes)
    .sort((a, b) => String(a.updated_at || "").localeCompare(String(b.updated_at || "")))
    .map((node) => ({
      key: node.node,
      label: nodeDisplayName(node.node),
      meta: node.updated_at ? `Snapshot · ${formatRunTime(node.updated_at)}` : "Snapshot",
      badge: node.elapsed_ms === undefined ? node.error_type || "" : formatElapsedMs(node.elapsed_ms),
      status: nodeSnapshotStatus(node.status),
    }));
}

function RunsView(props: {
  jobs: ReviewJobResponse[];
  status: AsyncViewStatus;
  filter: ReviewJobsFilter;
  query: string;
  selectedReport: ReviewReportResponse | null;
  onRefresh: () => void;
  onFilterChange: (filter: ReviewJobsFilter) => void;
  onQueryChange: (query: string) => void;
  onCancel: (jobId: string) => void;
  onRetry: (jobId: string) => void;
  onOpenReport: (job: ReviewJobResponse) => void;
  onOpenDetail: (jobId: string) => void;
}) {
  return (
    <main className="hero runs-hero" aria-label="Review runs">
      <div className="runs-head">
        <div className="h-head">
          <div className="eyebrow">RUN HISTORY · 历史审稿</div>
          <h1>
            Review runs.
            <span className="zh">查看本地异步审稿任务、状态和最终报告。</span>
          </h1>
        </div>
        <div className="runs-toolbar">
          <label className="run-search" aria-label="Search review runs">
            <Search size={14} />
            <input
              value={props.query}
              onChange={(event) => props.onQueryChange(event.currentTarget.value)}
              placeholder="Search paper, job, venue"
            />
          </label>
          <div className="run-status-filter" role="group" aria-label="Run status filter">
            {runFilters.map((item) => (
              <button
                type="button"
                className={props.filter === item.value ? "on" : ""}
                key={item.value}
                onClick={() => props.onFilterChange(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <button className="btn" type="button" onClick={props.onRefresh} disabled={props.status === "loading"}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
      </div>

      <section className="runs-panel" aria-label="Local review job history">
        <div className="runs-table-head">
          <span>Job</span>
          <span>Status</span>
          <span>Venue</span>
          <span>Mode</span>
          <span>Progress</span>
          <span>Updated</span>
          <span>Report</span>
        </div>
        {props.status === "loading" ? <div className="runs-message">Loading local runs...</div> : null}
        {props.status === "failed" ? <div className="runs-message error">Failed to load local runs.</div> : null}
        {props.status === "ready" && props.jobs.length === 0 ? (
          <div className="runs-message">No review runs match this filter.</div>
        ) : null}
        {props.jobs.map((job) => (
          <div className="run-row" key={job.job_id}>
            <div className="run-main">
              <span className="run-id">{job.job_id.slice(0, 8)}</span>
              <span className="run-paper">{paperBasename(job.request.paper_path)}</span>
            </div>
            <span className={`run-pill ${job.status.toLowerCase()}`}>{job.status}</span>
            <span className="run-meta">{job.request.venue_collection} · {job.request.venue_code}</span>
            <span className="run-meta">{job.request.review_mode === "FULL_REVIEW" ? "Full" : "Quick"}</span>
            <RunProgressCell job={job} />
            <span className="run-meta">{formatRunTime(job.updated_at)}</span>
            <div className="report-actions">
              <button
                className="report-link"
                type="button"
                disabled={!canOpenJobReport(job)}
                onClick={() => props.onOpenReport(job)}
              >
                <FileText size={13} /> Preview
              </button>
              <button
                className="report-link"
                type="button"
                onClick={() => props.onOpenDetail(job.job_id)}
              >
                {job.status === "SUCCEEDED" ? "Open" : "Inspect"}
              </button>
              {isLiveJobStatus(job.status) ? (
                <button
                  className="report-link danger"
                  type="button"
                  onClick={() => props.onCancel(job.job_id)}
                >
                  <XCircle size={13} /> Cancel
                </button>
              ) : null}
              {canRetryJob(job) ? (
                <button
                  className="report-link"
                  type="button"
                  onClick={() => props.onRetry(job.job_id)}
                >
                  <RotateCcw size={13} /> {job.status === "SUCCEEDED" ? "Run again" : "Retry"}
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </section>

      <section className="run-report-panel" aria-label="Selected report preview">
        <div className="runs-section-title">Report preview</div>
        {props.selectedReport ? (
          <>
            <div className="report-meta">
              <div className="report-meta-text">
                <span>{props.selectedReport.job_id.slice(0, 8)}</span>
                <span>{props.selectedReport.name}</span>
              </div>
              <a
                className="report-download"
                href={getReviewArtifactDownloadUrl(props.selectedReport.job_id, props.selectedReport.name)}
                download={props.selectedReport.name}
              >
                <Download size={13} /> Download
              </a>
              <button className="report-download" type="button" onClick={() => props.onOpenDetail(props.selectedReport?.job_id || "")}>
                <FileText size={13} /> Open full
              </button>
            </div>
            <pre className="run-report-preview">{reportPreviewBlock(props.selectedReport.content)}</pre>
          </>
        ) : (
          <p>选择一个已完成或已生成 partial report 的 run 查看 Markdown 报告预览。</p>
        )}
      </section>
    </main>
  );
}

function LibraryView(props: {
  expandedKeys: Set<string>;
  deleteMessage: string;
  deleteStatus: AsyncViewStatus;
  runs: LibraryRun[];
  selectedKeys: Set<string>;
  status: AsyncViewStatus;
  onDeleteSelected: (runs: LibraryRun[]) => void;
  onRefresh: () => void;
  onOpenRun: (jobId: string) => void;
  onToggleAll: () => void;
  onToggleExpanded: (run: LibraryRun) => void;
  onToggleRun: (run: LibraryRun) => void;
}) {
  const artifactCount = props.runs.reduce((total, run) => total + run.artifact_count, 0);
  const reportRuns = props.runs.filter((run) => run.primary_report_name).length;
  const selectedRuns = props.runs.filter((run) => props.selectedKeys.has(run.job_id));
  const allSelected = props.runs.length > 0 && selectedRuns.length === props.runs.length;
  return (
    <main className="hero library-hero" aria-label="Artifact library">
      <div className="library-head">
        <div className="h-head">
          <div className="eyebrow">ARTIFACT LIBRARY · 本地产物库</div>
          <h1>
            Review runs.
            <span className="zh">按一次审稿任务管理报告、诊断文件和中间产物。</span>
          </h1>
        </div>
        <button className="btn" type="button" onClick={props.onRefresh} disabled={props.status === "loading"}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      <section className="library-summary" aria-label="Artifact summary">
        <div>
          <span>{props.runs.length}</span>
          <small>runs</small>
        </div>
        <div>
          <span>{reportRuns}</span>
          <small>reports</small>
        </div>
        <div>
          <span>{artifactCount}</span>
          <small>artifacts</small>
        </div>
      </section>

      <section className="library-panel" aria-label="Local review artifacts">
        <div className="library-bulkbar">
          <label className="artifact-check all">
            <input
              type="checkbox"
              checked={allSelected}
              disabled={props.runs.length === 0}
              onChange={props.onToggleAll}
            />
            <span>{selectedRuns.length > 0 ? `${selectedRuns.length} selected` : "Select review runs"}</span>
          </label>
          <button
            className="report-link danger"
            type="button"
            disabled={selectedRuns.length === 0 || props.deleteStatus === "loading"}
            onClick={() => props.onDeleteSelected(selectedRuns)}
          >
            <XCircle size={13} /> {props.deleteStatus === "loading" ? "Deleting..." : "Delete selected runs"}
          </button>
          {props.deleteMessage ? <span className={`library-delete-message ${props.deleteStatus}`}>{props.deleteMessage}</span> : null}
        </div>
        <div className="library-table-head">
          <span />
          <span />
          <span>Review run</span>
          <span>Venue</span>
          <span>Files</span>
          <span>Updated</span>
          <span>Action</span>
        </div>
        {props.status === "loading" ? <div className="runs-message">Loading local review runs...</div> : null}
        {props.status === "failed" ? <div className="runs-message error">Failed to load artifact library.</div> : null}
        {props.status === "ready" && props.runs.length === 0 ? (
          <div className="runs-message">No review runs yet.</div>
        ) : null}
        {props.runs.map((run) => {
          const expanded = props.expandedKeys.has(run.job_id);
          return (
          <div className={expanded ? "library-row expanded" : "library-row"} key={run.job_id}>
            <label className="artifact-check" aria-label={`Select ${paperBasename(run.paper_path)}`}>
              <input
                type="checkbox"
                checked={props.selectedKeys.has(run.job_id)}
                onChange={() => props.onToggleRun(run)}
              />
            </label>
            <button
              className="library-expand"
              type="button"
              aria-label={expanded ? "Collapse artifacts" : "Expand artifacts"}
              aria-expanded={expanded}
              onClick={() => props.onToggleExpanded(run)}
            >
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            <div className="library-artifact">
              <span>{paperBasename(run.paper_path)}</span>
              <small>{run.job_id.slice(0, 8)} · {humanReviewMode(run.review_mode)} · {run.job_status}</small>
            </div>
            <div className="library-venue">
              <span>{run.venue_collection} · {run.venue_code}</span>
              <small>{run.final_decision || run.job_status}</small>
            </div>
            <div className="library-venue">
              <span>{run.artifact_count} files</span>
              <small>{formatBytes(run.total_size_bytes)} · {run.report_count} reports</small>
            </div>
            <span className="run-meta">{formatRunTime(run.updated_at)}</span>
            <div className="library-actions">
              <button className="report-link" type="button" onClick={() => props.onOpenRun(run.job_id)}>
                Open
              </button>
              {run.primary_report_download_url ? (
                <a className="report-download" href={getApiDownloadUrl(run.primary_report_download_url)} download={run.primary_report_name}>
                  <Download size={13} /> Report
                </a>
              ) : null}
              <button className="report-link danger" type="button" onClick={() => props.onDeleteSelected([run])}>
                <Trash2 size={13} /> Delete
              </button>
            </div>
            {expanded ? (
              <div className="library-run-expanded">
                {run.artifacts.length === 0 ? (
                  <span className="library-empty-artifacts">No artifacts found in this run.</span>
                ) : (
                  run.artifacts.map((artifact) => (
                    <div className="library-artifact-line" key={`${run.job_id}-${artifact.name}`}>
                      <div>
                        <span>{artifact.name}</span>
                        <small>{artifact.content_type} · {formatBytes(artifact.size_bytes)}</small>
                      </div>
                      <a className="report-download" href={getApiDownloadUrl(artifact.download_url)} download={artifact.name}>
                        <Download size={13} /> Download
                      </a>
                    </div>
                  ))
                )}
              </div>
            ) : null}
          </div>
        );
        })}
      </section>
    </main>
  );
}

function ReportDetailView(props: {
  job: ReviewJobResponse | null;
  artifacts: ReviewArtifact[];
  report: ReviewReportResponse | null;
  diagnostics: ReviewDiagnosticsResponse | null;
  llmCalls: ReviewLLMCallsResponse | null;
  status: AsyncViewStatus;
  error: string;
  autoRefreshing: boolean;
  onBackToRuns: () => void;
  onCancel: (jobId: string) => void;
  onRetry: (jobId: string) => void;
  onRefresh: (jobId: string) => void;
}) {
  const job = props.job;
  const primaryReport = props.report
    ? props.artifacts.find((artifact) => artifact.name === props.report?.name)
    : props.artifacts.find((artifact) => artifact.name === "final_report.md" || artifact.name === "partial_report.md");
  const reportLabel = props.report?.name === "partial_report.md" ? "Partial Markdown" : "Final Markdown";
  const workflowItems = job ? workflowTimelineItems(job) : [];
  return (
    <main className="hero report-hero" aria-label="Report detail">
      <div className="report-detail-head">
        <div className="h-head">
          <div className="eyebrow">REPORT DETAIL · 审稿报告</div>
          <h1>
            Review report.
            <span className="zh">查看某一次审稿 run 的完整 Markdown 报告、状态和本地产物。</span>
          </h1>
        </div>
        <div className="report-detail-actions">
          {props.autoRefreshing ? <span className="auto-refresh-chip">Auto-refreshing</span> : null}
          <button className="btn" type="button" onClick={props.onBackToRuns}>
            <ArrowLeft size={15} /> Runs
          </button>
          <button
            className="btn"
            type="button"
            disabled={!job || props.status === "loading"}
            onClick={() => job ? props.onRefresh(job.job_id) : undefined}
          >
            <RefreshCw size={15} /> Refresh
          </button>
          {job && isLiveJobStatus(job.status) ? (
            <button className="btn danger" type="button" onClick={() => props.onCancel(job.job_id)}>
              <XCircle size={15} /> Cancel
            </button>
          ) : null}
          {job && canRetryJob(job) ? (
            <button className="btn" type="button" onClick={() => props.onRetry(job.job_id)}>
              <RotateCcw size={15} /> {job.status === "SUCCEEDED" ? "Run again" : "Retry"}
            </button>
          ) : null}
        </div>
      </div>

      {props.status === "loading" ? <div className="runs-message">Loading report detail...</div> : null}
      {props.status === "failed" ? <div className="runs-message error">{props.error || "Failed to load report detail."}</div> : null}

      {job ? (
        <>
          <section className="report-detail-grid" aria-label="Run summary">
            <ReportMetric label="Run" value={job.job_id.slice(0, 8)} detail={job.run_id ? `run ${job.run_id.slice(0, 8)}` : job.status} />
            <ReportMetric label="Decision" value={job.final_decision || job.status} detail={`${job.request.venue_collection} · ${job.request.venue_code}`} />
            <ReportMetric label="Mode" value={humanReviewMode(job.request.review_mode)} detail={job.request.output_language === "zh" ? "Chinese output" : "English output"} />
            <ReportMetric label="Updated" value={formatRunTime(job.updated_at)} detail={paperBasename(job.request.paper_path)} />
          </section>

          <ReviewTheater job={job} />

          <section className="report-detail-layout" aria-label="Report and artifacts">
            <aside className="artifact-side">
              <div className="runs-section-title">Artifacts</div>
              {props.artifacts.length === 0 ? (
                <p>{job.status === "SUCCEEDED" ? "No artifacts found." : "No failure artifacts are available for this run."}</p>
              ) : null}
              <div className="artifact-list">
                {props.artifacts.map((artifact) => (
                  <a
                    key={artifact.name}
                    href={getReviewArtifactDownloadUrl(job.job_id, artifact.name)}
                    download={artifact.name}
                  >
                    <span>{artifact.name}</span>
                    <small>{formatBytes(artifact.size_bytes)}</small>
                  </a>
                ))}
              </div>

              <DiagnosticsPanel diagnostics={props.diagnostics} llmCalls={props.llmCalls} job={job} />

              <div className="workflow-side-section">
                <div className="runs-section-title">Workflow</div>
                {workflowItems.length === 0 ? (
                  <p>No node events have been recorded yet.</p>
                ) : (
                  <div className="workflow-timeline" aria-label="Workflow node timeline">
                    {workflowItems.map((item) => (
                      <div className={`workflow-event ${item.status}`} key={item.key}>
                        <span className="workflow-dot" />
                        <div className="workflow-event-main">
                          <b>{item.label}</b>
                          <small>{item.meta}</small>
                        </div>
                        <em>{item.badge}</em>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </aside>

            <article className="report-document">
              <div className="report-document-head">
                <div>
                  <div className="runs-section-title">{reportLabel}</div>
                  <p>{props.report ? props.report.name : "Markdown report is not available for this run yet."}</p>
                </div>
                {props.report && primaryReport ? (
                  <a
                    className="report-download"
                    href={getReviewArtifactDownloadUrl(job.job_id, primaryReport.name)}
                    download={primaryReport.name}
                  >
                    <Download size={13} /> Download
                  </a>
                ) : null}
              </div>
              {props.report ? (
                <MarkdownReport content={props.report.content} />
              ) : job.status === "FAILED" ? (
                <RunIssuePanel job={job} />
              ) : (
                <div className="report-empty-state">
                  这个 run 还没有可展示的最终报告。当前状态：{job.status}。
                </div>
              )}
            </article>
          </section>
        </>
      ) : null}
    </main>
  );
}

function RunProgressCell({ job }: { job: ReviewJobResponse }) {
  const percent = job.progress.total_nodes > 0 ? job.progress.percent : job.status === "SUCCEEDED" ? 100 : 0;
  const next = runProgressNextLabel(job);
  return (
    <div className="run-progress-cell">
      <div className="run-progress-top">
        <span>{percent}%</span>
        <small>{job.progress.completed_nodes}/{job.progress.total_nodes || "-"}</small>
      </div>
      <div className="run-progress-bar" aria-label={`Run progress ${percent}%`}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <em>{next}</em>
    </div>
  );
}

function MarkdownReport({ content }: { content: string }) {
  return (
    <div className="report-document-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target={href?.startsWith("http") ? "_blank" : undefined}
              rel={href?.startsWith("http") ? "noreferrer" : undefined}
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function DiagnosticsPanel(props: { diagnostics: ReviewDiagnosticsResponse | null; llmCalls: ReviewLLMCallsResponse | null; job: ReviewJobResponse }) {
  const diagnostics = props.diagnostics?.diagnostics;
  if (!diagnostics) {
    return null;
  }
  const errors = Array.isArray(diagnostics.errors) ? diagnostics.errors : [];
  const fallbackEvents = Array.isArray(diagnostics.fallback_events) ? diagnostics.fallback_events : [];
  const llmCalls = diagnostics.llm_calls && typeof diagnostics.llm_calls === "object" ? diagnostics.llm_calls : {};
  const firstError = firstDiagnosticError(errors);
  const rows: [string, string][] = [
    ["Status", textFromUnknown(diagnostics.status) || props.job.status],
    ["Errors", String(errors.length)],
    ["Fallbacks", String(fallbackEvents.length)],
    ["LLM Calls", numberFromUnknown(llmCalls.call_count)],
    ["LLM Errors", numberFromUnknown(llmCalls.error_count)],
    ["LLM Fallbacks", numberFromUnknown(llmCalls.fallback_count)],
  ];
  if (firstError) {
    rows.push(["Error type", textFromUnknown(firstError.error_type) || "-"]);
    rows.push(["Node", textFromUnknown(firstError.node) || lastFailedNode(props.job) || "-"]);
    rows.push(["Provider", textFromUnknown(firstError.provider) || "-"]);
    rows.push(["Model", textFromUnknown(firstError.model) || "-"]);
  }

  return (
    <div className="diagnostics-panel">
      <div className="runs-section-title">Diagnostics</div>
      <div className="diagnostics-grid">
        {rows.map(([label, value]) => (
          <div key={label}>
            <small>{label}</small>
            <span>{value}</span>
          </div>
        ))}
      </div>
      {firstError ? <p>{textFromUnknown(firstError.message) || "No diagnostic message."}</p> : null}
      <LLMCallTimeline llmCalls={props.llmCalls} />
    </div>
  );
}

function LLMCallTimeline({ llmCalls }: { llmCalls: ReviewLLMCallsResponse | null }) {
  const events = llmCalls?.events ?? [];
  const visibleEvents = events.slice(-8);
  return (
    <div className="llm-call-section">
      <div className="runs-section-title">LLM Timeline</div>
      {visibleEvents.length === 0 ? (
        <p>No LLM call events were recorded for this run.</p>
      ) : (
        <div className="llm-call-timeline" aria-label="LLM call timeline">
          {visibleEvents.map((event, index) => (
            <div className={`llm-call-event ${llmEventStatus(event.event)}`} key={`${event.timestamp || index}-${event.event}`}>
              <span className="workflow-dot" />
              <div className="llm-call-main">
                <b>{llmEventLabel(event)}</b>
                <small>{llmEventMeta(event)}</small>
              </div>
              <em>{event.elapsed_ms !== null && event.elapsed_ms !== undefined ? formatElapsedMs(event.elapsed_ms) : event.event}</em>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RunIssuePanel({ job }: { job: ReviewJobResponse }) {
  const error = job.error || {};
  const rows: [string, string][] = [
    ["Error type", textFromUnknown(error.error_type) || "Unknown"],
    ["Node", textFromUnknown(error.node) || lastFailedNode(job) || "-"],
    ["Provider", textFromUnknown(error.provider) || "-"],
    ["Model", textFromUnknown(error.model) || "-"],
  ];
  return (
    <div className="run-issue-panel">
      <div className="run-issue-head">
        <span>Run issue</span>
        <b>{job.status}</b>
      </div>
      <p>{textFromUnknown(error.message) || "This review job did not produce a final report."}</p>
      <div className="run-issue-grid">
        {rows.map(([label, value]) => (
          <div key={label}>
            <small>{label}</small>
            <span>{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function firstDiagnosticError(errors: Array<Record<string, unknown>>): Record<string, unknown> | null {
  return errors.find((item) => item && typeof item === "object") ?? null;
}

function ReportMetric(props: { label: string; value: string; detail: string }) {
  return (
    <div className="report-metric">
      <small>{props.label}</small>
      <span>{props.value}</span>
      <b>{props.detail}</b>
    </div>
  );
}

function VenuesView(props: {
  catalog: VenueCatalogItem[];
  selectedVenue: VenueCatalogItem | undefined;
  onUseVenue: (item: VenueCatalogItem) => void;
}) {
  const [activeDomain, setActiveDomain] = useState<"ALL" | Domain>("ALL");
  const [activeCollection, setActiveCollection] = useState<VenueCollectionFilter>("ALL");
  const [query, setQuery] = useState("");

  const collections = useMemo(() => {
    const values = new Set<VenueCatalogItem["venue_collection"]>();
    props.catalog.forEach((item) => values.add(item.venue_collection));
    return Array.from(values).sort();
  }, [props.catalog]);

  const visibleVenues = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return props.catalog
      .filter((item) => activeDomain === "ALL" || item.domain === activeDomain)
      .filter((item) => activeCollection === "ALL" || item.venue_collection === activeCollection)
      .filter((item) => {
        if (!needle) return true;
        return `${item.code} ${item.name} ${item.venue_collection}`.toLowerCase().includes(needle);
      })
      .slice(0, 120);
  }, [activeCollection, activeDomain, props.catalog, query]);

  const counts = venueCounts(props.catalog);

  return (
    <main className="hero venues-hero" aria-label="Venue catalog">
      <div className="venues-head">
        <div className="h-head">
          <div className="eyebrow">VENUE CATALOG · 期刊会议库</div>
          <h1>
            Target venues.
            <span className="zh">浏览当前系统支持的 CS / IS 期刊会议，并把目标 venue 带回审稿首页。</span>
          </h1>
        </div>
        <div className="venue-count-card">
          <span>{props.catalog.length}</span>
          <small>venues</small>
        </div>
      </div>

      <section className="venues-toolbar" aria-label="Venue filters">
        <div className="venues-search">
          <Search size={14} />
          <input
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            placeholder="Search code, name, collection"
          />
        </div>
        <div className="venue-filter-row">
          {(["ALL", "CS", "IS"] as const).map((item) => (
            <button
              key={item}
              className={activeDomain === item ? "on" : ""}
              type="button"
              onClick={() => setActiveDomain(item)}
            >
              {item === "ALL" ? "All" : item} <span>{item === "ALL" ? props.catalog.length : counts.domain[item]}</span>
            </button>
          ))}
        </div>
        <div className="venue-filter-row">
          <button
            className={activeCollection === "ALL" ? "on" : ""}
            type="button"
            onClick={() => setActiveCollection("ALL")}
          >
            All collections <span>{props.catalog.length}</span>
          </button>
          {collections.map((item) => (
            <button
              key={item}
              className={activeCollection === item ? "on" : ""}
              type="button"
              onClick={() => setActiveCollection(item)}
            >
              {item} <span>{counts.collection[item] ?? 0}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="venues-panel" aria-label="Supported venues">
        <div className="venues-table-head">
          <span>Code</span>
          <span>Name</span>
          <span>Domain</span>
          <span>Collection</span>
          <span>Action</span>
        </div>
        {visibleVenues.length === 0 ? (
          <div className="venues-message">No venues match this filter.</div>
        ) : null}
        {visibleVenues.map((item) => {
          const selected = props.selectedVenue?.code === item.code && props.selectedVenue?.venue_collection === item.venue_collection;
          return (
            <div className={`venue-row ${selected ? "selected" : ""}`} key={`${item.domain}-${item.venue_collection}-${item.code}`}>
              <div className="venue-code">
                <span>{item.code}</span>
                {selected ? <small>selected</small> : null}
              </div>
              <div className="venue-name">{item.name}</div>
              <span className="venue-chip">{item.domain}</span>
              <span className="venue-chip">{item.venue_collection}</span>
              <button type="button" className="report-link" onClick={() => props.onUseVenue(item)}>
                Use
              </button>
            </div>
          );
        })}
      </section>
    </main>
  );
}

function SettingsView(props: {
  appConfig: AppConfigResponse;
  apiBaseUrl: string;
  catalogCount: number;
  health: "checking" | "ok" | "offline";
  llmConfig: LLMRuntimeConfigResponse | null;
  llmConfigStatus: AsyncViewStatus;
  openApiSummary: OpenApiSummary | null;
  openApiStatus: AsyncViewStatus;
  outputLanguage: OutputLanguage;
  presets: ReviewPresetResponse[];
  presetsStatus: AsyncViewStatus;
  reviewMode: ReviewMode;
  onRefreshLLMConfig: () => void;
  onRefreshPresets: () => void;
  onUsePreset: (preset: ReviewPresetResponse) => void;
}) {
  const uploadLabels = props.appConfig.supported_upload_extensions.map((item) => item.replace(/^\./, "").toUpperCase());
  return (
    <main className="hero settings-hero" aria-label="Settings">
      <div className="settings-head">
        <div className="h-head">
          <div className="eyebrow">SYSTEM SETTINGS · 系统状态</div>
          <h1>
            Runtime settings.
            <span className="zh">当前前端读取到的后端契约、上传限制和本地开发状态。</span>
          </h1>
        </div>
        <span className={`settings-health ${props.health}`}>{props.health.toUpperCase()}</span>
      </div>

      <section className="settings-grid" aria-label="Runtime configuration">
        <SettingsCard
          title="API"
          rows={[
            ["Base URL", props.apiBaseUrl],
            ["Health", props.health],
          ]}
        />
        <SettingsCard
          title="Upload"
          rows={[
            ["Types", uploadLabels.join(" / ")],
            ["Max size", formatBytes(props.appConfig.max_upload_bytes)],
          ]}
        />
        <SettingsCard
          title="Review Defaults"
          rows={[
            ["Default mode", humanReviewMode(props.appConfig.default_review_mode)],
            ["Default language", props.appConfig.default_output_language === "zh" ? "Chinese" : "English"],
            ["Current mode", humanReviewMode(props.reviewMode)],
            ["Current language", props.outputLanguage === "zh" ? "Chinese" : "English"],
          ]}
        />
        <LLMConfigCard
          config={props.llmConfig}
          status={props.llmConfigStatus}
          onRefresh={props.onRefreshLLMConfig}
        />
        <PresetsCard
          presets={props.presets}
          status={props.presetsStatus}
          onRefresh={props.onRefreshPresets}
          onUsePreset={props.onUsePreset}
        />
        <SettingsCard
          title="Catalog"
          rows={[
            ["Loaded venues", String(props.catalogCount)],
            ["Source", "GET /api/venue-catalog"],
          ]}
        />
        <SettingsCard
          title="API Contract"
          rows={[
            ["Status", props.openApiStatus],
            ["Title", props.openApiSummary?.title || "Unavailable"],
            ["Paths", props.openApiSummary ? String(props.openApiSummary.path_count) : "-"],
            ["Schemas", props.openApiSummary ? String(props.openApiSummary.schema_count) : "-"],
          ]}
          action={{
            href: getOpenApiDownloadUrl(),
            label: "Open OpenAPI",
          }}
        />
      </section>
    </main>
  );
}

function LLMConfigCard(props: {
  config: LLMRuntimeConfigResponse | null;
  status: AsyncViewStatus;
  onRefresh: () => void;
}) {
  const config = props.config;
  const readyProviders = config?.providers.filter((provider) => provider.base_url_configured && provider.api_key_configured).length ?? 0;
  const rows: [string, string][] = config
    ? [
        ["Status", config.status],
        ["Mode", config.mode],
        ["Default", config.default_model || "-"],
        ["Providers", `${readyProviders}/${config.providers.length} ready`],
        ["Models", String(config.models.length)],
        ["Prompts", String(config.prompts.length)],
      ]
    : [
        ["Status", props.status],
        ["Mode", "-"],
      ];
  const promptRoutes = config?.prompts.slice(0, 5) ?? [];

  return (
    <div className="settings-card presets-card llm-card">
      <div className="settings-card-title">
        <span>LLM Routing</span>
        <button type="button" onClick={props.onRefresh} disabled={props.status === "loading"}>
          <RefreshCw size={12} /> Refresh
        </button>
      </div>
      <div className="settings-kv">
        {rows.map(([label, value]) => (
          <div className="settings-kv-row" key={label}>
            <span>{label}</span>
            <b>{value}</b>
          </div>
        ))}
      </div>
      {config?.status === "error" ? <p className="preset-empty error">{config.error_type}: {config.error_message}</p> : null}
      {promptRoutes.length > 0 ? (
        <div className="preset-list" aria-label="LLM prompt routes">
          {promptRoutes.map((prompt) => (
            <div className="preset-row" key={prompt.name}>
              <div>
                <b>{prompt.name}</b>
                <span>{prompt.model} · {prompt.provider || "unregistered"}</span>
              </div>
              <button type="button" disabled>{prompt.registered ? "OK" : "MISS"}</button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PresetsCard(props: {
  presets: ReviewPresetResponse[];
  status: AsyncViewStatus;
  onRefresh: () => void;
  onUsePreset: (preset: ReviewPresetResponse) => void;
}) {
  return (
    <div className="settings-card presets-card">
      <div className="settings-card-title">
        <span>Saved Presets</span>
        <button type="button" onClick={props.onRefresh} disabled={props.status === "loading"}>
          <RefreshCw size={12} /> Refresh
        </button>
      </div>
      {props.status === "loading" ? <div className="preset-empty">Loading presets...</div> : null}
      {props.status === "failed" ? <div className="preset-empty error">Failed to load presets.</div> : null}
      {props.status === "ready" && props.presets.length === 0 ? <div className="preset-empty">No saved presets yet.</div> : null}
      {props.presets.slice(0, 5).map((preset) => (
        <div className="preset-row" key={preset.preset_id}>
          <div>
            <b>{preset.name}</b>
            <span>
              {humanReviewMode(preset.review_mode)} · {preset.venue_domain} · {preset.venue_code} · {preset.output_language === "zh" ? "中文" : "EN"}
            </span>
          </div>
          <button type="button" onClick={() => props.onUsePreset(preset)}>Use</button>
        </div>
      ))}
    </div>
  );
}

function SettingsCard(props: { title: string; rows: [string, string][]; action?: { href: string; label: string } }) {
  return (
    <div className="settings-card">
      <div className="settings-card-title">{props.title}</div>
      <div className="settings-kv">
        {props.rows.map(([key, value]) => (
          <div className="settings-kv-row" key={key}>
            <span>{key}</span>
            <b>{value}</b>
          </div>
        ))}
      </div>
      {props.action ? (
        <a className="settings-action" href={props.action.href} target="_blank" rel="noreferrer">
          {props.action.label}
        </a>
      ) : null}
    </div>
  );
}

function initialViewMode(): ViewMode {
  if (window.location.hash === "#runs") return "runs";
  if (window.location.hash === "#library") return "library";
  if (window.location.hash.startsWith("#report=")) return "report";
  if (window.location.hash === "#venues") return "venues";
  if (window.location.hash === "#settings") return "settings";
  return "workbench";
}

function viewPrimaryLabel(viewMode: ViewMode): string {
  if (viewMode === "runs") return "Runs";
  if (viewMode === "library") return "Library";
  if (viewMode === "report") return "Report";
  if (viewMode === "venues") return "Venues";
  if (viewMode === "settings") return "Settings";
  return "Workbench";
}

function viewSecondaryLabel(viewMode: ViewMode): string {
  if (viewMode === "runs") return "History";
  if (viewMode === "library") return "Runs";
  if (viewMode === "report") return "Detail";
  if (viewMode === "venues") return "Catalog";
  if (viewMode === "settings") return "Runtime";
  return "New review";
}

function reportJobIdFromHash(): string {
  const prefix = "#report=";
  if (!window.location.hash.startsWith(prefix)) return "";
  return decodeURIComponent(window.location.hash.slice(prefix.length));
}

function venueCounts(catalog: VenueCatalogItem[]): {
  domain: Record<Domain, number>;
  collection: Partial<Record<VenueCatalogItem["venue_collection"], number>>;
} {
  const domainCounts: Record<Domain, number> = { CS: 0, IS: 0 };
  const collectionCounts: Partial<Record<VenueCatalogItem["venue_collection"], number>> = {};
  catalog.forEach((item) => {
    domainCounts[item.domain] += 1;
    collectionCounts[item.venue_collection] = (collectionCounts[item.venue_collection] ?? 0) + 1;
  });
  return { domain: domainCounts, collection: collectionCounts };
}

function paperBasename(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

function fileExtension(filename: string): string {
  const dotIndex = filename.lastIndexOf(".");
  if (dotIndex < 0) return "";
  return filename.slice(dotIndex).toLowerCase();
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${Math.round(bytes / (1024 * 1024))} MB`;
  }
  if (bytes >= 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${bytes} B`;
}

function humanReviewMode(mode: ReviewMode): string {
  return mode === "FULL_REVIEW" ? "Full Review" : "Quick Review";
}

function nodeDisplayName(nodeName: string): string {
  const labelMap: Record<string, string> = {
    doc_parse: "Parser",
    content_check: "Content Checker",
    journal_req_collector: "Journal Collector",
    field_analyst: "Field Analyst",
    se_check: "Senior Editor",
    ae_check: "Associate Editor",
    review_dispatch: "Review Dispatch",
    reviewer1: "Reviewer 1",
    reviewer2: "Reviewer 2",
    reviewer3: "Reviewer 3",
    devils_advocate: "Devil's Advocate",
    ae_final: "AE Final",
    final_artifact_render: "Artifact Renderer",
    invalid_file: "Invalid File Output",
    desk_reject_output: "Desk Reject Output",
    parse_fail_output: "Parse Failure Output",
  };
  return labelMap[nodeName] || nodeName;
}

function nodeEventLabel(event: string): string {
  if (event === "start") return "Started";
  if (event === "done") return "Finished";
  if (event === "error") return "Failed";
  return event || "Event";
}

function nodeEventStatus(event: string): WorkflowTimelineItem["status"] {
  if (event === "start") return "running";
  if (event === "done") return "done";
  if (event === "error") return "failed";
  return "pending";
}

function nodeSnapshotStatus(status: string): WorkflowTimelineItem["status"] {
  if (status === "RUNNING") return "running";
  if (status === "SUCCEEDED") return "done";
  if (status === "FAILED") return "failed";
  return "pending";
}

function llmEventStatus(event: string): WorkflowTimelineItem["status"] {
  if (event === "done") return "done";
  if (event === "error") return "failed";
  if (event === "start" || event === "fallback") return "running";
  return "pending";
}

function llmEventLabel(event: ReviewLLMCallEvent): string {
  if (event.event === "fallback") {
    return `Fallback ${event.from_model || "-"} -> ${event.to_model || "-"}`;
  }
  const prompt = event.prompt || "LLM";
  const model = event.model || event.provider_model || "-";
  return `${prompt} · ${event.event} · ${model}`;
}

function llmEventMeta(event: ReviewLLMCallEvent): string {
  const parts = [
    event.provider || "",
    event.provider_model || "",
    event.attempt ? `attempt ${event.attempt}` : "",
    event.error_type || "",
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "safe summary only";
}

function lastFailedNode(job: ReviewJobResponse): string {
  const failedEvent = [...job.node_events].reverse().find((event) => event.event === "error");
  if (failedEvent) return nodeDisplayName(failedEvent.node);
  const failedNode = Object.values(job.nodes).find((node) => node.status === "FAILED");
  return failedNode ? nodeDisplayName(failedNode.node) : "";
}

function textFromUnknown(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function numberFromUnknown(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
    return String(Number(value));
  }
  return "0";
}

function formatElapsedMs(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
  return `${Math.round(value)}ms`;
}

function formatRunTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function reportPreviewBlock(content: string): string {
  return content.length <= 6000 ? content : `${content.slice(0, 6000)}\n\n...`;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
