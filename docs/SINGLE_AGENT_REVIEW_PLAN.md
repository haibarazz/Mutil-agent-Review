# Single Agent Review 模式改造计划

本文档记录 `SINGLE_AGENT_REVIEW` 的产品语义、后端流程、前端剧场和逐步实现顺序。目标是让后续改造可以一小步一小步完成，每一步都能单独理解和验证。

## 1. 模式定位

`SINGLE_AGENT_REVIEW` 是一个单 Agent 快速审稿模式。

它不是删除前处理流程，而是把真正的审稿判断集中到一个综合审稿人身上：

- 保留文档解析、内容检查、venue context 和领域分析。
- 跳过 SE / AE 初筛。
- 跳过 3 位 reviewer + Devil's Advocate 的并行外审。
- 跳过 AE Final 汇总节点。
- 由一个 `single_reviewer` 节点直接生成综合审稿意见。
- 最后仍然进入统一的 `final_artifact_render`，输出正式报告。

## 2. 三种审稿模式对比

### Full Review

完整审稿，最接近真实编辑流程。

```text
doc_parse
-> content_check
-> journal_req_collector
-> field_analyst
-> se_check
-> ae_check
-> review_dispatch
-> reviewer1 / reviewer2 / reviewer3 / devils_advocate
-> ae_final
-> final_artifact_render
```

### Quick Review

快速多审稿人模式，跳过 SE / AE 初筛，但保留多 reviewer 和 AE Final。

```text
doc_parse
-> content_check
-> journal_req_collector
-> field_analyst
-> review_dispatch
-> reviewer1 / reviewer2 / reviewer3 / devils_advocate
-> ae_final
-> final_artifact_render
```

### Single Agent Review

单 Agent 综合审稿模式，用最低成本产出一份完整审稿意见。

```text
doc_parse
-> content_check
-> journal_req_collector
-> field_analyst
-> single_reviewer
-> final_artifact_render
```

## 3. 后端设计

### 3.1 ReviewMode

在核心模型中新增第三种审稿模式：

```text
SINGLE_AGENT_REVIEW
```

它和现有模式并列：

```text
FULL_REVIEW
QUICK_REVIEW
SINGLE_AGENT_REVIEW
```

### 3.2 Prompt

新增：

```text
prompts/single_reviewer.md
```

这个 prompt 不是 `reviewer1` / `reviewer2` / `reviewer3` 的简单复制，而是综合型审稿人：

- 评估贡献与 novelty。
- 评估方法和实验严谨性。
- 评估表达清晰度。
- 评估目标 venue fit。
- 判断主要风险和可修复性。
- 输出 OpenReview-style 结构化审稿 JSON。

同时在：

```text
configs/llm.yaml
```

为 `single_reviewer` 配置温度、token 上限和模型调用参数。

### 3.3 Node

新增：

```text
src/graphs/nodes/single_reviewer_node.py
```

职责：

- 从 `GlobalState` 读取 `parsed_paper`、`journal_requirements`、`venue_profile`、`field_info`。
- 调用 `ReviewNodes.single_reviewer(...)` 或复用现有 reviewer 调用逻辑。
- 返回一个 `ReviewerReport`。
- 写入：

```text
reviewer_reports: [single reviewer report]
stage_outputs.single_reviewer
final_decision
decision_letter
```

### 3.4 Graph 路由

修改：

```text
src/graphs/graph.py
```

重点是 `route_after_field_analyst`。

当前逻辑：

```text
QUICK_REVIEW -> review_dispatch
其他 -> se_check
```

目标逻辑：

```text
SINGLE_AGENT_REVIEW -> single_reviewer
QUICK_REVIEW -> review_dispatch
FULL_REVIEW -> se_check
```

新增边：

```text
field_analyst -> single_reviewer
single_reviewer -> final_artifact_render
```

### 3.5 API 进度路径

修改：

```text
src/api/app.py
```

新增 Single Agent 的 progress path：

```text
doc_parse
content_check
journal_req_collector
field_analyst
single_reviewer
final_artifact_render
```

这样前端进度条、节点状态和剧场才能和真实后端流程一致。

### 3.6 Artifact 输出

修改：

```text
src/services/review_service.py
```

新增中间产物：

```text
single_reviewer.json
```

最终仍然输出：

```text
final_report.md
diagnostics.json
stage_outputs.json
reviewer_reports.json
final_decision.json
```

## 4. 前端设计

### 4.1 首页模式选择

修改：

```text
frontend/src/pages/WorkbenchHome.tsx
frontend/src/api/client.ts
```

新增第三个按钮：

```text
Single Agent
单 Agent 综合审稿
最快，只生成一份综合审稿意见
```

三种模式的产品含义：

- `Full Review`：SE / AE + 多 reviewer + AE Final，最完整。
- `Quick Review`：跳过 SE / AE，直接多 reviewer。
- `Single Agent`：一个综合审稿人快速出报告。

