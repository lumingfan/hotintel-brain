# 三层能力定义

创建时间：2026-04-27
最近更新：2026-04-27（栈与功能锁定后）
状态：Accepted

`HotIntel Brain` 的研判能力按 L1 / L2 / L3 三层递进，并在 L3 之上叠一个 V4 自我改进闭环。每层有清晰的能力边界、对应工具、面向 HotPulse 的 endpoint 和评测项。

每层升级都要在同一份评测集上跑 baseline 对比，输出 **质量 × 延迟 × 成本** 三维报告（详见 `eval/protocol.md`）。

---

## L1 SingleShot（V1 主体）

### 能力

- 单次模型调用
- 输入：单条 `raw_document`（标题 + 正文 + 来源 + 发布时间 + topic 上下文）
- 输出：Pydantic v2 锁定的结构化结果
  - `relevanceScore`（0-100）
  - `isReal`（bool + 置信度）
  - `importance`（low / medium / high / urgent）
  - `summary`（≤ 100 字）
  - `keywordMentioned`（bool）
  - `reasoning`（短解释，≤ 60 字）
- 用 **`instructor`** 自动处理 schema 校验 + 自我修复 retry；最多重试 1 次后仍失败则返回 `partial=true`
- prompt 版本化（例如文件 `prompts/judge_v1.md` 对应 frontmatter `version: judge-v1.0`），每次改动留版本号 + diff
- 所有调用走 **Langfuse trace**，prompt 版本号 / 模型 / 输入输出 / token / 延迟均落到 trace 字段
- 模型抽象走 LiteLLM，请求体支持 `forceModel` 用于多模型对比

### V1 endpoint

- `POST /v1/judge` — 单条研判
- `POST /v1/summarize` — event detail / report / digest 三种 style 摘要
- `GET /v1/health` — 健康检查（含 `modelReachable` / `esReachable` / `langfuseReachable`）

### 不做

- 不调用工具
- 不检索历史
- 不多步推理

### 评测

- 200 条标注集（HotPulse `raw_document` 抽样）
- 主指标：importance macro-F1 / isReal precision-recall / summary ROUGE-L 或 G-Eval
- 工程指标：p50/p95 延迟、tokens / sample、cost / 100 samples、partial rate
- 评测工具：DeepEval（pytest 集成）+ ragas + 自写 metric
- Trace 在 Langfuse 里可点开看每条样本完整 prompt + 输出 + score

### 引入条件

V1 起步直接做。

---

## L2 RAG-Augmented + 业务扩展（V2）

### 能力升级

- L1 + 检索增强 + 多业务 endpoint
- **检索栈升级到 hybrid + reranker**：
  - 共用 HotPulse `hotspot_search` ES 索引
  - 加 `dense_vector` 字段（768 维，`bge-large-zh-v1.5` 或 `bge-m3`）
  - 检索路径 = BM25（ES 原生）+ dense top-30 → **`bge-reranker-v2-m3` rerank** → top-5
- 检索时机：在 LLM 调用之前
  - 拉同主题历史 top-k 已研判热点
  - 拉同主题近 7 天热点摘要
- 上下文构造：把 retrieved docs 拼入 prompt 的 `<context>` 段
- 降级：检索失败 / 召回为空 → 退化为 L1
- 启用 **Anthropic prompt caching**：HotPulse topic context 大量重复，命中后省钱降延迟

### V2 新增 endpoint

- `POST /v1/expand` — 关键词扩展（topic 创建 / 调整时调用，原 V1 spec 推到 V2）
- `POST /v1/aggregate-hint` — 事件聚合判定，输入候选 event 指针 + 新 hotspot，输出"是否同一事件 + 置信度 + 理由"。HotPulse 现有 sha256 hash 作为快路径，Brain 作为补充
- `POST /v1/triage-hint` — 给一个 event，输出 `recommendedTriageStatus` (`NEW/REVIEWING/CONFIRMED/DISMISSED`) + 理由 + 置信度，HotPulse work queue 用作智能预排
- `POST /v1/judge/batch` — 批量研判

### V2 不做

- 不做 query rewrite（V3 再考虑）
- 不做混合检索权重自动学习（手工 tune 加权）
- 不做语义缓存命中"模糊匹配"（V3 引入 GPTCache 时再做）

### 评测

- 同一份 200 条标注集，跑 L2 与 L1 对比；对 aggregate-hint / triage-hint / expand 各起一份独立小评测集（约 50 条）
- 期望：边界用例 importance 准确率提升、isReal 误判减少
- 同步报告：检索召回率（人工抽样判断 retrieved docs 是否相关）、延迟变化、token 成本变化
- aggregate-hint：与 HotPulse 已有 hash 链路的"同一事件"标签对比，准确率 / 召回率
- triage-hint：在 HotPulse demo 数据上人工标注 100 条 event，看 LLM 推荐的 status 与人工 label 一致率

### 引入条件

L1 macro-F1 ≥ 0.65（importance）且 isReal P-R ≥ 0.7 后再启动。

