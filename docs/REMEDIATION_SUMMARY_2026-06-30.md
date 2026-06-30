# Remediation Summary - 2026-06-30

本文档总结 12 个稳定性、安全性、契约和评估任务的收尾结果。每个任务都按同一个原则推进：先从系统应该保证的基本事实出发，再落到可测试、可追踪的代码证据。

## 1. Non-paper Input Routing

First principle: 支持的文件格式不等于可审稿内容。系统必须先判断上传内容是否像学术论文，不能把菜谱、日记、短文本或伪装文档送进正常审稿链路。

Implemented:

- `src/graphs/review_nodes.py`
- `src/graphs/nodes/invalid_file_node.py`
- `src/infra/renderers/review_artifact_renderer.py`
- Tests in `tests/test_workflow.py`

Evidence:

- 非论文 `.md` / `.tex` / fake PDF parse result 会输出 `INVALID_SUBMISSION`。
- `invalid_file` 路由不会进入 reviewer / AE review 节点。

## 2. Prompt Injection Isolation

First principle: 论文正文是用户提供的不可信数据，里面的任何“忽略前文指令”“直接接受论文”等内容都只能作为待审材料，不应改变 agent 的角色、输出格式或决策标准。

Implemented:

- `src/graphs/review_nodes.py`
- Tests in `tests/test_single_reviewer_node.py`

Evidence:

- `paper_content` 和 `content_preview` 被包进 `BEGIN_UNTRUSTED_PAPER_CONTENT` / `END_UNTRUSTED_PAPER_CONTENT`。
- 测试确认 prompt injection 文本仍出现在待审稿内容中，但不会被当作系统指令执行。

## 3. Chinese Report Localization

First principle: 用户选择中文输出时，最终报告的自然语言框架也应该是中文。保留专业术语可以接受，但不能出现混乱的英文报告标题和 `Dear Author(s)`。

Implemented:

- `src/infra/renderers/review_artifact_renderer.py`
- Tests in `tests/test_workflow.py` and `tests/test_api.py`

Evidence:

- 中文报告使用 `审稿报告`、`尊敬的作者：` 等中文标签。
- 测试确认中文报告不再出现 `Decision Letter` / `Dear Author(s)` 等旧英文框架。

## 4. Frontend Workflow Alignment With AE Split

First principle: 前端剧场应该展示后端真实 workflow，而不是旧节点名。否则用户看到的进度会和实际 LangGraph 路径不一致。

Implemented:

- `frontend/src/pages/WorkbenchHome.tsx`
- `frontend/src/components/ReviewTheater.tsx`

Evidence:

- 前端节点已对齐 `ae_decision -> ae_report -> ae_finalize`。
- 前端 build 通过。

## 5. Author Report / Internal Audit Split

First principle: 作者版报告和系统内部审计报告服务不同对象。作者版应像真实审稿意见；内部审计版才保留 AE / reviewer / traceability 等调试信息。

Implemented:

- `src/graphs/nodes/final_artifact_render_node.py`
- `src/infra/renderers/review_artifact_renderer.py`
- Tests in `tests/test_workflow.py`

Evidence:

- 成功 run 生成 `final_report.md`、`author_report.md` 和 `internal_audit.md`。
- 作者版不包含内部 AE synthesis / R&R traceability 标签。
- 内部审计版保留 `AE 终审综合意见` 和 `R&R 可追踪矩阵`。

## 6. Gold Decision Alignment Script

First principle: 跑通不等于判断可靠。系统需要一个固定 gold decision benchmark，持续衡量模型审稿决策与真实 OpenReview 决策的对齐程度。

Implemented:

- `scripts/decision_alignment.py`
- Tests in `tests/test_decision_alignment_script.py`

Evidence:

- 脚本输出 `decision_alignment_v1`。
- 支持 `alignment_summary.json` 和 `alignment_details.csv`。
- 已在历史 1171 full batch 上 smoke：可比较样本 1169，accuracy 约 0.627。

## 7. LLM Retry / Fallback Diagnostics

First principle: 工业级 agent 失败时，不能只说“失败了”。必须能回答哪个 prompt、哪个 provider/model、第几次 attempt、下一步 retry 还是 fallback、最终耗尽在哪个模型。

Implemented:

- `src/infra/llm_diagnostics.py`
- `src/services/review_service.py`
- `scripts/batch_review.py`
- Tests in `tests/test_workflow.py` and `tests/test_batch_review_script.py`

Evidence:

