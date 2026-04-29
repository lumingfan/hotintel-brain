# HotIntel Brain Roadmap

最近更新：2026-04-27（栈与功能锁定后重写）
状态：Accepted

四阶段推进：V1 baseline → V2 RAG + 业务扩展 → V3 Agent + 协议加分 → V4 feedback 自我改进闭环。每个里程碑都要有真实可展示的产物。

## V1 — L1 SingleShot baseline + 主项目接入（目标：2-3 周）

### 产物

- 200 条手工标注集（HotPulse `raw_document` 抽样，覆盖 6 类来源）
- FastAPI 服务（uv + ruff + pytest 工程基建）
- 端点：`POST /v1/judge`、`POST /v1/summarize`、`GET /v1/health`
- Pydantic v2 模型：`RawDocument` / `TopicContext` / `JudgementResult` / `SummarizeResult`
- LiteLLM 接入，先跑通 GPT + Claude 双 provider，对照实验在两者内部完成
- `instructor` 包装，自动 schema 校验 + retry / repair
- Prompt v1：judge / summarize 两套
- Langfuse 自托管（docker），所有 LLM 调用走 trace
- DeepEval pytest 用例 + ragas + 自写 metric
- 第一份 eval 报告（`eval/reports/2026-MM-DD-v1-baseline.md`）
- HotPulse `intelligence` 模块的 HTTP 客户端 stub（`fullstack-product/docs/tasks/T-034`），本地 smoke 跑通

### 退出条件

- importance macro-F1 ≥ 0.65
- isReal precision ≥ 0.7 / recall ≥ 0.6
- summary ROUGE-L ≥ 0.25 或 G-Eval 平均 ≥ 3.5
- HTTP 对接在本地 smoke 中能让 HotPulse 写出 LLM 生成的 `summary`
- Langfuse 中能点开任一 prompt 版本对应的 trace 列表

### 关键决策（V1 启动前确认）

- 主模型选择 → ADR 0006（V1 = `gpt-4o-mini` / `gpt-4o` / `claude-3-5-haiku-latest` / `claude-3-5-sonnet-latest`）
- 标注口径细则 → 走 spec，不走 ADR（已沉淀在 `data/labeling-guide.md`）
- HotPulse `T-034` 启动时机：Brain V1 Day 1（FastAPI 服务跑起、judge endpoint 能返回任何合法响应）后即可启动；不必等 V1 完整评测

---

## V2 — L2 RAG + 业务扩展（目标：3-4 周，V1 完成后启动）

### 产物

- HotPulse ES `hotspot_search` 索引补 `dense_vector` 字段（V2 启动前主仓起任务 `T-035`）
- HotPulse 写链路在已研判热点入库时同步生成 embedding（写到 ES）
- Brain `chains/l2_rag.py`：
  - BM25 + dense top-30
  - `bge-reranker-v2-m3` rerank → top-5
  - context 注入 prompt
  - 同 prompt 复跑
- Anthropic prompt caching 启用（topic context 复用部分）
- 新增 endpoint：
  - `POST /v1/expand`
  - `POST /v1/aggregate-hint`
  - `POST /v1/triage-hint`
  - `POST /v1/judge/batch`
- aggregate-hint / triage-hint 各自的小评测集（约 50 条）
- Eval 报告 v2（与 v1 对比 + 新 endpoint 各自报告）
- HotPulse `T-035`（V2 主仓任务）：
  - 索引 mapping 升级
  - aggregation 钩子接入
  - work queue 增加 `recommendation` 字段
  - RabbitMQ 异步桥（`hotintel.judge.requested` / `.completed`）

### 退出条件

- L2 在 v1 标注集上：importance / isReal 至少一项 macro-F1 提升 ≥ 0.05
- 平均延迟相对 L1 ≤ 2x，p95 延迟 ≤ 3.5x
- 检索召回率（人工抽样）≥ 0.7
- aggregate-hint 与 hash 链路对比，准确率 ≥ 0.85（"显然非同事件"易判，看的是边界）
- triage-hint 与人工 100 条 label 一致率 ≥ 0.65

### 关键决策

- Embedding 模型：`bge-large-zh-v1.5` 还是 `bge-m3` → ADR 0007
- 是否引入 GPTCache → 看 V2 数据再决定（默认不上）

---

## V3 — L3 Agent + 协议加分 + Milvus Ablation（目标：4-5 周，V2 稳定后启动）

### 产物

