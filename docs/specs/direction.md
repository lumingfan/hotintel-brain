# 副项目方向：HotIntel Brain

创建时间：2026-04-27
状态：Accepted

## 1. 一句话定位

`HotIntel Brain` 是一个独立可运行的 Python 服务，作为 HotPulse 主项目的 intelligence 层供给方，负责**热点情报的研判（relevance / isReal / importance / summary）+ 关键词扩展 + 受限 Agent 编排**，并提供配套的 prompt 版本管理与系统化评测。

## 2. 为什么不做"独立科研任务"

之前曾考虑把副项目设为"我的科研任务"（具体方向略）。这一选项已废弃，原因：

- **故事不闭环**：科研任务和 HotPulse 业务无关，简历和面试需要把两个项目分开讲，复杂度反而升高
- **工程信号弱**：科研更偏算法/论文/复现，离"大模型工程实习"评价标准更远
- **评测闭环缺失**：科研任务往往以"跑通 baseline"为终点，不天然包含 prompt 版本化、降级、对接生产系统这些"工程"维度
- **时间成本不可控**：复现 SOTA 可能反复踩坑，但产出对简历的边际价值有限

废弃这一选项后，方向调整为现在的 `HotIntel Brain`。

## 3. 与 HotPulse 主项目的衔接

### 3.1 调用关系

```
HotPulse Worker  ── (raw_document) ──▶  HotIntel Brain
                                            │
                                            ▼
                                   structured judgement
                                            │
HotPulse Worker  ◀── (judgement) ────────────┘
```

### 3.2 交互方式

- **同步 HTTP**（V1 默认）：HotPulse 在 `pipeline` 阶段同步调用 Brain
- **异步 RabbitMQ**（V2 演进）：HotPulse 把 `raw_document` 入队，Brain 消费后回写到 `hotspot_item`
- **降级**：Brain 不可用 / 超时 / 返回不合规 schema 时，HotPulse 退回到现有规则路径

### 3.3 契约入口

- `POST /v1/judge` — 单条研判
- `POST /v1/judge/batch` — 批量研判（V2）
- `POST /v1/expand` — query expansion（topic 创建时调用）
- `POST /v1/summarize` — 摘要（事件 / report 生成时调用）
- `GET /v1/health` — 健康检查
- 详细字段见 `api/contract.md`

## 4. 不做的部分

明确写下来的"不做"清单（防止范围发散）：

- 不做模型微调 / SFT / LoRA / 蒸馏 / 训练
- 不做论文复现 / SOTA benchmark 跑分
- 不做与 HotPulse 业务无关的通用 LLM 应用（代码评审、PDF 问答、写作助手等）
- 不引入 Milvus / Qdrant / Pinecone（共用 HotPulse 的 ES，详见 ADR 0002）
- 不做多 Agent / A2A / 复杂 multi-agent 编排（Pydantic AI 单 agent 受限 ReAct 已足够讲清楚）
- 不做向量数据库选型对比这种"调研报告"型工作
- 不引入 LangChain / LlamaIndex / DSPy / CrewAI（栈定调见 ADR 0003）

## 5. 四阶段能力

简短版定义在这里，详细见 `specs/three-layer-capability.md`。

| 阶段 | 层 | 能力 | 引入条件 |
| --- | --- | --- | --- |
| V1 | L1 SingleShot | `instructor` + Pydantic 自动 retry + Langfuse trace + judge / summarize | 起步即做 |
| V2 | L2 RAG-Augmented | 共用 HotPulse ES + hybrid (BM25 + dense) + bge-reranker + expand / aggregate-hint / triage-hint / batch | L1 评测 macro-F1 ≥ 0.65 后 |
| V3 | L3 Agent-Orchestrated | Pydantic AI 受限 ReAct + 4 类工具 + budget + follow-up-hint + 可选 MCP server | L2 评测稳定后 |
| V4 | Feedback Loop | 用 HotPulse confirmed/dismissed event 弱监督 + LLM critic 自动生成 prompt 改进建议 | V3 完成 + 数据累积 ≥ 3 周 |

每升一层都要在同一份评测集上跑 baseline 对比，输出**质量 × 延迟 × 成本**三维报告。

## 6. 简历定位

副项目段在简历中按阶段递进式呈现，详细兑现节奏见 `roadmap.md`：

- 标题：「HotIntel Brain — 大模型情报研判与评测服务」
- 一句话：以 HotPulse 多源情报采集为输入，独立 Python 服务输出结构化研判，覆盖 prompt 版本化、`instructor` 自动 schema 修复、`Langfuse` trace、`Pydantic AI` 受限 Agent、hybrid RAG（BM25 + dense + bge-reranker）与系统化评测
- 关键 bullet 候选（V3 / V4 完成后稳定形态）：
  - V1：L1 baseline + instructor + Langfuse + DeepEval + 200 条标注集 + HotPulse HTTP 对接 + summary 三种 style
  - V2：L2 RAG（hybrid + bge-reranker） + 三个新业务 endpoint（aggregate-hint / triage-hint / expand）+ Anthropic prompt caching + RabbitMQ 异步桥
  - V3：L3 Pydantic AI 受限 ReAct（4 类工具、限步、限 token budget）+ follow-up-hint + 可选 MCP server
  - V4：feedback 闭环 + LLM critic 自动 prompt 改进建议（"evaluation-driven self-improving system"）

## 7. 成功标准

副项目的"V1 完成"判据：

- [ ] 200 条标注集落地，含 inter-rater check（自查一致率 ≥ 0.8）
- [ ] L1 SingleShot 服务可启动，`POST /v1/judge` 与 `POST /v1/summarize` 通过 schema 校验
- [ ] Langfuse 自托管已起，所有 LLM 调用走 trace 且能在 UI 看到
- [ ] eval 报告 v1 落地：importance macro-F1 / isReal P-R / summary ROUGE-L (或 G-Eval) 全部有数
- [ ] HotPulse 的 `intelligence` 模块通过 HTTP 调通 Brain，本地 smoke 输出正确
- [ ] 简历副项目段可写出 3 条具体 bullet（不是"未来计划"）

V2 / V3 / V4 的退出条件见 `roadmap.md`。
