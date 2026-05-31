# Industrial Error Handling Design

本文件记录我们后续要逐步完善的“工业级 agent 异常处理”方案。它不是一次性实现清单，而是系统演进基线：先把错误分类、恢复策略、可观测性和最终产品输出约定下来，后续按阶段落地。

## 背景

当前系统已经能跑通真实 `QUICK_REVIEW`，但真实 LLM 调用暴露了几个典型问题：

- 长论文、多 reviewer、多 provider 时，单次调用耗时较长，需要更合理的 timeout。
- 不同 provider 的 JSON 输出稳定性不同，可能出现少逗号、截断、不符合字段约束等问题。
- 当前 graph 失败时基本是直接抛异常，缺少节点级错误收集、fallback、partial report 和可恢复执行。
- 最终报告已经产品化，但异常路径还没有形成正式的用户可读输出。

我们已经做了两个基础修正：

- `LLM_TIMEOUT_SEC=600`
- 本地 `json-repair` 修复 LLM JSON 小错误

下一步要从“能跑”升级为“可恢复、可观测、可诊断、可继续”的 agent 系统。

## 设计目标

1. **错误可分类**：不要只有原始 traceback；每类错误都能判断是否可重试、是否可 fallback、是否要终止。
2. **节点可恢复**：某个 reviewer 失败时，不应让已成功 reviewer 的结果白跑。
3. **输出可信**：不能伪造成功；失败、降级、partial 都必须明确标注。
4. **结果可追踪**：每个节点的 attempt、耗时、模型、provider、错误摘要都应落盘。
5. **产品可解释**：最终报告不仅有成功报告，也要有 parse failure、provider failure、partial review report 等用户可读输出。
6. **实现渐进**：先做 LLM/router 层和节点错误结构，再做 checkpoint 和复杂恢复。

## 外部实践参考

这些是本方案对齐的工业实践方向：

- LangGraph fault tolerance：节点级 `RetryPolicy`、`TimeoutPolicy`、error handler、可通过 `Command` 路由到恢复节点。
  - https://docs.langchain.com/oss/python/langgraph/fault-tolerance
- LangGraph persistence：使用 checkpointer 保存 graph state，失败后可从 checkpoint 恢复。
  - https://docs.langchain.com/oss/python/langgraph/persistence
- Temporal workflow：activity retry policy、start-to-close timeout、schedule-to-close timeout、heartbeat，用于长任务可恢复执行。
  - https://docs.temporal.io/encyclopedia/retry-policies
  - https://docs.temporal.io/encyclopedia/detecting-activity-failures
- Pydantic AI structured output：schema validation、output validator、失败后 `ModelRetry`。
  - https://pydantic.dev/docs/ai/core-concepts/output/
- OpenAI Agents SDK / LangSmith observability：trace 每一步模型调用、工具调用、错误和耗时。
  - https://openai.github.io/openai-agents-python/tracing/
  - https://docs.langchain.com/oss/python/langchain/observability

## 核心原则

### 1. JSON 是内部协议，不是可靠事实

LLM 返回 JSON 只是“模型尝试遵守协议”。工业级系统必须继续做：

```text
raw response
-> json_repair
-> schema validation
-> business validation
-> repair retry / fallback
-> node error
```

不能因为 JSON 能 parse 就认为节点成功。

### 2. 失败不能被伪装成成功

例如 reviewer2 失败时，不应该生成一个假的 reviewer2 report。合理结果是：

```text
COMPLETED
COMPLETED_WITH_WARNINGS
PARTIAL_FAILED
FAILED_RETRYABLE
FAILED_FATAL
```

最终报告需要明确显示哪些节点成功、哪些节点失败、失败是否影响最终结论。

### 3. 重试要分层

不要把所有重试都放在一个地方。建议分层：

```text
Provider HTTP retry
-> LLM structured-output repair retry
-> model fallback
-> LangGraph node retry
-> graph-level checkpoint resume
```

每层只处理自己能判断的错误。

### 4. 可恢复优先于重跑

多 reviewer 并行场景下，如果 reviewer1、reviewer3、devils_advocate 已经完成，reviewer2 失败后应该复用成功结果，而不是全部重跑。

## 错误分类

建议新增 `src/core/errors.py` 或 `src/infra/errors.py`，统一定义错误类型。

