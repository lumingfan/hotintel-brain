# llm-project 状态

最近更新：2026-04-29（V1 第二批收口中）
项目代号：`HotIntel Brain`
目标：作为 HotPulse 的 intelligence 层供给方，提供热点研判 / RAG / Agent 编排服务，以及 V4 feedback 自我改进闭环

## 当前里程碑

- 副项目方向已锁定，废弃此前"独立科研任务"设想
- **V1 第一批骨架已落地（2026-04-27 第四轮）**：可运行的 `pytest` + `uvicorn`，`/v1/health` 端点工作，无需任何 API key 即可跑通
- **V1 第二批已启动（2026-04-29）**：
  - `src/api/routes_judge.py` 已落地，`POST /v1/judge` 可返回 `503 MODEL_UNAVAILABLE`（无 key）或成功透传 chain 结果
  - `src/chains/l1_singleshot.py` 已落地：本地 prompt 文件读取、frontmatter 版本解析、成功结果包装、schema 失败降级为 `partial=true`
  - `src/api/routes_summarize.py` + `src/chains/summarize_singleshot.py` 已落地，`POST /v1/summarize` 可走完整 summarize 链路
  - `src/llm/client.py` 已接入 `instructor.from_litellm(acompletion)` 的 judge / summarize 调用入口；provider key 缺失时抛 `ModelUnavailableError`
  - 已支持 OpenAI-compatible `OPENAI_BASE_URL`；用本地网关 `http://localhost:17654/v1` + `gpt-4o-mini` 跑过真实 judge / summarize smoke
  - `src/observability/langfuse_client.py` 已接通真实 `is_reachable()`、prompt fallback、generation trace wrapper；缺 Langfuse key 时自动退回本地 prompt + `traceId=null`
  - `eval/harness.py` + `eval/metrics.py` + `scripts/sample_from_hotpulse.py` 已起最小 scaffold，能在 mock runner 下生成报告骨架
  - 已从 `fullstack-product` 本地 MySQL 真实抽出 `data/sampled-v1.jsonl`（80 条、待人工标注，不进 git）
  - 已产出第一份 engineering-only sanity baseline：`eval/reports/2026-04-29-sampled-v1-l1-baseline.md`
  - 测试已覆盖 route 无 key、成功透传、schema 降级、timeout / rate limit 映射、Langfuse health/prompt fallback、eval harness smoke
- **技术栈与功能切片均已锁定（2026-04-27 第二轮）**：
  - 栈：Python 3.11 + uv + ruff + FastAPI + Pydantic v2 + `instructor` + LiteLLM + `Pydantic AI` + Elasticsearch (shared) + bge-large-zh + bge-reranker-v2-m3 + Langfuse + DeepEval + ragas + 自写 metric
  - 阶段：V1 (L1 + judge/summarize) → V2 (L2 RAG + expand/aggregate-hint/triage-hint/batch) → V3 (L3 Pydantic AI Agent + follow-up-hint + Milvus ablation + 可选 MCP) → V4 (feedback 闭环)
  - ADR 0001 / 0002 / 0003 / 0004 / 0005 / 0006 全部 Accepted
- **第三轮调整（2026-04-27）**：
  - V3 引入 Milvus ablation 实验，作为对 ADR 0002 选型的 evaluation-driven 验证；ADR 0002 升级标题与决策段
  - HotPulse 端沉淀 `fullstack-product/docs/specs/backend-evaluation-and-hardening-backlog.md`，记录主项目优化路线（仅记录、不实施），副项目 V1 按计划立即启动
  - T-034 顺手加两项：`intelligence_brain_partial_total` / `_fallback_total` 指标；规则路径 baseline 字段或表，作为 LLM vs 规则的 head-to-head 对照
