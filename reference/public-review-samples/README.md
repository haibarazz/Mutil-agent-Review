# Public Review Samples

这个目录用于保存公开真实审稿样例的结构化观察，暂时只做参考，不改 prompts。

## 边界

- 来源优先选 OpenReview 上公开可访问的 review / meta-review / decision。
- 本目录不保存整篇 review 原文，只保存来源链接、note id、字段结构、评分分布等轻量信息。
- 如果后面要改 prompts，应该基于这些结构规律，而不是复制真实 reviewer 的长文本。

## 已下载的结构化摘要

- `openreview_review_samples_summary.json`

这个 JSON 记录了每个样例的：

- paper / venue / forum url
- official review note urls
- public notes 数量
- official review 数量
- review 字段出现频次
- rating / confidence 的简化值
- meta-review / decision note 入口

## 样例来源

| Label | Venue | Paper | Forum |
| --- | --- | --- | --- |
| `neurips_2023_poster` | NeurIPS 2023 | Feature-Learning Networks Are Consistent Across Widths At Realistic Scales | https://openreview.net/forum?id=LTdfYIvbHc |
| `iclr_2024_poster_llm_optimizer` | ICLR 2024 poster | Large Language Models as Optimizers | https://openreview.net/forum?id=Bb4VGOWELI |
| `iclr_2024_spotlight_cas` | ICLR 2024 spotlight | CAS: A Probability-Based Approach for Universal Condition Alignment Score | https://openreview.net/forum?id=E78OaH2s3f |
| `iclr_2024_oral_causal_world_models` | ICLR 2024 oral | Robust agents learn causal world models | https://openreview.net/forum?id=pOoKI3ouv1 |
| `tmlr_neural_collapse_review` | TMLR | Neural Collapse: A Review on Modelling Principles and Generalization | https://openreview.net/forum?id=QTXocpAP9p |

## 共同结构观察

OpenReview 会议类 review 常见结构：

- `Summary`
- `Strengths`
- `Weaknesses`
- `Questions`
- `Soundness`
- `Presentation`
- `Contribution`
- `Rating`
- `Confidence`
- `Ethics / Code of Conduct`

NeurIPS 样例额外常见：

- `Limitations`

ICLR 样例常见最终编辑层结构：

- `Meta Review`
- `Decision`
- `Justification For Why Not Higher Score`
- `Justification For Why Not Lower Score`

TMLR 样例更接近 journal review，结构更集中：

- `Claims And Evidence`
- `Recommendation`
- `Action Editor Comment`

## 对我们系统的启发

后面调整最终报告和 prompts 时，建议让输出更接近下面这个层次：

1. `Decision`
2. `Area Chair / AE Meta Review`
3. `Decision Letter`
4. `Review 1 / Review 2 / Review 3`
5. 每个 review 里面固定包含 `Summary`、`Strengths`、`Weaknesses`、`Questions`、`Rating`、`Confidence`
6. 如果是会议型 venue，加入 `Soundness`、`Presentation`、`Contribution`
7. 如果是期刊型 venue，加入 `Claims And Evidence` 和 `Recommendation`
8. 桌拒输出应该走编辑信格式，不应该伪装成外审 review
