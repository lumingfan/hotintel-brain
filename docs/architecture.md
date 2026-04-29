# HotIntel Brain 架构

最近更新：2026-04-27（栈与功能锁定后重写）
状态：Accepted

## 1. 系统形态

- 独立 Python 服务（FastAPI + Pydantic v2）
- 进程内组合三层 chain（L1 / L2 / L3）+ V4 后台 feedback 任务
- 共用 HotPulse 的 Elasticsearch（不另起向量库），加 `dense_vector` 字段
- 模型 API 通过 LiteLLM 抽象，支持多模型切换与对比
- 所有 LLM 调用走 Langfuse trace（自托管）
- 评测 / 实验是同等公民，与服务代码并列

## 2. 锁定技术栈

```
基础
  Python 3.11
  uv                              ← 包管理（事实标准，2025+）
  ruff                            ← lint + format

服务 / 结构化
  FastAPI                         ← HTTP 服务
  Pydantic v2                     ← schema 模型
  instructor                      ← Pydantic + LLM 自动 retry/repair
  LiteLLM                         ← 模型路由抽象

Agent / Chain
  Pydantic AI                     ← L3 受限 ReAct + tool calling

RAG
  Elasticsearch (shared)          ← BM25 + dense_vector（V2 起步）
  Milvus standalone               ← V3 ablation 实验，结果驱动是否切换
  bge-large-zh-v1.5 / bge-m3      ← embedding（V2 引入时定）
  bge-reranker-v2-m3              ← reranker（V2 引入）

Observability
  Langfuse (self-hosted)          ← trace + prompt 版本 + 评分挂回 trace

评测
  DeepEval (pytest-style)
  ragas
  自写 metric                       ← importance macro-F1 / confusion matrix 等
  G-Eval                           ← LLM-as-judge 方法学

缓存
  Anthropic prompt caching         ← V1 调通后启用
  GPTCache                         ← V2/V3 视场景

协议（V3 后可选）
  MCP server                       ← Brain 也能被 Cursor/Claude Code 直接用

测试
  pytest + httpx
```

## 3. 部署形态

```
HotPulse compose.yaml
  ├── mysql / redis / rabbitmq / elasticsearch / xxl-job (existing)
  ├── langfuse + langfuse-db (new, brain V1 起)
  └── hotintel-brain (new, optional service)
        ├── FastAPI on :8090
        ├── reads ES (shared)
        ├── reads MQ (V2 异步路径)
        ├── reports trace to langfuse
        └── pulls model API via LiteLLM
```

- 默认仅本地开发，生产化非本副项目目标
- compose 加 service，不强制启动；HotPulse 不可见 Brain 时按降级路径运行
- Langfuse 自托管 docker，约 200MB 资源，本地 acceptable

## 4. 模块划分

```
src/
├── api/                  ← FastAPI routers, request/response schemas
│   ├── routes_judge.py
│   ├── routes_summarize.py
│   ├── routes_expand.py            ← V2
│   ├── routes_aggregate_hint.py    ← V2
│   ├── routes_triage_hint.py       ← V2
│   ├── routes_follow_up_hint.py    ← V3
│   ├── routes_feedback.py          ← V4
│   └── deps.py
├── chains/
│   ├── l1_singleshot.py
│   ├── l2_rag.py                   ← V2
│   └── l3_agent.py                 ← V3 (Pydantic AI)
├── prompts/
│   ├── judge_v1.md
│   ├── summarize_v1.md
│   ├── expand_v1.md                ← V2
│   ├── aggregate_hint_v1.md        ← V2
│   ├── triage_hint_v1.md           ← V2
│   ├── follow_up_hint_v1.md        ← V3
│   └── feedback_critic_v1.md       ← V4
├── retrieval/                      ← V2 起
│   ├── es_client.py
│   ├── embeddings.py               ← bge encoder
│   ├── reranker.py                 ← bge-reranker-v2-m3
│   └── retriever.py                ← BM25 + dense + rerank pipeline
├── tools/                          ← V3 起 (Pydantic AI tools)
│   ├── expand_keyword.py
│   ├── search_history.py
│   ├── fetch_doc.py
│   └── score_one.py
├── llm/
│   ├── client.py                   ← instructor + LiteLLM 包装
│   ├── budget.py                   ← token / step budget tracking
│   └── caching.py                  ← prompt caching helpers
├── observability/
│   ├── langfuse_client.py
│   └── tracing.py                  ← decorator / context for chains
├── eval/
│   ├── harness.py                  ← 单一入口
│   ├── metrics.py                  ← macro-F1 / ROUGE-L / G-Eval
│   ├── deepeval_cases.py           ← DeepEval 测试用例
│   ├── ragas_runner.py
│   ├── reports.py                  ← 报告渲染
│   └── datasets.py
├── feedback/                       ← V4 起
│   ├── pull_hotpulse.py            ← 拉 confirmed/dismissed event
│   ├── score_predictions.py        ← 事后判分
│   ├── critic.py                   ← LLM critic 生成 prompt 建议
│   └── weekly_job.py               ← 后台 cron 入口
├── mcp/                            ← V3 可选
│   └── server.py                   ← MCP server 暴露
└── common/
    ├── models.py                   ← JudgementResult / RawDocument 等
    ├── config.py                   ← Pydantic Settings
    └── logging.py
```

## 5. 数据流（按层）

### 5.1 L1 SingleShot

```
RawDocument
  → instructor + LiteLLM (judge_v1 prompt + Pydantic schema)
  → 自动 retry/repair (instructor 内置)
  → JudgementResult
  ↑ Langfuse trace (prompt version, model, tokens, latency, score)
```

