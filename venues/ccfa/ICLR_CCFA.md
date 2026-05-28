# International Conference on Learning Representations (ICLR)

> CCF-A 智能体 venue 画像版，更新日期：2026-05-25。资料来源为 CCF 第七版《中国计算机学会推荐国际学术会议和期刊目录》正式版、CCF 官方目录入口和结构化整理源。此文件用于“用户选择 CS/CCF-A venue 后，智能体判断主题 fit、贡献类型和写作方向”。

## 基本识别

- 简写：ICLR
- 全名：International Conference on Learning Representations
- 文件名：ICLR_CCFA.md
- 类型：会议
- 榜单归属：CCF-A
- CCF 专业领域：人工智能 / Artificial Intelligence
- 出版方 / 主办方：OpenReview
- CCF 官方目录入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/

## 一句话定位

ICLR 是 CCF 推荐目录中 **人工智能** 领域的 A 类会议。人工智能方向的顶级 venue，适合机器学习、人工智能、计算机视觉、自然语言处理、表示学习和智能系统研究。

## 官方目录定位：适合什么主题

CCF 第七版目录把该 venue 归入 **人工智能**，并标记为 **A 类**。对智能体来说，最重要的 fit 判断是：论文是否真正推进该 CCF 专业领域的核心问题，而不是只借用该领域作为应用背景。

该领域通常覆盖：

- 机器学习与深度学习方法
- 人工智能推理、规划和智能体
- 自然语言处理与语言模型
- 计算机视觉和多模态学习
- 强化学习、生成模型和表示学习
- AI 系统评测、可靠性、公平性和安全性

## CCF-A 投稿/选刊判断要点

- A 类表示 CCF 推荐目录中该专业领域的最高推荐等级之一，但 CCF 官方也说明目录是推荐建议，不建议简单作为学术评价依据。
- 主题必须与该 venue 所在 CCF 专业领域高度一致。
- 贡献需要达到顶级 CS venue 的标准：问题重要、方法扎实、实验/理论/系统评估充分、对领域有可迁移价值。
- 如果是系统或工程类论文，应有真实系统、明确工作负载、可复现实验和与强基线对比。
- 如果是理论类论文，应有清晰模型、定理、证明和相对已有结果的实质推进。
- 如果是 AI/数据类论文，应有强基线、消融、误差分析、数据/任务合理性和泛化讨论。
- CCF 官方说明中，会议论文指 Full paper 或 Regular paper；Short paper、Demo paper、Technical Brief、Summary、Findings 以及 Workshop 等不计入目录考虑范围。

## 对主题 fit 的判断规则

适合 ICLR 的论文通常满足：

- 研究问题属于 **人工智能** 的核心问题。
- 论文贡献与 International Conference on Learning Representations 的全名和领域传统一致。
- 方法、理论、系统或实验设计能够支撑 CCF-A 级别贡献。
- 结果不仅在单一数据集或场景有效，还能形成可迁移的领域 insight。
- 写作能清楚回答“为什么这个问题重要、为什么现在解决、为什么该 venue 的读者会关心”。

不适合 ICLR 的情况：

- 只是把现成技术应用到一个数据集或案例，缺少方法/系统/理论贡献。
- 主题属于相邻领域，但没有解释为什么适合 **人工智能**。
- 只有性能数字，没有机制解释、消融、误差分析或系统洞察。
- 论文贡献主要是产品实现、工程堆叠或业务报告，而不是可发表研究。

## 官方要求抓取（官方源，2026-05-25）

官方来源：

- ICLR 2026 Call for Papers: https://iclr.cc/Conferences/2026/CallForPapers
- ICLR 2026 Author Guide: https://iclr.cc/Conferences/2026/AuthorGuide

### 官方定位与主题范围

- 官方短摘：`all areas of machine learning`。
- ICLR 2026 subject areas 包括 representation learning、transfer/meta/lifelong learning、reinforcement learning、representation learning for vision/audio/language/other modalities、metric/kernel learning、probabilistic methods、generative models、causal reasoning、optimization、learning theory、graphs/geometries/topologies、fairness/safety/privacy、interpretability、datasets and benchmarks、infrastructure/software/hardware、neurosymbolic/hybrid AI、robotics/autonomy/planning、neuroscience/cognitive science、physical sciences、general ML。
- 会议采用 OpenReview，包含 public review and discussion。

### 官方投稿与评审要求

- Submission main text 最多 9 pages；discussion/rebuttal phase 和 camera ready 增至 10 pages。
- ICLR 2026 为 double blind；暴露作者身份的正文或 supplementary material 会 desk reject。
- 官方鼓励 code supplementary materials，尤其用于 replicability；reviewers 被鼓励但不被要求阅读补充材料。
- Ethics statement 和 reproducibility statement 是 recommended；ethics statement 最多 1 页，不计入页数。
- 作者需遵守 reciprocal reviewing requirement；没有注册合格 reviewer 的 submission 可能 desk reject。
- 如果 LLM 在 ideation 或 writing 中起到显著 contributor 作用，作者需在 LLM usage section 中披露；LLM 不可作为作者。

### 给智能体的硬约束

- ICLR 的 fit 应围绕 representation/learning/general ML 问题来判断；仅使用深度学习工具解决非 ML 主题，不自动适合 ICLR。
- 对论文建议中应强制加入 reproducibility statement、可匿名代码/数据、清晰假设或实验细节。
- 如果论文涉及 LLM 辅助研究或写作，要提示用户按官方要求披露显著使用情形。

## 智能体提示词片段

```text
目标 venue 是 International Conference on Learning Representations (ICLR)，CCF-A，类型为会议，所属 CCF 专业领域为：人工智能 / Artificial Intelligence。

请按 CCF-A 顶级 CS venue 标准评估论文：先判断研究问题是否真正属于该专业领域，再检查贡献是否达到顶级会议要求。重点评估问题重要性、技术/理论/系统新意、实验或证明强度、与强基线对比、可复现性、局限性和领域影响。

如果论文只是把通用方法套到一个场景，或者主题与 人工智能 关系弱，请明确指出 fit 不足，并建议如何重写为该领域核心问题。
```

## 可用于提问用户的 fit-check 问题

- 你的论文最核心的 CS 问题是什么？它为什么属于 **人工智能**？
- 你的贡献是理论、算法、系统、实证、数据集、benchmark，还是多种结合？
- 你和该 venue 近三年论文相比的新意在哪里？
- 你的 strongest baselines、ablation、scalability 或 proof obligations 是否足够？
- 如果审稿人认为这是相邻领域论文，你如何解释它适合 ICLR？

## 来源

- CCF 官方目录入口：https://www.ccf.org.cn/Academic_Evaluation/By_category/
- CCF 第七版正式目录 PDF：CCF 官方页面中的“第七版中国计算机学会推荐国际学术会议和期刊目录（正式版）”
- 结构化整理源：https://ccf.atom.im/
- GitHub Gist 结构化 JSON：https://gist.github.com/ayusdixit/3dac1dcc26ece8a2ddbe3da019d671ea
