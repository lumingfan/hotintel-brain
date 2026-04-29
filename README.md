# HotIntel Brain (llm-project)

`HotIntel Brain` 是 portfolio 中的副项目，承担一件具体任务：**为 HotPulse 主项目提供大模型驱动的热点情报研判服务**。

它既可以独立运行、独立讲述，又通过明确的 HTTP / 异步契约挂回 HotPulse 主链路。

## 一句话定位

输入 HotPulse 采集到的 `raw_document`，输出结构化的研判结果（`relevance / isReal / importance / summary / expandedKeywords / followUpHint`），并提供配套的 prompt 版本管理、RAG 检索增强、受限 Agent 编排与系统化评测。

## 与主项目的关系

```
HotPulse  ── collector / scan ──▶  raw_document
              │
              ▼  HTTP (sync) or RabbitMQ (async)
       HotIntel Brain  (this project)
              │
              ▼
       structured judgement
              │
              ▼
HotPulse  ── hotspot_item / hotspot_event / notification / report
```

- HotPulse 在 collector 之后、`hotspot_item` 入库之前调用 `POST /v1/judge`
- V1 默认走同步 HTTP，V2 再演进到 RabbitMQ 异步通道，避免 LLM 延迟阻塞主请求
- Brain 不可用时，HotPulse 退回到现有规则路径，保证主链路不断

## 四阶段能力

| 阶段 | 层 / 能力 | 关键产出 |
| --- | --- | --- |
| V1 | L1 SingleShot | `instructor` + Pydantic 自动 retry + Langfuse trace + DeepEval + judge / summarize endpoint + 200 条评测 |
| V2 | L2 RAG-Augmented + 业务扩展 | Hybrid (BM25 + dense) + `bge-reranker-v2-m3` + expand / aggregate-hint / triage-hint / batch + Anthropic prompt caching + RabbitMQ 异步桥 |
| V3 | L3 Agent-Orchestrated | `Pydantic AI` 受限 ReAct + 4 类工具 + budget + follow-up-hint endpoint + 可选 MCP server |
| V4 | Feedback Loop | 用 HotPulse confirmed/dismissed event 弱监督 + LLM critic 自动生成 prompt 改进建议（"evaluation-driven self-improving system"） |

每阶段升级都用同一份评测集跑 baseline 对比，最终输出 **质量 × 延迟 × 成本** 三维报告。

## 技术栈

```
基础            Python 3.11 + uv + ruff + pytest
服务 / 结构化   FastAPI + Pydantic v2 + instructor + LiteLLM
Agent / Chain   Pydantic AI（V3）
RAG             Elasticsearch (shared) + bge-large-zh / bge-m3 + bge-reranker-v2-m3
Observability   Langfuse (self-hosted)
评测            DeepEval + ragas + 自写 metric + G-Eval 方法学
缓存            Anthropic prompt caching；GPTCache（V2/V3 视场景）
协议            主：HTTP REST API；可选：MCP server（V3 后）
```

详细取舍见 `docs/adr/0001` ~ `0006`。

## 当前状态（高层摘要）

- 方向已锁定 + 栈与功能切片已锁定 + 6 份 ADR 全部 Accepted
- **V1 第一批骨架已落地**（2026-04-27）：`pytest` + `uvicorn` 可跑通，`/v1/health` 端点工作，无需任何 API key 即可验证
- **V1 第二批已推进到 L1 闭环骨架**（2026-04-29）：`POST /v1/judge` 与 `POST /v1/summarize` 已接到 chain，OpenAI-compatible `OPENAI_BASE_URL` 已支持，`gpt-4o-mini` 本地网关 smoke 已跑通
- Langfuse health ping / prompt fallback / trace wrapper、错误映射和 eval scaffold 已落地；真正的 Langfuse trace 验证与第一份 baseline 报告仍待 Langfuse key 与标注集配齐
- 当前不做：独立微调 / 蒸馏 / 训练；不引入 Milvus / Qdrant（V3 才考虑 Milvus ablation）

详细进度见 `docs/STATUS.md`。

## 快速启动（验证 V1 第一批骨架）

```bash
cd llm-project
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 跑测试（不需要任何 API key）
pytest

# 启动服务
uvicorn src.api.main:app --port 8090 --reload

# 健康检查
curl -s http://localhost:8090/v1/health | jq
```

第一次启动时 `modelReachable` / `langfuseReachable` 都是 `false` —— 这是预期的，因为还没有配置 API key 和 Langfuse。若配置了本地 OpenAI-compatible 网关，请把 `OPENAI_BASE_URL` 写成带 `/v1` 的完整地址，例如 `http://localhost:17654/v1`。

## 目录结构（当前）

```
llm-project/
├── README.md                  ← 本文件
├── AGENTS.md                  ← 在此目录里开新会话时的工作守则
├── .gitignore
├── docs/
│   ├── INDEX.md
│   ├── STATUS.md
│   ├── WORKFLOW.md
│   ├── specs/
│   │   ├── direction.md       ← 副项目定位、与 HotPulse 衔接、不做的部分
│   │   └── three-layer-capability.md  ← V1/V2/V3/V4 能力定义
│   ├── architecture.md        ← 服务架构、模块划分、数据流、降级策略
│   ├── roadmap.md             ← V1 / V2 / V3 / V4 阶段切片
│   ├── data/
│   │   └── labeling-guide.md  ← 标注口径与样本来源
│   ├── eval/
│   │   └── protocol.md        ← 评测协议、指标定义、汇报模板
│   ├── api/
│   │   └── contract.md        ← /v1/judge /v1/summarize /v1/aggregate-hint 等契约
│   ├── runbooks/
│   │   └── local-dev.md       ← 本地启动 / 跑评测 / 联调 HotPulse
│   └── adr/
│       ├── 0001-language-and-runtime.md
│       ├── 0002-rag-on-shared-elasticsearch.md
│       ├── 0003-structured-output-and-agent-framework.md
│       ├── 0004-observability-with-langfuse.md
│       ├── 0005-evaluation-stack.md
│       └── 0006-llm-provider-selection.md
├── infra/
├── prompts/
├── pyproject.toml
├── src/
└── tests/
```

## 给协作者（含未来的我）

- 在这个目录里做的所有事情，都应该是"既能让 llm-project 独立讲清楚，又能让 HotPulse 受益"
- 任何"和 HotPulse 无关的发散实验"应该单独立项，不进这个仓
- 如果发现自己在做"科研论文复现"或"调研报告"——停下来，回到主线
