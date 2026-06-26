import type { ReviewJobResponse, ReviewNodeEvent } from "../api/client";

type PixelAgentId = "parser" | "checker" | "collector" | "analyst" | "se" | "ae" | "r1" | "r2" | "r3" | "da" | "solo" | "final";
type AgentId = PixelAgentId | "parse_fail" | "invalid" | "dispatch" | "desk_reject" | "renderer";
type TheaterStatus = "pending" | "running" | "done" | "failed" | "skipped";
type VerdictKind = "ok" | "warn" | "err" | "info";

type TheaterAgent = {
  id: AgentId;
  pixelId: PixelAgentId;
  node: string;
  name: string;
  zh: string;
  role: string;
  read: string;
  ponder: string[];
  mark: string;
  verdict: string;
  verdictSub: string;
  kind: VerdictKind;
  onlyWhenReached?: boolean;
};

const agents: TheaterAgent[] = [
  { id: "parser", pixelId: "parser", node: "doc_parse", name: "Parser", zh: "文档解析员", role: "Structure · refs", read: "解析结构 · 抽取标题 / 章节 / 引用", ponder: ["title?", "sections?", "refs?"], mark: "✓", verdict: "结构完成", verdictSub: "title · sections · refs", kind: "ok" },
  { id: "parse_fail", pixelId: "parser", node: "parse_fail_output", name: "Parse Failure Output", zh: "解析失败说明", role: "Fallback report", read: "整理解析失败原因与下一步建议", ponder: ["parse failed", "fallback?", "report"], mark: "!", verdict: "失败说明", verdictSub: "parse failure", kind: "err", onlyWhenReached: true },
  { id: "checker", pixelId: "checker", node: "content_check", name: "Content Checker", zh: "内容检查员", role: "Integrity · figures", read: "核对稿件是否为学术论文", ponder: ["paper?", "complete?", "valid?"], mark: "✓", verdict: "内容通过", verdictSub: "paper intent", kind: "ok" },
  { id: "invalid", pixelId: "checker", node: "invalid_file", name: "Invalid File Output", zh: "无效稿件说明", role: "Fallback report", read: "生成无效输入说明，提示重新上传论文", ponder: ["invalid?", "explain", "retry"], mark: "!", verdict: "无效输入", verdictSub: "invalid manuscript", kind: "err", onlyWhenReached: true },
  { id: "collector", pixelId: "collector", node: "journal_req_collector", name: "Journal Collector", zh: "期刊收集员", role: "Scope · venue", read: "拉取 venue 要求与画像", ponder: ["scope?", "fit?", "rules?"], mark: "≈", verdict: "范围匹配", verdictSub: "venue profile", kind: "info" },
  { id: "analyst", pixelId: "analyst", node: "field_analyst", name: "Field Analyst", zh: "领域分析员", role: "Literature pos.", read: "在当前文献中定位本文", ponder: ["novel?", "incremental?", "gap?"], mark: "~", verdict: "定位完成", verdictSub: "field context", kind: "info" },
  { id: "se", pixelId: "se", node: "se_check", name: "Senior Editor", zh: "主编", role: "Desk-reject gate", read: "初筛 · 范围 / 新颖性 / 门槛", ponder: ["DESK REJ?", "送审?", "DESK REJ?", "送审?"], mark: "→", verdict: "送审判断", verdictSub: "desk decision", kind: "ok" },
  { id: "ae", pixelId: "ae", node: "ae_check", name: "Associate Editor", zh: "责编", role: "Assignment", read: "组建审稿小组 · 分配方向", ponder: ["R1?", "R2?", "R3?", "DA?"], mark: "‖", verdict: "分派外审", verdictSub: "panel assigned", kind: "info" },
  { id: "desk_reject", pixelId: "se", node: "desk_reject_output", name: "Desk Reject Output", zh: "桌拒意见生成", role: "Desk decision", read: "生成正式桌拒说明与改进建议", ponder: ["desk reject", "reasons", "advice"], mark: "!", verdict: "桌拒说明", verdictSub: "desk reject", kind: "err", onlyWhenReached: true },
  { id: "dispatch", pixelId: "ae", node: "review_dispatch", name: "Review Dispatch", zh: "外审分发员", role: "Parallel start", read: "把同一份稿件分发给外审小组", ponder: ["R1 · R2", "R3 · DA", "parallel"], mark: "‖", verdict: "并行启动", verdictSub: "reviewers queued", kind: "info" },
  { id: "r1", pixelId: "r1", node: "reviewer1", name: "Reviewer · R1", zh: "方法论审稿人", role: "Methodology", read: "方法论与实验设计", ponder: ["method?", "baseline?", "ablation?"], mark: "!", verdict: "方法评审", verdictSub: "methods", kind: "warn" },
  { id: "r2", pixelId: "r2", node: "reviewer2", name: "Reviewer · R2", zh: "领域审稿人", role: "Domain", read: "领域贡献与定位", ponder: ["contribution?", "fit?", "related?"], mark: "✓", verdict: "贡献评审", verdictSub: "positioning", kind: "ok" },
  { id: "r3", pixelId: "r3", node: "reviewer3", name: "Reviewer · R3", zh: "跨学科审稿人", role: "Cross-disc", read: "清晰度与可迁移性", ponder: ["clear?", "assumption?", "transfer?"], mark: "✓", verdict: "表达评审", verdictSub: "clarity", kind: "ok" },
  { id: "da", pixelId: "da", node: "devils_advocate", name: "Devil's Advocate", zh: "反方辩护人", role: "Adversarial", read: "寻找最强反对意见", ponder: ["weakness?", "counter?", "failure?"], mark: "✕", verdict: "反例检查", verdictSub: "edge cases", kind: "err" },
  { id: "solo", pixelId: "solo", node: "single_reviewer", name: "Solo Reviewer", zh: "综合审稿人", role: "Contribution · method · venue fit", read: "综合评估贡献、方法、实验与 venue fit", ponder: ["contribution?", "method?", "experiment?", "venue fit?", "revision risk?", "decision?"], mark: "★", verdict: "综合评审", verdictSub: "single reviewer", kind: "warn" },
  { id: "final", pixelId: "final", node: "ae_final", name: "AE · Final", zh: "终审编辑", role: "Decision letter", read: "汇总 4 份报告 · 权衡分歧", ponder: ["MAJOR?", "MINOR?", "ACCEPT?", "REJECT?"], mark: "±", verdict: "终审决定", verdictSub: "decision letter", kind: "warn" },
  { id: "renderer", pixelId: "final", node: "final_artifact_render", name: "Report Renderer", zh: "报告生成器", role: "Artifacts", read: "渲染 Markdown 报告、诊断信息与下载产物", ponder: ["markdown", "artifacts", "ready?"], mark: "◆", verdict: "产物完成", verdictSub: "artifacts ready", kind: "ok" },
];

