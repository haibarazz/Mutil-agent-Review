# Roadmap

这个文件只记录近期要一步一步完善的工程计划，避免把短期执行事项塞进大的架构文档。

## Current Focus

0. Frontend / backend foundation
   - Status: started
   - Goal: 按 Claude 的 Home B 方案搭建 React/Vite 前端，并通过 FastAPI 暴露前端需要的本地 API。
   - Current slice: 首页已经可以把浏览器选择的稿件上传到 FastAPI，并复用现有 `ReviewWorkflow` 创建本地审稿 run。
   - Next slice done: 新增 `POST /api/jobs` + `GET /api/jobs/{job_id}`，前端改为创建本地异步 job 并轮询状态。
   - Progress slice done: job 状态现在包含 LangGraph 节点级进度，Home B 右侧 agent rail 可以显示 RUN / OK / ERR。
   - Artifact slice done: 新增 `GET /api/jobs/{job_id}/artifacts` 和 `/report`，首页完成后能显示 artifact 数量和报告预览。
   - Runs slice done: 新增 `GET /api/jobs` 和前端 Runs 视图，可以查看本地历史审稿任务并打开报告预览。
   - Download slice done: 新增 artifact 下载接口，Runs 报告预览区可以下载 `final_report.md`。
   - Frontend config slice done: 前端 API client 支持 `VITE_API_BASE_URL`，本地默认仍可走 Vite proxy。
   - Backend config slice done: 后端 CORS origins 支持 `APP_CORS_ORIGINS`，便于前后端分离部署。
   - App config slice done: 新增 `GET /api/config`，前端上传规则从后端契约读取，后端同步校验文件类型和大小。
   - Venues slice done: 顶部 Venues 导航接入 `GET /api/venue-catalog`，可筛选 venue 并带回 Workbench 使用。
   - Settings slice done: 顶部 Settings 导航显示 API base、后端健康状态、上传契约和 catalog 计数。
   - Library slice done: 新增 `GET /api/library`，顶部 Library 导航可以集中浏览已完成 run 的本地产物并下载。
   - Report detail slice done: 新增 `#report=<job_id>` 前端详情页，可以从 Runs / Library 打开完整 Markdown 报告和 artifact 下载列表。
   - Markdown report slice done: 报告详情页使用 Markdown/GFM 渲染，表格、标题、列表和代码块不再只是纯文本。
   - Dev scripts slice done: 新增 backend / frontend / fullstack 启动脚本和统一检查脚本，方便本地前后端联调。
   - Docker compose slice done: 新增后端 FastAPI 镜像、前端 nginx 镜像和 `docker-compose.yml`，保持前后端分离部署边界。
   - API contract slice done: 前端使用的 JSON 接口补齐 Pydantic response models，并用 OpenAPI 测试锁住关键 schema。
   - OpenAPI export slice done: 新增 `docs/api/openapi.json`、导出脚本和一致性检查脚本，统一检查会提示契约是否过期。
   - Settings contract slice done: Settings 页面读取 `/openapi.json`，展示 API contract 摘要并提供打开入口。
   - Report workflow slice done: 报告详情页复用 job 的 node events，展示工作流节点时间线、状态和耗时。
   - Active job display slice done: 顶部运行状态和右侧 agent rail 会跟随当前打开的 job，历史报告也能显示真实节点状态。
   - Failed job detail slice done: Runs 中失败或运行中的 job 也能进入详情页，查看错误摘要和节点状态。
   - Live detail slice done: 打开运行中 job 的详情页时，前端会静默自动刷新节点状态直到任务结束。
   - Workbench report action slice done: 首页审稿完成态可以直接打开完整报告或下载 `final_report.md`。
   - Frontend smoke slice done: 新增浏览器 smoke 脚本，能自动上传小稿件、创建 job，并检查完成态报告按钮。
   - Failed artifact slice done: 失败 run 的 `partial_report.md` 也会进入 Library，并且 Runs Preview 可以直接预览。
   - Failure smoke slice done: 新增失败路径浏览器 smoke，验证 failed job 能从 Runs Preview 打开 `partial_report.md` 详情页。
   - Diagnostics detail slice done: 新增 `GET /api/jobs/{job_id}/diagnostics`，报告详情页可以直接显示结构化错误摘要。
   - LLM diagnostics UI slice done: 报告详情页 Diagnostics 面板显示 LLM Calls / Errors / Fallbacks 摘要，并由浏览器 smoke 验证。
   - Job summary slice done: 新增 `GET /api/jobs/summary`，顶部 `QUEUE` 状态改为真实 job 汇总，不再显示静态假数据。
   - arXiv intake slice done: 首页 `OR PASTE` 从静态展示改成真实 arXiv PDF 拉取，后端落到 `data/uploads` 后复用现有 job 流程。
   - Preset slice done: 首页 `Save preset` 接入 `POST /api/presets`，当前审稿配置会保存到本地 `data/presets.json`。
   - Preset reuse slice done: Settings 页面接入 `GET /api/presets`，可以查看最近保存的配置并一键带回 Workbench。
   - Preset smoke slice done: 新增独立浏览器 smoke，验证 `Save preset -> Settings -> Use preset -> Workbench` 闭环。
   - Command palette slice done: 顶部 `⌘K` 从静态展示变成命令面板，可快速切换 Workbench / Runs / Library / Venues / Settings，并有独立浏览器 smoke 验证。
   - Desktop smoke slice done: 新增 1440px 桌面视口浏览器 smoke，固定验证 Workbench 主区和右侧 agent rail 的网页端布局。
   - Drag upload slice done: 首页上传区支持真实拖拽放下稿件，复用同一套文件类型/大小校验，并有独立浏览器 smoke 验证。
   - Cancel job slice done: 新增 `POST /api/jobs/{job_id}/cancel`，前端 Runs / Report / 当前运行态可取消 QUEUED/RUNNING job，并有 API 与浏览器 smoke 验证。
   - Retry job slice done: 新增 `POST /api/jobs/{job_id}/retry`，前端 Runs / Report / 当前终态 run 可复用原配置重跑，并有 API 与浏览器 smoke 验证。
   - Runs filter slice done: `GET /api/jobs` 支持按状态过滤，前端 Runs 页可切换 All / Active / Done / Failed / Canceled，并有 API 与浏览器 smoke 验证。
   - Runs search slice done: `GET /api/jobs?q=...` 支持按 job id、论文文件名、venue、状态等元信息搜索，前端 Runs 页接入搜索框，并有 API 与浏览器 smoke 验证。
   - Smoke robustness slice done: filter smoke 默认端口被占用时会自动选择空闲端口；显式指定端口时仍严格失败，避免覆盖用户配置。