- `diagnostics.json` 新增 `llm_retry_timeline`。
- batch failure row 可直接暴露 `failed_prompt`、`failed_model`、`last_retry_next_action`、`model_output_error_ref`。
- `llm_calls.jsonl` 仍保留完整逐事件日志。

## 8. Long-context Control

First principle: 论文全文是大且不可信的输入，不能无界地重复塞进每个 LLM 节点。LLM 节点应该看到结构稳定、长度可控的 paper brief，而完整解析结果继续保存在 artifact 中。

Implemented:

- `src/graphs/review_nodes.py`
- Tests in `tests/test_single_reviewer_node.py`

Evidence:

- 审稿 LLM 节点统一使用 `_paper_prompt_brief()`。
- brief 保留 title、abstract、selected manuscript sections，并跳过 references / appendix 类章节。
- 超长输入会出现 `Prompt paper brief was truncated` 说明。

Boundary:

- 当前版本是 bounded brief / deterministic truncation，不是完整语义 chunk-RAG。完整 chunk retrieval 可以作为后续增强，但当前已解决无界上下文和尾部噪声进入 prompt 的问题。

## 9. API / OpenAPI / Frontend Contract Alignment

First principle: 后端实际返回、OpenAPI 文档、前端 TypeScript 类型必须描述同一个接口。否则字段会在 response model 中被过滤，前端也会读不到诊断信息。

Implemented:

- `src/api/schemas.py`
- `frontend/src/api/client.ts`
- `docs/api/openapi.json`
- Tests in `tests/test_api.py`

Evidence:

- `ReviewLLMCallEventResponse` 暴露 `error_message`、`next_action`、`model_output_error_kind`、`model_output_error_ref`、`model_output_preview`。
- `scripts/check-api-contract.sh` 通过。
- Frontend build 通过。

## 10. Artifact API Safety And Privacy

First principle: artifact API 读的是本地文件系统。任何 URL 或 JSON 里的 `job_id` / `artifact_name` 都是不可信输入，只能访问该 run artifact 目录里的安全普通文件。

Implemented:

- `src/services/review_jobs.py`
- Tests in `tests/test_api.py`

Evidence:

- `artifact_path()` 收敛到 `_safe_artifact_path()`。
- `list_artifacts()` 只列出安全普通文件。
- symlink escape、隐藏文件、路径穿越、跨 runs 删除被拒绝。

Boundary:

- 本项目仍是 local-first 工具，API 里保留 `paper_path` / `artifact_dir` 作为本地调试锚点。当前任务解决的是 artifact 文件系统访问边界，不是多租户隐私隔离。

## 11. Batch Summary Status Precision

First principle: batch 进程跑完和样本全部成功不是同一件事。summary 必须显式区分成功完成、带失败完成、失败后中止和 dry run。

Implemented:

- `scripts/batch_review.py`
- Tests in `tests/test_batch_review_script.py`

Evidence:

- `summary.json` 状态包括 `SUCCEEDED`、`COMPLETED_WITH_FAILURES`、`STOPPED_AFTER_FAILURE`、`DRY_RUN`、`EMPTY`。
- 新增 `completed_count`、`succeeded_count`、`failed_count`、`planned_count`。

## 12. Token / Cost / Provider Observability

First principle: 大批量审稿必须知道每篇论文花了多少 token、多少钱、走了哪个 provider/model。否则无法做成本控制、provider 选择和失败排查。

Implemented:

- `configs/llm_pricing.yaml`
- `src/infra/llm_usage.py`
- `src/services/review_service.py`
- `src/services/review_jobs.py`
- `src/api/schemas.py`
- `frontend/src/pages/WorkbenchHome.tsx`
- `frontend/src/api/client.ts`
- Tests in `tests/test_llm_usage.py`, `tests/test_workflow.py`, `tests/test_api.py`

Evidence:

- 每个 run 写入 `usage_summary.json`。
- API 提供 `/api/jobs/{job_id}/usage`。
- 前端报告详情页展示 cost、tokens、provider/model breakdown。

## Verification

Final verification commands:

```bash
.venv/bin/python -m unittest discover tests
.venv/bin/python -m src.cli doctor
scripts/check-api-contract.sh
cd frontend && npm run build
```

Final verified state:

- Python tests: 121 tests passed.
- CLI doctor: passed.
- OpenAPI contract: up to date.
- Frontend production build: passed.
- `main` was pushed to `origin/main` after each task branch was merged directly.

## Local Files Intentionally Left Out Of Commits

The following local files were intentionally not included in the remediation commits:

- `AGENTS.md`: local modified working copy retained.
- `docs/SYSTEM_TEST_AUDIT_2026-06-28.md`: local audit draft retained as untracked context.