const reviewerIds: AgentId[] = ["r1", "r2", "r3", "da"];
const nodeToAgent = new Map(agents.map((agent) => [agent.node, agent]));

export function ReviewTheater({ job }: { job: ReviewJobResponse }) {
  // 这里把后端 job 快照翻译成舞台状态，避免动画组件直接理解 LangGraph 细节。
  const visibleAgents = visibleTheaterAgents(job);
  const statuses = agentStatuses(job);
  const activeAgents = activeTheaterAgents(visibleAgents, statuses);
  const doneAgents = visibleAgents.filter((agent) => statuses[agent.id] === "done");
  const queueAgents = visibleAgents.filter((agent) => statuses[agent.id] === "pending" && !activeAgents.some((active) => active.id === agent.id));
  const isFinished = job.status === "SUCCEEDED" || job.status === "FAILED" || job.status === "CANCELED";
  const hasVisibleNode = visibleAgents.length > 0;
  const stagePercent = Math.round((doneAgents.length / Math.max(1, visibleAgents.length)) * 100);
  const percent = job.progress.total_nodes > 0 ? job.progress.percent : stagePercent;
  const nowText = theaterNowText(job, activeAgents);
  const logEvents = job.node_events.slice(-12);
  const nextNodeLabel = progressNextLabel(job);

  return (
    <section className={`review-theater-card ${job.status.toLowerCase()}`} aria-label="Review theater">
      <div className="review-theater-head">
        <div className="review-theater-title">
          <span className="eyebrow">REVIEW THEATER · 审稿剧场</span>
          <h2>{paperTitle(job.request.paper_path)}</h2>
          <p>{job.request.venue_code} · {humanReviewMode(job.request.review_mode)} · {job.status}</p>
        </div>
        <div className="review-theater-run">
          <b>{job.job_id.slice(0, 8)}</b>
          <span>{formatRunTime(job.updated_at)}</span>
        </div>
      </div>

      <div className="review-theater-meter">
        <span className="review-theater-now"><i />{nowText}</span>
        <div className="review-theater-bar"><span style={{ width: `${percent}%` }} /></div>
        <b>{percent}%</b>
      </div>

      <div className="review-theater-stats" aria-label="Review progress summary">
        <span><small>Elapsed</small><b>{formatDurationMs(job.progress.elapsed_ms)}</b></span>
        <span><small>Done</small><b>{job.progress.completed_nodes}/{job.progress.total_nodes || visibleAgents.length}</b></span>
        <span><small>Next</small><b>{nextNodeLabel}</b></span>
      </div>

      <div className="review-theater-body">
        <div className="review-stage">
          <div className="review-stage-zone done" aria-label="Completed agents">
            {doneAgents.map((agent) => <MiniAgent agent={agent} key={agent.id} status="done" />)}
          </div>
          <div className="review-podium">
            <div className="review-stage-pool" />
            {isFinished && activeAgents.length === 0 && !hasVisibleNode ? (
              <TerminalNotice job={job} />
            ) : isFinished && activeAgents.length === 0 ? (
              <CurtainCall agents={visibleAgents} statuses={statuses} />
            ) : activeAgents.length > 1 ? (
              <ParallelActors agents={activeAgents} statuses={statuses} />
            ) : activeAgents.length === 1 ? (
              <SingleActor agent={activeAgents[0]} status={statuses[activeAgents[0].id]} />
            ) : (
              <div className="review-stage-idle">Waiting for next node… · 等待下一个节点</div>
            )}
          </div>
          <div className="review-stage-zone queue" aria-label="Queued agents">
            {queueAgents.slice(0, 7).map((agent, index) => <MiniAgent agent={agent} key={agent.id} status={index === 0 ? "running" : "pending"} />)}
          </div>
        </div>

        <aside className="review-theater-log" aria-label="Review activity log">
          <div className="review-theater-log-head">
            <span>LIVE</span>
            <b>Activity log</b>
          </div>
          <div className="review-theater-log-body">
            {logEvents.length === 0 ? (
              <p>{emptyLogText(job)}</p>
            ) : logEvents.map((event, index) => <LogEntry event={event} key={`${event.timestamp}-${event.node}-${index}`} />)}
          </div>
        </aside>
      </div>
    </section>
  );
}