```text
ProviderTransientError
  临时供应商错误：timeout、连接失败、429、5xx。
  策略：可重试，可 fallback。

ProviderFatalError
  供应商配置错误：401、403、模型不存在、API key 错。
  策略：不重试，直接失败并提示配置问题。

ProviderCapabilityError
  供应商不支持某种能力：json_object、schema output、tool calling。
  策略：切换到兼容模型或降级调用方式。

ModelOutputParseError
  模型输出无法解析为 JSON。
  策略：json_repair，本地修复失败后模型修复重试。

ModelOutputValidationError
  JSON 合法，但字段缺失或违反业务规则。
  策略：把校验错误反馈给模型重试，仍失败则 fallback。

NodeRecoverableError
  节点失败但可恢复。
  策略：节点级 retry / fallback / partial。

NodeFatalError
  节点失败且继续无意义。
  策略：终止 graph，生成失败报告。
```

## LLMRouter 策略

后续 `configs/llm.yaml` 可以扩展成这样：

```yaml
models:
  deepseek/deepseek-v4-pro:
    provider: deepseek_official
    provider_model_id: deepseek-v4-pro
    timeout_sec: 600
    max_attempts: 2
    retry_backoff_sec: 2
    fallback_models:
      - sf/deepseek-v4-pro
      - openrouter/glm-4.6
    structured_output: json_object
```

调用流程：

```text
resolve model id
-> call provider
-> retry transient errors
-> parse/repair JSON
-> validate schema
-> fallback model if needed
-> raise typed error if exhausted
```

需要注意：

- retry 只处理 transient error，不重试 API key 错误。
- fallback 要记录原模型和 fallback 模型，方便后续分析质量。
- 每次调用都应记录 provider、model、prompt_name、attempt、elapsed_ms。

## Structured Output Validation

建议为主要 LLM 节点定义 Pydantic schema。

第一批最需要 schema 的节点：

```text
reviewer1
reviewer2
reviewer3
devils_advocate
ae_final
```

Reviewer schema 需要验证：

```text
major_comments >= 3
minor_comments >= 2
questions_for_authors >= 2
major_comments + minor_comments >= 5
scores.rating 存在
recommendation 存在
每条 comment 有 title/comment/evidence/severity/suggested_fix
```

AE final schema 需要验证：

```text
final_decision in ACCEPT/MINOR_REVISION/MAJOR_REVISION/REJECT
decision_letter 非空
revision_checklist 非空
rr_traceability_matrix 是 list
revision_roadmap 包含 must_fix / should_fix / nice_to_fix
```

失败时不要直接崩：

```text
validation error
-> 生成结构化错误说明
-> 反馈给模型重试一次
-> 仍失败则 fallback
-> 仍失败则 NodeRecoverableError
```

## LangGraph 节点策略

不同节点的异常策略不同。

| Node | 错误策略 | 说明 |
| --- | --- | --- |
| `doc_parse` | 可 fallback parser，不建议无限重试 | MinerU 失败后 PyMuPDF fallback，仍失败则 parse failure report |
| `content_check` | retry 1-2 次 | 失败时不能随便放行任意文件 |
| `journal_req_collector` | fatal | venue 文件是本地配置，失败说明项目配置有问题 |
| `field_analyst` | retry + fallback | 失败会影响 reviewer 分工，但可用默认 reviewer_config 降级 |
| `se_check` | retry + fallback | full review 关键节点，失败不能静默跳过 |
| `ae_check` | retry + fallback | full review 关键节点 |
| `reviewer1/2/3` | retry + fallback，失败则 failed retryable | 三个正式 reviewer 不建议静默缺失 |
| `devils_advocate` | retry + fallback，可降级 warning | DA 失败可以继续，但 final report 必须标注 DA unavailable |
| `ae_final` | retry + fallback，失败则 partial report | 没有 AE final 不应给正式 final decision |
| `final_artifact_render` | fatal | 本地 renderer 失败是代码问题，不能吞掉 |

## Graph State 扩展

建议在 `GlobalState` 里增加：

```python
run_status: str
node_errors: list[dict]
node_attempts: dict[str, int]
node_timings: dict[str, float]
fallback_events: list[dict]
warnings: list[str]
```

其中 `node_errors` 的结构：

```json
{
  "node": "reviewer2",
  "prompt_name": "reviewer2",
  "provider": "deepseek_official",
  "model": "deepseek-v4-pro",
  "error_type": "ModelOutputValidationError",
  "recoverable": true,
  "attempt": 2,
  "message": "major_comments has 1 item; expected at least 3",
  "elapsed_ms": 83421
}
```

## Artifact 设计

每次 run 应保留：