### 4.2 右侧 agent roster

Single Agent 模式下不应该显示 4 个 reviewer，而应该显示自己的最短路径：

```text
Parser
Content Checker
Venue Context
Field Analyst
Solo Reviewer
Report Renderer
```

可以新增一个角色：

```text
Solo Reviewer / 综合审稿人
```

### 4.3 Review Theater

修改：

```text
frontend/src/components/ReviewTheater.tsx
```

Single Agent 剧场不是空白版，而是专属单人审稿剧场：

```text
Parser
-> Content Checker
-> Venue Context
-> Field Analyst
-> Solo Reviewer
-> Report Renderer
```

`Solo Reviewer` 的气泡可以轮流显示：

```text
contribution?
method?
experiment?
venue fit?
revision risk?
decision?
```

这样用户会感觉它是“一个专家快速审”，而不是“少了一堆节点”。

## 5. 最小实现步骤

### Step 1: 新增核心模式枚举

改：

```text
src/core/models.py
src/graphs/state.py
```

目标：

- 系统知道 `SINGLE_AGENT_REVIEW` 是合法模式。
- 先不接 graph。
- 先不改前端。

### Step 2: 新增 single reviewer prompt

改：

```text
prompts/single_reviewer.md
configs/llm.yaml
```

目标：

- 有一个综合审稿人的结构化输出协议。
- Router 知道这个 prompt 使用哪个 model 和参数。

### Step 3: 新增后端 single_reviewer 业务逻辑

改：

```text
src/graphs/review_nodes.py
src/graphs/nodes/single_reviewer_node.py
```

目标：

- 新节点可以调用 LLM。
- 可以返回一个 `ReviewerReport`。

### Step 4: 接入 LangGraph

改：

```text
src/graphs/graph.py
```

目标：

- `SINGLE_AGENT_REVIEW` 走 `single_reviewer`。
- `QUICK_REVIEW` 和 `FULL_REVIEW` 原流程不变。

### Step 5: 同步 API 进度和 artifact

改：

```text
src/api/app.py
src/services/review_service.py
```

目标：

- API 能正确返回 Single Agent 的节点路径。
- 本地生成 `single_reviewer.json`。

### Step 6: 后端测试

改：

```text
tests/test_workflow.py
tests/test_api.py
```

目标：

- `SINGLE_AGENT_REVIEW` 可以跑通。
- 最终有 `final_report.md`。
- `reviewer_reports` 只有 1 个。
- 不应出现 `se_check`、`ae_check`、`reviewer2`、`devils_advocate` 等多 Agent 节点输出。

验证：

```bash
.venv/bin/python -m unittest discover tests
.venv/bin/python -m src.cli doctor
```

### Step 7: 前端新增第三个模式按钮

改：

```text
frontend/src/api/client.ts
frontend/src/pages/WorkbenchHome.tsx
```

目标：

- 用户可以在首页选择 `Single Agent`。
- 请求体中的 `review_mode` 正确传到后端。

### Step 8: 单 Agent 剧场

改：

```text
frontend/src/components/ReviewTheater.tsx
frontend/public/agents-px.js
```

目标：

- Single Agent 模式显示专属剧场路径。
- 不显示多 reviewer 并行动画。
- 中央显示 `Solo Reviewer / 综合审稿人`。

### Step 9: 全链路验证

验证：

```bash
.venv/bin/python -m unittest discover tests
.venv/bin/python -m src.cli doctor
npm --prefix frontend run build
scripts/check-api-contract.sh
```

最后再用 mock 模式实际跑一次：

```bash
.venv/bin/python -m src.cli review <paper> \
  --mode SINGLE_AGENT_REVIEW \
  --venue-domain CS \
  --venue-collection CCFA \
  --venue-code AAAI \
  --output-language zh
```

## 6. 阅读顺序

如果要作为小白一步步看代码，建议按这个顺序：

1. `src/core/models.py`：先看 `ReviewMode` 是什么。
2. `src/graphs/graph.py`：看模式如何决定流程分支。
3. `src/graphs/nodes/single_reviewer_node.py`：看一个节点如何读写 `GlobalState`。
4. `src/graphs/review_nodes.py`：看节点背后的 LLM 调用逻辑。
5. `src/api/app.py`：看后端如何把节点路径暴露给前端。
6. `frontend/src/pages/WorkbenchHome.tsx`：看用户如何选择模式。
7. `frontend/src/components/ReviewTheater.tsx`：看节点事件如何变成剧场动画。

## 7. 暂不做的事情

第一版先不做：

- 不做数据库。
- 不做复杂的单 Agent benchmark。
- 不做 LangSmith 深度集成。
- 不新增联网搜索工具。
- 不修改 Full Review 和 Quick Review 的既有语义。

等 Single Agent 基础链路跑通后，再单独讨论质量评估、真实模型对比和失败恢复。