function TerminalNotice({ job }: { job: ReviewJobResponse }) {
  const isCanceled = job.status === "CANCELED";
  const isFailed = job.status === "FAILED";
  return (
    <div className={`review-terminal ${isCanceled ? "canceled" : isFailed ? "failed" : "done"}`}>
      <div className="review-terminal-card">
        <span>{isCanceled ? "⊘" : isFailed ? "!" : "✓"}</span>
        <b>{isCanceled ? "Run canceled" : isFailed ? "Run failed" : "Run finished"}</b>
        <small>{isCanceled ? "审稿在 LangGraph 节点启动前已取消" : isFailed ? "没有可展示的节点事件" : "没有记录到节点事件"}</small>
      </div>
    </div>
  );
}

function SingleActor({ agent, status }: { agent: TheaterAgent; status: TheaterStatus }) {
  const failed = status === "failed";
  return (
    <div className={`review-cast single k-${failed ? "err" : agent.kind}`}>
      <div className={`review-actor ${status}`}>
        <ThoughtBubble agent={agent} status={status} />
        <div className="review-actor-fig"><agent-px id={agent.pixelId} size="96" /></div>
        <ManuscriptPaper active={status === "running"} />
        <div className="review-actor-plate">
          <span>{agent.name}</span>
          <small>{agent.zh} · {agent.role}</small>
        </div>
      </div>
    </div>
  );
}

function ParallelActors({ agents, statuses }: { agents: TheaterAgent[]; statuses: Record<AgentId, TheaterStatus> }) {
  return (
    <div className="review-cast parallel">
      <div className="parallel-tag">‖ 并行外审 · reviewers reading at once</div>
      {agents.map((agent) => (
        <div className={`review-actor compact ${statuses[agent.id]} k-${statuses[agent.id] === "failed" ? "err" : agent.kind}`} key={agent.id}>
          <ThoughtBubble agent={agent} status={statuses[agent.id]} compact />
          <div className="review-actor-fig"><agent-px id={agent.pixelId} size="64" /></div>
          <ManuscriptPaper active={statuses[agent.id] === "running"} compact />
          <div className="review-actor-plate">
            <span>{agent.name.replace("Reviewer · ", "")}</span>
            <small>{agent.zh}</small>
          </div>
        </div>
      ))}
    </div>
  );
}