---

## L3 Agent-Orchestrated（V3）

### 能力升级

- L2 + **Pydantic AI 受限 ReAct 多步编排**
- 选 Pydantic AI（不是手写 ReAct，也不是 LangGraph）：类型安全 + 原生 tool calling + 与现有 Pydantic v2 / instructor 风格统一
- 工具集（4 个，明确边界）：
  - `expand_keyword(topic, primary_keyword) -> list[str]`
  - `search_history(topic_id, query, top_k) -> list[doc]`
  - `fetch_doc(doc_id) -> raw_document`
  - `score_one(doc, context) -> judgement`
- 限制：
  - 最大 6 步
  - 最大 2000 token 总开销
  - 工具调用次数上限：每类工具最多 2 次
- 触发条件：L2 在 `relevanceScore` 处于 [40, 60] 中间地带或 `isReal` 置信度 < 0.6 时升 L3
- 降级：超 budget / 工具异常 → 退回到 L2 当前结果
- 高级 RAG：如果 L2 评测显示 retrieval 召回是瓶颈，引入 **HyDE / 多查询重写**

### V3 新增 endpoint

- `POST /v1/follow-up-hint` — 给 event 详情，输出 `followUpStatus` 推荐 + 下一步动作建议（"等待官方说明"/"二次来源核验"/"标记完成"）+ 理由

### V3 可选交付（加分项）

- **MCP server 暴露**：让 Cursor / Claude Code 把 Brain 当工具直接用
  - 工具集复用现有 4 个
  - 不影响 HTTP 主交付
  - 简历能讲"实现了 MCP server，符合 Anthropic 2024 年提出的事实标准协议"

### 评测

- 同一份评测集，对比 L1 / L2 / L3 在质量、延迟、成本三维
- 重点看：边界用例提升幅度 vs 平均成本增幅
- 报告必含：升 L3 的样本占比、平均工具调用次数、典型失败 trace
- follow-up-hint：在 HotPulse demo 数据上人工标 50 条 event 的"理想下一步"，对比 LLM 输出

### 引入条件

L2 评测稳定且明确"L1 / L2 在某子集上质量到顶"后再启动。

---

## V4 Self-Improving Loop（亮点项目，V3 完成后）

### 能力

- 每周从 HotPulse 拉一次 confirmed / dismissed event 数据，作为弱监督信号
- 对 Brain 当初的预测做"事后判分"：
  - 当初判 `relevanceScore=85, importance=high`，但用户最终 `dismissed`，且 follow-up note 指出"实际上是噪音" → 记为弱负样本
  - 当初判 `relevanceScore=55, importance=medium`，但用户 `confirmed` 并标记 `urgent` → 记为弱正样本
- 用这批弱标签跑一份"真实分布上"的 eval 报告（与 v1 标注集互补）
- 自动生成 prompt 改进建议（用一个独立的 critic prompt + LLM 跑 diff 分析）

### V4 新增 endpoint / 后台任务

- 后台 cron：`weekly_feedback_eval`
- `GET /v1/feedback/reports` — 列出历史 feedback eval 报告
- `GET /v1/feedback/reports/:id` — 单份报告详情，含 prompt 改进建议

### 评测

- 不再是"模型对人工标签的拟合度"，而是"模型预测对真实业务结果的预测力"
- 主指标：predicted_importance 与 user_confirmed_importance 的 macro-F1
- 增量指标：每周 prompt 改 / 不改的 eval 趋势线

### 引入条件

V3 完成 + HotPulse demo 账号或真实使用沉淀至少 3 周数据后再启动。

### 简历价值

这是整个项目最容易让面试官眼前一亮的部分：「我用 HotPulse 中用户最终 confirmed/dismissed 的 event 作为弱监督信号，每周自动跑 feedback eval，对比 Brain 当初的预测与用户实际行为，并用 LLM critic 自动生成 prompt 改进建议」 —— 这是真正的 evaluation-driven self-improving system，不是 baseline + RAG + Agent 的简单堆叠。

---

## 三层 + V4 共用约束

- 所有层共用同一份 evaluation harness（`eval/run.py`）
- 所有层输出统一 Pydantic 模型（`JudgementResult` / `SummarizeResult` / `AggregateHintResult` / `TriageHintResult` / `FollowUpHintResult`）
- 所有层都有 prompt 版本号、调用记录、Langfuse trace、失败重试日志
- 任何层都允许在请求里强制指定 `forceLayer = L1 | L2 | L3`，方便对比与降级
- 任何层都允许在请求里强制指定 `forceModel`（默认走配置），方便 multi-model 对比

## 阶段与 endpoint 对照表

| 版本 | 层 | 必出 endpoint |
| --- | --- | --- |
| V1 | L1 | `judge` / `summarize` / `health` |
| V2 | L2 | + `judge/batch` / `expand` / `aggregate-hint` / `triage-hint` |
| V3 | L3 | + `follow-up-hint`；可选 MCP server |
| V4 | feedback | + 后台 cron + `feedback/reports` 查询 |