失败路径：

```
schema 校验最终失败 → JudgementResult(layer=L1, partial=true, errorCode="SCHEMA_INVALID")
                  → trace 留 partial 标记
```

### 5.2 L2 RAG-Augmented

```
RawDocument
  → embeddings.encode(title + content)
  → es.search:
       - BM25 (keyword)
       - dense top-30 (cosine)
  → reranker.rerank(top-30 → top-5)
  → context = format(retrieved, max_tokens=1500)
  → instructor + LiteLLM (judge_v1 prompt + <context> + schema)
  → JudgementResult
  ↑ Langfuse trace（含 retrieved doc IDs / rerank scores）
```

降级：检索失败 / 召回为空 → 退到 L1

### 5.3 L3 Agent-Orchestrated

```
RawDocument
  → Pydantic AI Agent (with 4 tools, max 6 steps, max 2000 tokens)
  → Loop:
       observation → thought → tool_call → result
       budget check（步数 / tokens）
  → 终止：
       (a) 模型决定输出 final answer
       (b) 步数 / token 超限 → 退到 L2 当前最佳
  → JudgementResult(layer=L3, traces=[tool_calls], partial?)
  ↑ Langfuse trace（含完整 ReAct loop）
```

### 5.4 V4 Feedback Loop

```
weekly cron
  → pull HotPulse confirmed/dismissed event (last 7 days)
  → for each event with Brain prediction:
       compare predicted vs user-final
       attach "user signal" label
  → run weak-supervised eval report
  → critic LLM analyzes systematic errors
  → emit prompt改进建议 + diff
  → 报告落 eval/reports/feedback-2026-MM-DD.md
```

## 6. 与 HotPulse 的对接

### 6.1 V1：同步 HTTP

```
HotPulse pipeline
  → POST /v1/judge {rawDocument, topicContext, forceLayer?, forceModel?}
  → Brain 处理（默认 L1，可强制 L2 / L3 / 模型）
  → 返回 JudgementResult
  → HotPulse 写入 hotspot_item

HotPulse report / digest 链路
  → POST /v1/summarize {topicContext, hotspots[], style}
  → Brain 处理 → SummarizeResult
  → HotPulse 写入 topic_report.markdown_content / digest 内容
```

- 超时：HotPulse 设 5s 超时；Brain 内部 L1=2s / L2=4s / L3=10s 自身超时
- Brain 不可用 / 超时 / schema 不合规 → HotPulse 走规则 fallback

### 6.2 V2：异步 RabbitMQ + 业务扩展

```
HotPulse pipeline
  → publish "hotintel.judge.requested"
  → Brain consumer 处理
  → publish "hotintel.judge.completed"
  → HotPulse listener 写回 hotspot_item

HotPulse aggregation 钩子（hotspot 入库前）
  → POST /v1/aggregate-hint {candidateEventIds, newHotspot}
  → Brain 返回 "isSameEvent + 置信度 + 理由"
  → HotPulse 决定挂到现有 event 还是新建

HotPulse work queue 计算
  → POST /v1/triage-hint {event}
  → Brain 返回 recommendedTriageStatus
  → HotPulse 写入 work_queue.recommendation 字段
```

### 6.3 V3：Agent 接入 + Follow-up

```
HotPulse event detail 页
  → POST /v1/follow-up-hint {event}
  → Brain 返回 recommended followUpStatus + 下一步建议
  → HotPulse 在 event detail 渲染 "AI 建议" 卡片
```

### 6.4 V4：feedback bridge

```
Brain weekly_feedback_job
  → 通过 HotPulse 的只读 API 拉 confirmed/dismissed event
  → 不写回 HotPulse（仅 Brain 端报告）
```

## 7. 降级矩阵

| 触发 | 行为 |
| --- | --- |
| Brain 服务不可达 | HotPulse 走规则 fallback，不阻塞 |
| Brain 返回 `partial=true` | HotPulse 走规则 fallback；trace 留证据 |
| 模型 API 限流 / 超时 | LiteLLM 自动重试 + backoff；超过 budget 后返回 partial |
| ES 检索失败（L2） | 退化到 L1 |
| Reranker 失败（L2） | 跳过 rerank，用 dense top-5 |
| L3 budget 耗尽 | 返回 L2 当前最佳作为最终结果 |
| Langfuse 不可达 | 服务不阻塞，只在本地 stderr 落 fallback 日志 |

## 8. 配置

- 模型：环境变量 `BRAIN_DEFAULT_MODEL`，provider key 走 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`（V1 范围见 ADR 0006）
- ES：`BRAIN_ES_URL` / `BRAIN_ES_USER` / `BRAIN_ES_PASS`
- 默认层级：`BRAIN_DEFAULT_LAYER=L1`
- Embedding 模型：本地 `models/bge-large-zh-v1.5`
- Langfuse：`LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`
- 所有秘钥通过 `.env`（git-ignore）加载

## 9. 演进方向（不预支）

- V1：L1 SingleShot + judge + summarize + Langfuse + DeepEval + 200 条评测 + HotPulse intelligence stub
- V2：L2 RAG (hybrid + reranker) + expand / aggregate-hint / triage-hint / batch + Anthropic prompt caching + RabbitMQ 异步
- V3：L3 Pydantic AI Agent + follow-up-hint + 高级 RAG（HyDE 视情况）+ **Milvus ablation 实验** + MCP server（可选）
- V4：feedback 闭环 + 自动 prompt critic + 周度报告
- 不在当前规划：模型路由 A/B 灰度平台、prompt marketplace、自训练