function CurtainCall({ agents, statuses }: { agents: TheaterAgent[]; statuses: Record<AgentId, TheaterStatus> }) {
  return (
    <div className="review-curtain">
      <div className="review-curtain-row">
        {agents.map((agent) => (
          <div className={`review-curtain-agent k-${statuses[agent.id] === "failed" ? "err" : agent.kind}`} key={agent.id}>
            <agent-px id={agent.pixelId} size="44" />
            <span>{statuses[agent.id] === "failed" ? "!" : agent.mark}</span>
          </div>
        ))}
      </div>
      <p>Review finished · 审稿流程已生成结果</p>
    </div>
  );
}

function MiniAgent({ agent, status }: { agent: TheaterAgent; status: TheaterStatus }) {
  return (
    <div className={`review-mini ${status} k-${agent.kind}`}>
      <agent-px id={agent.pixelId} size="28" />
      {status === "done" ? <span>{agent.mark}</span> : <small>{status === "running" ? "up next" : "waiting"}</small>}
    </div>
  );
}

function ThoughtBubble({ agent, status, compact = false }: { agent: TheaterAgent; status: TheaterStatus; compact?: boolean }) {
  const failed = status === "failed";
  const done = status === "done";
  return (
    <div className={`review-bubble ${compact ? "compact" : ""} ${status} k-${failed ? "err" : agent.kind}`}>
      {status === "running" ? (
        <span className="thinking-script">
          {agent.ponder.map((item, index) => (
            <i key={`${agent.id}-${item}-${index}`} style={{ animationDelay: `${index * 1.05}s` }}>{item}</i>
          ))}
        </span>
      ) : done || failed ? (
        <>
          <b>{failed ? "!" : agent.mark}</b>
          <span>{failed ? "失败" : agent.verdict}</span>
          {!compact ? <small>{failed ? "node error" : agent.verdictSub}</small> : null}
        </>
      ) : (
        <span>{agent.read}</span>
      )}
    </div>
  );
}

function ManuscriptPaper({ active, compact = false }: { active: boolean; compact?: boolean }) {
  return (
    <div className={`review-paper ${compact ? "compact" : ""} ${active ? "reading" : ""}`}>
      <span className="corner" />
      <i className="t" /><i /><i className="s" /><i /><i className="s" /><i />
      <span className="scan" />
    </div>
  );
}

function LogEntry({ event }: { event: ReviewNodeEvent }) {
  const agent = nodeToAgent.get(event.node);
  return (
    <div className={`review-log-entry ${event.event}`}>
      <span>{formatRunTime(event.timestamp)}</span>
      <i>{event.event === "done" ? "✓" : event.event === "error" ? "✕" : "▶"}</i>
      <p>
        <b>{agent?.name || event.node}</b> {nodeEventText(event)}
        {event.elapsed_ms !== undefined ? <em>{formatElapsedMs(event.elapsed_ms)}</em> : null}
        {event.error_type ? <em>{event.error_type}</em> : null}
      </p>
    </div>
  );
}

function agentStatuses(job: ReviewJobResponse): Record<AgentId, TheaterStatus> {
  // 不同审稿模式只改变可见角色；节点状态仍以服务端 LangGraph 事件为准。
  const statuses = Object.fromEntries(agents.map((agent) => [agent.id, isSkipped(agent, job) ? "skipped" : "pending"])) as Record<AgentId, TheaterStatus>;
  for (const agent of agents) {
    if (isSkipped(agent, job)) continue;
    const node = job.nodes[agent.node];
    if (!node) continue;
    if (node.status === "RUNNING") statuses[agent.id] = "running";
    if (node.status === "SUCCEEDED") statuses[agent.id] = "done";
    if (node.status === "FAILED") statuses[agent.id] = "failed";
  }
  if (job.status === "SUCCEEDED") {
    for (const agent of agents) {
      if (statuses[agent.id] !== "skipped") statuses[agent.id] = "done";
    }
  }
  return statuses;
}

function visibleTheaterAgents(job: ReviewJobResponse): TheaterAgent[] {
  const terminal = job.status === "SUCCEEDED" || job.status === "FAILED" || job.status === "CANCELED";
  const hasFallbackPath = agents.some((agent) => agent.onlyWhenReached && hasNodeActivity(agent, job));
  return agents.filter((agent) => {
    if (isSkipped(agent, job)) return false;
    if (terminal && (job.status !== "SUCCEEDED" || hasFallbackPath)) {
      return hasNodeActivity(agent, job);
    }
    return !agent.onlyWhenReached || hasNodeActivity(agent, job);
  });
}

