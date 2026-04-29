# ADR 0003 — 结构化输出与 Agent 框架选型

状态：Accepted
日期：2026-04-27

## Context

Brain 需要两类能力：

1. **结构化输出**：所有 LLM 调用必须返回 Pydantic 锁定的 JSON，且能在 schema 校验失败时自动 retry / repair
2. **Agent 编排**（V3）：受限多步 ReAct，含 4 类工具与 budget 限制

候选方案需要在"轻量 / 工程化 / 简历讲述价值"三方面权衡。

候选：

| 类别 | 候选 |
| --- | --- |
| 结构化输出 | (a) 手写 JSON Mode + try/except 重试 (b) `instructor` (c) Outlines (d) Guidance |
| Agent 框架 | (a) 手写 ReAct loop (b) **Pydantic AI** (c) LangGraph (d) CrewAI / AutoGen / Swarm |

## Decision

- 结构化输出：**`instructor`**
- Agent 框架：**Pydantic AI**

## Consequences

### 正面

**结构化输出 = `instructor`**

- 与 Pydantic v2 原生绑定，schema 定义复用
- 自动 retry / repair：模型输出不合规时把错误信息塞回 prompt 让模型自己修，比手写 try/except 干净一档
- 与 LiteLLM 兼容（`instructor.from_litellm()`）
- 简历讲解："用 instructor 把 LLM 输出锁到 Pydantic schema，自动处理 schema 不合规时的 retry / repair" 是一个干净的工程描述

**Agent 框架 = Pydantic AI**

- 类型安全、tool calling 原生支持、与 instructor + Pydantic v2 风格统一
- 比 LangGraph 轻量：不引入 LangChain 依赖树
- 学习曲线低：Pydantic AI 的 `Agent.run()` 和 `@agent.tool()` 装饰器一目了然
- 2024 末发布，2025 年快速升温，简历是个新词
- 与 ReAct 概念兼容，面试讲"我用 Pydantic AI 实现了受限 ReAct，限步、限 token、4 类工具"完全顺畅

### 负面

**`instructor`**

- 引入一层封装，调试 LLM 实际请求要看 instructor 内部
- 重试链路黑盒（但 Langfuse trace 能补上）

**Pydantic AI**

- 相对新，社区成熟度不及 LangGraph
- 如果 V3 需求超出 Pydantic AI 能力（例如长时间状态机、跨会话 memory），可能需要切走

### 缓解

- `instructor` 的实际请求都通过 Langfuse trace 落地，调试不依赖 instructor 内部日志
- Pydantic AI 不满足 V3 需求时，回到本 ADR 重新评估 LangGraph

## 不选其他方案的理由

### 不选手写 JSON Mode + try/except

- 实际等同于"重新发明 instructor 的功能"，工程不优雅
- 简历讲述时 "我手写了 schema retry 逻辑" 会被反问 "为什么不直接用 instructor"

### 不选 Outlines / Guidance

- Outlines 用 finite state machine 强制结构化，对开源模型很强；但商用模型已有 JSON Mode / Tool Calling，Outlines 优势不明显
- Guidance 偏 Microsoft 生态，独立度不如 instructor

### 不选手写 ReAct loop（V3 阶段）

- 在 2026 年简历语境下手写 ReAct 是负信号："为什么不用 Pydantic AI 或 LangGraph"
- 手写实现的 budget tracking / tool routing / 错误处理代码量与 Pydantic AI 提供的差不多，但 Pydantic AI 是验证过的工程方案

### 不选 LangGraph

- 引入 LangChain 依赖树（数百个间接依赖），项目重量级急升
- LangGraph 是状态机模型，对我们"受限 ReAct + 4 类工具" overkill
- 但 LangGraph 是行业用得最广的，简历上认知度更高 —— 我们用 Pydantic AI 时要在面试讲解里准备好"为什么不用 LangGraph"的答案：
  - 项目轻量，单 agent + 受限步骤不需要 stateful graph
  - 与现有 Pydantic v2 / instructor 栈风格一致，认知负担小
  - Pydantic AI 是 Pydantic 团队出的，类型安全更好

### 不选 CrewAI / AutoGen / Swarm

- 多 agent 不是我们方向（明确不做）
- 单 agent 用这些框架反而绕远

## 验证条件（V1 / V3 启动时）

- V1 起步用 instructor，跑 200 条评测时 partial rate ≤ 5%
- V3 起步用 Pydantic AI，跑 100 条 L3 升级样本时：
  - 平均工具调用次数 ≤ 4
  - budget 触底降级率 ≤ 20%

任何一条不达标，回到本 ADR 重新评估。

## 关联文档

- `specs/three-layer-capability.md` L1 / L3 段
- `architecture.md` 第 4-5 节
- `api/contract.md`