1. Node-level verbose logging
   - Status: done
   - Goal: 用 `REVIEW_VERBOSE=true` 在终端看到每个 LangGraph 节点的 start / done / error 和耗时。

2. LLMRouter-level verbose logging
   - Status: done
   - Goal: 在终端看到每次 LLM 调用的 prompt、provider、model、attempt、fallback 和耗时。
   - Boundary: 不打印 API key、论文全文、完整 prompt。
   - Done: `REVIEW_LLM_VERBOSE=true` 会输出安全的 router start / done / error / fallback 摘要，只包含 prompt 名称和 prompt 长度。

3. Diagnostics artifacts
   - Status: started
   - Goal: 把节点错误、fallback 事件、最终失败原因稳定写入 `data/runs/<run_id>/diagnostics.json`。
   - LLM call artifact slice done: `LLMRouter` 的安全调用摘要会写入 `llm_calls.jsonl`，并在 `diagnostics.json` 里保留 call/error/fallback 计数。
   - LLM call timeline slice done: 新增 `/api/jobs/{job_id}/llm-calls`，报告详情页可以展示安全的 LLM 调用时间线。

4. Partial failure output
   - Status: started
   - Goal: 某些节点失败时，不一定直接中断；能生成 partial report，告诉用户已完成哪些阶段、失败在哪里。
   - Simple version done: graph 失败时也写一个 `partial_report.md`，API 和前端报告详情页可以像读取 final report 一样读取它。
   - Later slice: 节点失败后，系统根据错误类型决定生成 partial report 还是进入 fallback output。