```text
data/runs/{run_id}/
  request.json
  parsed_paper.json
  stage_outputs.json
  reviewer_reports.json
  final_decision.json
  final_report.md
  node_errors.json
  node_timings.json
  fallback_events.json
  llm_calls.jsonl
```

`llm_calls.jsonl` 每行记录一次 LLM 调用摘要，不写 API key，不写完整敏感内容。

建议字段：

```json
{
  "timestamp": "2026-05-29T...",
  "node": "reviewer2",
  "prompt_name": "reviewer2",
  "provider": "deepseek_official",
  "model": "deepseek-v4-pro",
  "attempt": 1,
  "elapsed_ms": 53120,
  "status": "parse_error",
  "error_type": "ModelOutputParseError",
  "input_chars": 82431,
  "output_chars": 6120
}
```

## 最终报告异常输出

最终报告需要支持以下状态：

```text
COMPLETED
COMPLETED_WITH_WARNINGS
PARTIAL_FAILED
FAILED_RETRYABLE
FAILED_FATAL
```

报告中新增一个固定 section：

```text
## Run Diagnostics

| Node | Status | Attempts | Model | Error |
| --- | --- | --- | --- | --- |
| reviewer2 | recovered_by_fallback | 2 | deepseek -> sf/deepseek | JSON validation failed |
```

如果是 partial report：

```text
## Review Status

This report is partial. Reviewer 2 failed after retry and fallback.
No final editorial decision is issued.
```

中文正文模式下，正文可以中文，但 section 标题仍可保持英文术语。

## Checkpoint 与恢复

后续启用 LangGraph checkpointer：

```python
main_graph = builder.compile(checkpointer=checkpointer)
main_graph.invoke(
    initial_state,
    config={"configurable": {"thread_id": run_id}},
)
```

目标：

- 每个 super-step 后保存 state。
- 节点失败后可以从 checkpoint resume。
- 并行 reviewer 中已完成的结果可以复用。
- 用户可以在前端点击“retry failed node”。

## 可观测性

短期先做本地 artifact：

```text
node_errors.json
node_timings.json
fallback_events.json
llm_calls.jsonl
```

中期接 LangSmith：

```text
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=paper-review-agent
```

长期前端展示：

```text
doc_parse -> content_check -> field_analyst -> reviewer nodes -> ae_final -> render
每个节点显示 status / elapsed / model / retry count
```

## 分阶段实现计划

### Phase 1: 错误结构与 LLMRouter retry/fallback

目标：解决最常见的 provider timeout、JSON parse、provider 不稳定问题。

任务：

- 新增统一 error classes。
- 扩展 `configs/llm.yaml` 支持 `timeout_sec/max_attempts/fallback_models`。
- `LLMRouter` 捕获 HTTP/parse/validation 错误并分类。
- 记录 `fallback_events` 和基础 `llm_calls.jsonl`。

### Phase 2: Reviewer / AE schema validation

目标：模型输出“看起来 JSON 合法但内容不合格”时能自动修复。

任务：

- 定义 reviewer schema。
- 定义 ae_final schema。
- 校验失败时做 repair retry。
- reviewer 至少 3 major + 2 minor + 2 questions 变成正式 validator。

### Phase 3: LangGraph node-level retry/error state

目标：节点失败能进入可控状态，而不是直接 traceback。

任务：

- `GlobalState` 增加 `node_errors/run_status/node_timings`。
- 给关键节点加 `RetryPolicy` 和 `TimeoutPolicy`。
- 设计 `error_handler_node` 或节点 wrapper。
- final renderer 展示 `Run Diagnostics`。

### Phase 4: Checkpoint + resume

目标：失败后从上次成功状态继续，不全量重跑。

任务：

- 启用 LangGraph checkpointer。
- 使用 `run_id` 作为 `thread_id`。
- 保存 checkpoint metadata。
- CLI/API 支持 `resume run_id`。

### Phase 5: 前端与人工介入

目标：前端能看到每个节点状态，并手动 retry/fallback。

任务：

- API 暴露 run status。
- API 暴露 node diagnostics。
- 支持 retry failed node。
- 支持手动选择 fallback model 后继续。

## 当前优先级建议

我们下一步先做：

```text
Phase 1 + Phase 2 的最小版本
```

也就是：

1. 先把 LLM 错误分类、retry、fallback 做起来。
2. 再把 reviewer / ae_final 的 schema validation 做起来。

这样能直接解决目前真实测试中最常出现的错误：

- provider 超时
- malformed JSON
- JSON 合法但字段不够
- 某个 provider 输出不稳定

Checkpoint 和前端可视化可以后置，因为它们依赖前面的错误结构稳定。