- 文档骨架已起：README / AGENTS / docs/INDEX / 本文件 / docs/WORKFLOW / docs/specs/direction / docs/specs/three-layer-capability / docs/architecture / docs/roadmap / docs/api/contract / docs/eval/protocol / docs/data/labeling-guide / docs/runbooks/local-dev / docs/adr/0001 ~ 0006
- **V1 第一批实现仓骨架已落地**：
  - `pyproject.toml`（uv + ruff + pytest + mypy 配置一次到位）
  - `.python-version` / `.env.example`
  - `infra/langfuse/compose.yaml` + `infra/langfuse/README.md`（占位 + 启动指南）
  - `src/api/main.py` + `src/api/routes_health.py`（FastAPI app + `/v1/health`）
  - `src/api/routes_judge.py`（`POST /v1/judge`）
  - `src/api/routes_summarize.py`（`POST /v1/summarize`）
  - `src/common/config.py` + `src/common/models.py`（Pydantic Settings + 全部 V1 schema）
  - `src/common/prompt_loader.py`（本地 markdown prompt 读取）
  - `src/chains/l1_singleshot.py`（judge prompt 读取 + 成功包装 + schema 降级）
  - `src/chains/summarize_singleshot.py`（summarize prompt 读取 + 成功包装）
  - `src/llm/client.py`（V1 模型白名单 + 可达性检查 + judge/summarize structured-call + timeout/rate-limit 规范化）
  - `src/observability/langfuse_client.py`（真实 health ping + prompt fallback + generation trace wrapper）
  - `eval/harness.py` + `eval/metrics.py` + `eval/reports/.gitkeep`
  - `scripts/sample_from_hotpulse.py`（CLI shell）
  - `prompts/judge_v1.md` + `prompts/summarize_v1.md`（含 frontmatter / 校准提示 / changelog）
  - `tests/test_health.py` / `tests/test_llm_client.py` / `tests/test_models.py` / `tests/test_judge.py` / `tests/test_summarize.py` / `tests/test_judge_smoke.py` / `tests/test_langfuse_client.py` / `tests/test_eval_harness.py` / `tests/conftest.py`
  - 当前 `pytest` 全量可通过
- **当前仍未做完（第二批后续）**：Langfuse 真实 trace 验证（需 key）、80 条样本人工标注、带质量指标的正式 baseline report

## 进行中

- V1 第二批正在推进，当前还需要用户在本地补齐：
  1. 按 `infra/langfuse/README.md` 起 Langfuse 自托管，拿到 publicKey / secretKey
  2. 如果要继续走本地 OpenAI-compatible 网关，准备 `OPENAI_API_KEY` + `OPENAI_BASE_URL=http://localhost:17654/v1`
  3. 标注集抽样来源和连接信息（供 `scripts/sample_from_hotpulse.py` 实现真实采样）

## 下一步（V1 第二批）

在当前切片基础上继续推进。后续内容：

1. 用 Langfuse key 跑一次真实 trace，确认 `traceId` 能在 UI 里检索
2. 对 `data/sampled-v1.jsonl` 做人工标注，先完成 80 条 sanity set
3. 在已标注样本上跑正式 baseline，补齐 importance / isReal / summary 指标
4. HotPulse `T-034` 同步起步（在 fullstack-product 仓里做）

V2 / V3 / V4 待 V1 评测稳定后启动，不预支。

## 阻塞 / 风险

- **主模型选型**：✅ 已落定，见 ADR 0006（V1 = GPT + Claude）
- **API key 等待中**：第二批需要 `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` + `LANGFUSE_PUBLIC_KEY/SECRET_KEY`
- **标注集人力成本**：200 条全人工标注约 5 小时；如果时间紧，可先标 80 条 sanity check
- **Langfuse 自托管资源**：本地需 1GB+ 内存（Postgres + ClickHouse + Redis + MinIO），与 HotPulse compose 共存时 8GB 机器吃紧
- **HotPulse `T-034` 启动时机**：可在 Brain V1 第二批 Day 1（judge endpoint 真能返回 LLM 输出后）启动

## 备注

- 当前正式方向：HotPulse 的 LLM 研判服务 + 系统化评测 + 自我改进闭环
- 不做：微调 / 蒸馏 / 训练 / 论文复现 / 多 Agent A2A / 与 HotPulse 无关的领域应用
- 共用基础设施：HotPulse 的 Elasticsearch（V2 加 `dense_vector` 字段），不另引入向量库
- 不引入：LangChain / LlamaIndex / DSPy / CrewAI / Milvus / Qdrant