function hasNodeActivity(agent: TheaterAgent, job: ReviewJobResponse): boolean {
  return Boolean(job.nodes[agent.node] || job.node_events.some((event) => event.node === agent.node));
}

function activeTheaterAgents(visibleAgents: TheaterAgent[], statuses: Record<AgentId, TheaterStatus>): TheaterAgent[] {
  const running = visibleAgents.filter((agent) => statuses[agent.id] === "running" || statuses[agent.id] === "failed");
  const runningReviewers = running.filter((agent) => reviewerIds.includes(agent.id));
  if (runningReviewers.length > 0) {
    return visibleAgents.filter((agent) => reviewerIds.includes(agent.id) && statuses[agent.id] !== "done" && statuses[agent.id] !== "skipped");
  }
  if (running.length > 0) return running;
  const next = visibleAgents.find((agent) => statuses[agent.id] === "pending");
  return next ? [next] : [];
}

function theaterNowText(job: ReviewJobResponse, activeAgents: TheaterAgent[]): string {
  if (job.status === "SUCCEEDED") return "审稿完成 · Decision ready";
  if (job.status === "FAILED") return "审稿失败 · Diagnostics ready";
  if (job.status === "CANCELED") return "审稿已取消 · Run canceled";
  if (activeAgents.length === 1 && activeAgents[0].id === "solo") return "综合审稿人正在快速审阅… · Solo review in progress";
  if (activeAgents.length > 1 && activeAgents.every((agent) => reviewerIds.includes(agent.id))) return "4 位审稿人并行评审中… · Reviewers ‖ + Devil's Advocate";
  if (activeAgents.length > 1) return `${activeAgents.length} 个节点并行运行中…`;
  if (activeAgents.length === 1) return `${activeAgents[0].name} 正在审阅… · ${activeAgents[0].role}`;
  return "Initialising run… · 准备开庭";
}

function emptyLogText(job: ReviewJobResponse): string {
  if (job.status === "CANCELED") return "Run canceled before graph node events.";
  if (job.status === "FAILED") return "Run failed before graph node events.";
  if (job.status === "SUCCEEDED") return "Run completed without recorded node events.";
  return "Run queued. Waiting for graph node events.";
}

function progressNextLabel(job: ReviewJobResponse): string {
  if (job.status === "SUCCEEDED") return "Done";
  if (job.status === "FAILED") return "Diagnostics";
  if (job.status === "CANCELED") return "Canceled";
  if (job.progress.active_nodes.length > 0) return job.progress.active_nodes.map(nodeLabel).join(" · ");
  if (job.progress.next_node) return nodeLabel(job.progress.next_node);
  return "Waiting";
}

function nodeLabel(node: string): string {
  return nodeToAgent.get(node)?.name || node.replace(/_/g, " ");
}

function isSkipped(agent: TheaterAgent, job: ReviewJobResponse): boolean {
  if (job.request.review_mode === "SINGLE_AGENT_REVIEW") {
    return ["se", "ae", "dispatch", "r1", "r2", "r3", "da", "final", "desk_reject"].includes(agent.id);
  }
  if (job.request.review_mode === "QUICK_REVIEW") {
    return agent.id === "se" || agent.id === "ae" || agent.id === "solo";
  }
  return agent.id === "solo";
}

function nodeEventText(event: ReviewNodeEvent): string {
  if (event.event === "start") return "started.";
  if (event.event === "done") return "completed.";
  if (event.event === "error") return "failed.";
  return event.event;
}

function humanReviewMode(value: string): string {
  if (value === "SINGLE_AGENT_REVIEW") return "Single Agent";
  return value === "QUICK_REVIEW" ? "Quick Review" : "Full Review";
}

function paperTitle(path: string): string {
  const name = path.split(/[\\/]/).pop() || "Manuscript";
  return name.replace(/\.[^.]+$/, "") || name;
}

function formatRunTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "-";
  return date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatElapsedMs(value: number): string {
  if (value < 1000) return `${Math.round(value)}ms`;
  return `${(value / 1000).toFixed(1)}s`;
}

function formatDurationMs(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "-";
  const totalSeconds = Math.max(0, Math.round(value / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}
