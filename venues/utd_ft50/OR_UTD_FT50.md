# Operations Research (OR / OPRE)

> 智能体期刊画像版，更新日期：2026-05-25。资料主要来自 INFORMS 官方 Editorial Statement。此文件用于用户选择 Operations Research 后，智能体判断论文是否属于 OR 顶刊范围。

## 基本识别

- 简写：OR / OPRE
- 全名：Operations Research
- 榜单归属：UTD24；FT50
- 主要领域：Operations Research；Analytics；Optimization；Decision Science
- 出版方 / 学会：INFORMS
- 官方主页：https://pubsonline.informs.org/journal/opre
- 官方 Editorial Statement：https://pubsonline.informs.org/page/opre/editorial-statement
- Area Editors' Statements：https://pubsonline.informs.org/page/opre/editorial-statement/area-editors-statements
- 投稿指南：https://pubsonline.informs.org/page/opre/submission-guidelines

## 一句话定位

Operations Research 是 INFORMS 社群的旗舰 OR 期刊，核心使命是发表推进 OR 领域前沿知识的创新和高影响研究，尤其关注如何用分析方法改善决策。

## 官方内容定位：适合什么主题

OR 比 M&SOM 更方法和理论导向，也更强调 methodological rigor。但它并不是纯数学期刊；官方强调 OR 传统上受到实践影响，创新和影响既可以来自方法卓越，也可以来自方法对实践产生影响。

官方 area structure 包括：

- **Decision Analysis**
- **Optimization**
- **Simulation**
- **Stochastic Modeling**
- **Energy and Environment**
- **Financial Engineering**
- **Operations and Supply Chains**
- **Security and Defense**
- **Societal Impact**
- **Transportation**
- **Machine Learning and Data Science**
- **Markets, Platforms, and Revenue Management**
- **Real World OR Innovations**
- **Data, Software, and Computation**

智能体可以把 OR 的主题边界理解为：**只要论文以严谨 analytical method 推进复杂决策问题的建模、求解、分析、计算或实践应用，就可能属于 OR；但必须证明创新性和影响力。**

## 官方偏好的论文类型与贡献方式

OR 强调：

- 方法创新：新的模型、算法、理论、证明、复杂性分析、随机模型、仿真方法、优化方法。
- 实践影响：用 OR 方法解决重要现实决策问题，产生可验证、可推广的影响。
- 数学严谨：很多 OR 贡献依赖数学证明。
- 经验严谨：也可以依赖数据、软件、计算和实证验证，但需要同样严谨。
- 面向 INFORMS 社群正在增长的方向：ML/data science、market/platform/revenue management、societal impact、energy/environment 等。

## 主题 fit 判断规则

适合 OR 的论文通常满足：

- 核心贡献是 OR 方法或 OR 方法驱动的决策改进。
- 有清晰的问题形式化、模型、算法、证明、仿真、计算实验或实证验证。
- 研究问题不只是实际重要，还要体现 OR intellectual contribution。
- 贡献能被 OR 社群识别：优化、随机模型、仿真、决策分析、市场设计、数据科学、供应链、运输、金融工程、社会影响等。
- 如果是应用论文，要说明方法为什么能推广到更广泛的 OR 问题，而不只是解决一个项目。

不适合的情况：

- 只有管理 insight，没有 OR 方法深度。
- 只有工程实现，没有理论、算法、模型或计算贡献。
- 算法比较只停留在 benchmark，缺少决策问题和理论解释。
- 只用通用机器学习做预测，无法说明对 OR decision-making 的贡献。
- 数学证明、计算实验或数据验证无法支撑论文主张。

## 智能体提示词片段

```text
目标期刊是 Operations Research。
请用 OR 顶刊标准评估论文：论文必须推进如何用 analytical methods 改善决策。它可以是理论、模型、算法、仿真、计算、数据软件或现实应用，但必须体现 OR 社群认可的创新性和影响力。

优先检查：
1. 决策问题是否被清楚形式化。
2. 核心贡献是否属于 OR 方法、模型、算法、证明、仿真或严谨应用。
3. 数学严谨性和/或经验严谨性是否足够。
4. 结果是否对 OR 领域有可推广意义。
5. 是否能说明 area fit，例如 Optimization、Stochastic Modeling、Simulation、Machine Learning and Data Science、Operations and Supply Chains、Transportation 等。

如果论文只是管理实证、普通 AI 预测或工程系统实现，必须指出 OR fit 不足，并建议重构为分析决策问题。
```

## 可用于提问用户的 fit-check 问题

- 你的核心 decision problem 是什么？
- 论文的 OR 方法贡献是什么：模型、算法、证明、仿真、计算、软件、数据还是实际部署？
- 你的结果是否能推广到一类问题，而不只是一个案例？
- 你准备投 OR 的哪个 area？
- 你的数学证明、计算实验或实证验证是否足以支持主张？
- 如果是应用研究，实践影响在哪里，方法创新在哪里？

## 来源

- INFORMS Operations Research journal page：https://pubsonline.informs.org/journal/opre
- INFORMS Operations Research Editorial Statement：https://pubsonline.informs.org/page/opre/editorial-statement
- INFORMS Operations Research Area Editors' Statements：https://pubsonline.informs.org/page/opre/editorial-statement/area-editors-statements
- INFORMS Operations Research Submission Guidelines：https://pubsonline.informs.org/page/opre/submission-guidelines