- Pydantic AI Agent + 4 类工具实现：`expand_keyword / search_history / fetch_doc / score_one`
- Brain `chains/l3_agent.py`：受限 ReAct + 步数 / token budget tracking
- 触发策略：L2 输出 `relevanceScore ∈ [40, 60]` 或 `isReal 置信度 < 0.6` 时自动升 L3
- 新增 endpoint：`POST /v1/follow-up-hint`
- Eval 报告 v3，含三层对比（质量 × 延迟 × 成本）
- 典型 trace 样本（成功 / 升 L3 后翻转 / budget 耗尽降级）
- 高级 RAG（V3 视情况引入）：HyDE / 多查询重写
- **Milvus ablation 实验**（详见 ADR 0002 V3 章节）：
  - `infra/milvus/compose.yaml` 起 Milvus standalone（含 etcd + minio）
  - 同一 embedding 模型批量回填 Milvus collection
  - `chains/l2_rag.py` 加 `vector_backend = "es" | "milvus"` 切换开关
  - 跑 ES dense vs Milvus dense 对比评测：Recall@10 / P50 / P95 / 内存占用
  - 实验报告 `eval/reports/v3-milvus-ablation.md`
  - 决策回写 ADR 0002（保留 ES / 切到 Milvus / 部分场景双路）
- **可选加分项**：MCP server (`src/mcp/server.py`)，工具集复用 4 类工具
- HotPulse `T-036`（V3 主仓任务）：
  - event detail 页加 "AI 建议" 卡片
  - work queue 利用 follow-up-hint
  - L2/L3 灰度切换通过 forceLayer header

### 退出条件

- 在 L2 失败 / 边界用例上，L3 准确率提升 ≥ 0.1
- L3 平均成本 ≤ L2 的 4x
- 升 L3 的样本占比 ≤ 全量 30%
- follow-up-hint 与人工 50 条 label 一致率 ≥ 0.6
- Milvus ablation 实验给出明确决策（保留 / 迁移 / 双路），不要求结果一定显著
- MCP server（如果做）能在 Cursor 里被识别并调用至少 1 个工具

### 关键决策

- HyDE / 多查询重写是否做 → V3 启动前看 V2 评测找到的瓶颈
- MCP server 是否本期完成 → 看 V3 主线时间余量
- Milvus ablation 后是否真切到 Milvus → 结果驱动，不预设

---

## V4 — Feedback Self-Improving Loop（亮点项目，V3 完成后）

### 产物

- 后台 cron `weekly_feedback_eval`（在 Brain 进程内 + APScheduler 即可，不必引 Celery）
- 拉 HotPulse confirmed/dismissed event 的只读 API 客户端
- 事后判分模块（`src/feedback/score_predictions.py`）
- LLM critic（`src/feedback/critic.py`），生成 prompt 改进建议
- 每周报告（`eval/reports/feedback-YYYY-MM-DD.md`）
- 新增 endpoint：`GET /v1/feedback/reports` / `GET /v1/feedback/reports/:id`
- HotPulse `T-037`（主仓任务）：暴露 confirmed/dismissed event 的只读 API（如果当前 API 不够用）

### 退出条件

- 至少 3 周连续 feedback 报告产出（数据需要时间累计）
- prompt 改进建议至少 1 次被采纳并通过常规 v1/v2 评测验证收益
- 报告中能给出 "用户实际行为 vs Brain 预测" 的混淆矩阵

### 关键决策

- 采纳建议是手动还是自动 → 起步手动（人工 review 后改 prompt 再跑常规 eval）；自动是后续延伸
- 数据隐私：HotPulse demo 账号数据可用；真实用户数据需要明示

---

## 不在 roadmap 内（明确不做）

- 模型微调 / SFT / LoRA / 蒸馏
- 多 Agent / A2A / 复杂 multi-agent
- 论文复现 / SOTA 跑分
- 与 HotPulse 业务无关的功能（代码评审 / PDF 问答等）
- 引入 Milvus / Qdrant / Pinecone（共用 HotPulse ES，决策见 ADR 0002）
- 引入 LangChain / LlamaIndex / DSPy / CrewAI（栈定调见 ADR 0003）

## 简历兑现节奏

- V1 完成：副项目段在简历首次出现，3 条 bullet（baseline + Langfuse + HotPulse 对接）
- V2 完成：升级到 5 条 bullet（加 RAG hybrid+reranker / aggregate-hint / triage-hint / 异步桥）
- V3 完成：升级到 6 条 bullet（加 Pydantic AI Agent + follow-up-hint + 可选 MCP）
- V4 完成：副项目变成"亮点项目"，简历段稳定为 6 条 + 一句"feedback 闭环"贴面
