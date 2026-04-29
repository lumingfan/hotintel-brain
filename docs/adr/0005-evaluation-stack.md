# ADR 0005 — 评测工具栈选型

状态：Accepted
日期：2026-04-27

## Context

V1 spec 原方案是 "ragas + 自写 metric"，但缺一件事：**让 eval 进 CI / 进 PR review 流程**。pytest 风格的 LLM 评测库（DeepEval）在 2024–2025 年起来后，已经成为这块的事实工具。

候选：

1. **DeepEval + ragas + 自写 metric**（本 ADR 选项）
2. 仅 ragas + 自写 metric
3. promptfoo（yaml 驱动 prompt diff）
4. TruLens / Braintrust（SaaS / 偏监控）

## Decision

采用方案 1：**DeepEval + ragas + 自写 metric**，并叠加 G-Eval 方法学用于 LLM-as-judge。

具体：

- DeepEval：pytest 风格的测试用例（`@pytest.mark.deepeval`），让 eval 与单元测试在同一套工具下跑，CI 里可以同时 fail
- ragas：现成的 RAG 评测指标（context relevance、faithfulness 等），V2 RAG 引入后启用
- 自写 metric：importance macro-F1、isReal precision-recall、ROUGE-L、confusion matrix
- G-Eval：summary / triage-hint / follow-up-hint 这种"开放式输出"用 LLM-as-judge 时，遵循 G-Eval 的"chain-of-thought 评分"方法学，避免 LLM judge 给分随意

输出：

- pytest 跑分作为最低门槛（CI 要求绿）
- 每次 prompt 变更产出一份 markdown 报告（`eval/reports/<date>-<title>.md`）
- 评分挂回 Langfuse trace，能从分数倒查现场

## Consequences

### 正面

- pytest 集成让 eval 写起来像普通测试，新人 / 自己回头都易上手
- DeepEval 内置常见 metric（answer relevancy / faithfulness / hallucination 等），不必全部手写
- ragas 是 RAG 场景的事实工具，V2 引入时不必再造轮子
- 自写 metric（macro-F1 / confusion）保留，因为业务字段（importance bucket / triage status）不是通用 LLM eval 库的标准对象
- G-Eval 给"主观字段"的 LLM-judge 立了个客观流程，不被反问"你的 judge 怎么判分"

### 负面

- 三个工具叠加，每个都有学习曲线（但都比"自己造一遍"低）
- DeepEval 的部分 metric 自带 LLM 调用，eval 跑分本身要花 token

### 缓解

- 三件套各司其职：DeepEval 跑 pytest 流程，ragas 跑 RAG metric，自写 metric 跑业务字段；不重复
- DeepEval 用 LLM 的部分挂到便宜模型（gpt-4o-mini / claude-haiku），不挂主模型

## 不选其他方案的理由

### 不选 仅 ragas + 自写 metric

- 没有 pytest 集成，eval 永远只在脚本侧；CI 卡不住质量回归
- 简历讲述少一档"eval 进 CI" 的工程故事

### 不选 promptfoo

- yaml 驱动的 prompt diff 很轻量，但范围更窄（主要是 prompt A/B），覆盖不到业务字段评测
- 可作为"以后想做 prompt A/B 时再加"的可选项，本期不上

### 不选 TruLens / Braintrust

- TruLens 偏"应用监控"，不是 batch eval
- Braintrust 是 SaaS，简历讲"eval 在 SaaS 上跑"信号弱
- Langfuse 已经覆盖了 trace + 评分挂回，不需要再加一个监控平台

## 与 Langfuse 的协作

- DeepEval / ragas / 自写 metric 跑出的分数，每条都打到 Langfuse trace（通过 `langfuse.score()`）
- 在 Langfuse UI 里可以按 score 排序、按 promptVersion 过滤、按错例分类查看
- eval 报告里贴 Langfuse trace 链接，PR review 时一键跳转

## 验证条件（V1 启动时）

- pytest 跑 200 条样本不超时（设并发 + 单条 timeout）
- DeepEval 用例 + 自写 metric 都能在 CI 里运行（CI 集成视项目阶段）
- 第一份 eval 报告能给出主指标 + confusion matrix + 10 条错例 + Langfuse 链接

## 关联文档

- `eval/protocol.md`
- `runbooks/local-dev.md` 第 3 节
- ADR 0004（Langfuse 协作）
