# Run Results Snapshot Before Rerun

记录时间：2026-06-27

这份文档记录删除旧运行结果前的本地结果文件状态。后续重新跑 1171 篇论文时，以本文作为旧结果快照，不再依赖旧 `data/runs/` 和 `data/batch_runs/`。

## 删除前规模

运行产物：

- `data/runs/`
  - run 目录：3147 个
  - 文件：52024 个
  - 大小：约 1.3G
- `data/batch_runs/`
  - batch 目录：15 个
  - 文件：67 个
  - 大小：约 3.2M
- `data/jobs/`
  - job 目录：0 个
  - 大小：约 24K

输入数据：

- `data/corpora/openreview_mineru_iclr2025/`
  - MinerU 解析后的 Markdown 论文：1171 篇
  - `manifest.jsonl`：1171 行
  - 大小：约 628M
- `data/eval_sets/`
  - `openreview_iclr2025_random100_seed42`
  - `openreview_iclr2025_random1000_seed42`
  - `openreview_iclr2025_remaining171_after_random1000_seed42`
  - 大小：约 2.1M

## 单次审稿结果文件

旧 `data/runs/<run_id>/` 中常见文件：

- `request.json`：本次审稿输入参数。
- `parsed_paper.json`：论文解析结果。
- `venue_profile.json`：venue 信息。
- `diagnostics.json`：诊断信息。
- `llm_calls.jsonl`：LLM 调用、retry、fallback 记录。
- `final_report.md`：最终审稿报告。
- `final_decision.json`：最终决定。
- `reviewer_reports.json`：审稿人意见汇总。
- `stage_outputs.json`：所有节点输出汇总。
- `partial_report.md`：失败时的 partial report。

旧节点中间产物：

- `doc_parse.json`
- `content_check.json`
- `field_analysis.json`
- `journal_requirements.json`
- `se_check.json`
- `ae_check.json`
- `review_dispatch.json`
- `reviewer1.json`
- `reviewer2.json`
- `reviewer3.json`
- `devils_advocate.json`
- `single_reviewer.json`
- `ae_final.json`
- `desk_reject_output.json`
- `final_artifact_render.json`

## 批量审稿结果文件

旧 `data/batch_runs/<batch_id>/` 中常见文件：

- `batch_request.json`：批跑参数。
- `manifest.jsonl`：每篇论文一行，记录成功/失败、run_id、错误类型。
- `summary.json`：总体统计。
- `final_decisions.csv`：最终 decision 汇总表。
- `failures.jsonl`：失败样本汇总。

重要旧 batch：

- `random1000_seed42_single_c20_20260626`
- `random1000_seed42_full_c5_20260626`
- `remaining171_after_random1000_seed42_single_c20_fixed_20260626`
- `remaining171_after_random1000_seed42_full_c5_fixed_20260626`

## 新诊断产物说明

最新代码已经统一了模型输出错误的 artifact 目录：

```text
data/runs/<run_id>/model_output_errors/
  parse_error_001.json
  validation_error_001.json
```

删除前的正式 `data/runs/` 中暂时没有实际生成该目录，因为该功能刚实现，之前正式批跑还没有用新代码重新触发 parse/validation 错误。

## 保留与删除

本次清理只删除旧运行结果：

- 删除：`data/runs/*`
- 删除：`data/batch_runs/*`
- 清空：`data/jobs/*`

保留输入数据：

- 保留：`data/corpora/openreview_mineru_iclr2025/`
- 保留：`data/eval_sets/`

## 重新跑批计划

使用完整 1171 篇 manifest：

```text
data/corpora/openreview_mineru_iclr2025/manifest.jsonl
```

新 batch 命名：

- `all1171_single_c20_20260627`
- `all1171_full_c5_20260627`

计划参数：

- SINGLE_AGENT_REVIEW：并发 20
- FULL_REVIEW：并发 5
- Venue：`CS / CCFA / AAAI`
- Output language：`zh`

