# HotIntel Brain

[English](README.md)

`HotIntel Brain` 是 `HotPulse` 的大模型 / RAG / agent 侧车服务。它接收主产品传来的 `raw_document` 或 `event` 上下文，输出结构化 intelligence 结果，并在模型、检索或工具链不可用时安全降级到保守 fallback。

当前仓库范围：

- L1 单次结构化 judgement / summarize
- L2 检索增强的 expand / aggregate / triage hint
- L3 单 Agent follow-up hint，带严格 budget 与 fallback

## 当前已实现的接口

目前已实现的 HTTP endpoint：

- `GET /v1/health`
- `POST /v1/judge`
- `POST /v1/judge/batch`
- `POST /v1/summarize`
- `POST /v1/embed`
- `POST /v1/expand`
- `POST /v1/aggregate-hint`
- `POST /v1/triage-hint`
- `POST /v1/follow-up-hint`

这个服务现在适合三种使用模式：

1. **Skeleton 模式**
   - 启动服务
   - 跑测试
   - 打 `/v1/health`
   - 不需要任何模型 key
2. **真实 LLM 模式**
   - 配置 OpenAI-compatible 或 Anthropic 凭据
   - 走真实 judgement / summarize / hint 生成
3. **与主产品联调模式**
   - 接到 `fullstack-product`
   - 复用 HotPulse 的 Elasticsearch 与本地 embedding / reranker 模型
   - 在真实产品页面里验证 L2 / L3 行为

## 与 HotPulse 的关系

```text
HotPulse collector / scan -> raw_document
                          -> HotIntel Brain
                          -> structured judgement / hints
                          -> hotspot_item / hotspot_event / report / follow-up UI
```

边界原则：

- Brain 是 sidecar，不是第二个独立产品
- HotPulse 负责用户工作流与最终降级语义
- Brain 负责 prompt、schema、retrieval、agent budget 和结构化输出

## 环境要求

本地使用时，至少假设你有：

- Python `3.11`
- `uv`
- 本地 virtualenv 支持

常见可选项：

- 模型凭据
  - `OPENAI_API_KEY`
  - 和/或 `ANTHROPIC_API_KEY`
- OpenAI-compatible 网关
  - `OPENAI_BASE_URL=http://localhost:17654/v1`
- Langfuse 自托管
  - 默认 UI: `http://localhost:3000`
- L2 / L3 所需 Elasticsearch
  - 一般复用 `fullstack-product/docker compose` 起的 ES
- 本地 embedding / reranker 模型目录
  - `models/bge-m3`
  - `models/bge-reranker-v2-m3`

## 安装

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

然后创建本地环境文件：

```bash
cp .env.example .env
```

模板文件：

- [.env.example](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/.env.example)

## 配置说明

### 核心运行时

对大多数本地会话，这些默认值就够了：

```dotenv
BRAIN_DEFAULT_MODEL=gpt-4o-mini
BRAIN_DEFAULT_LAYER=L1
BRAIN_LOG_LEVEL=INFO
```

### LLM provider 配置

如果你要跑真实模型调用，至少要配一条 provider 路径：

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=
ANTHROPIC_API_KEY=
```

说明：

- 如果你通过本地 OpenAI-compatible 网关转发，请填写 `OPENAI_BASE_URL`
- 该 URL 需要包含结尾的 `/v1`
- 如果没有任何模型 key：
  - `/v1/health` 会显示 `modelReachable=false`
  - 依赖真实模型调用的 L1 / L2 route 会明确失败
  - L3 follow-up hint 在产品侧仍可能返回结构化 fallback

### Langfuse 配置

```dotenv
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_PROMPT_FETCH_ENABLED=false
```

行为说明：

- 没有 Langfuse key：tracing 关闭，但服务照常可启动
- 配好 key：trace 会写到 Langfuse UI
- prompt fetch 默认关闭，避免本地还没建远端 prompt 时出现多余 404

### Retrieval / L2-L3 配置

```dotenv
BRAIN_ES_URL=
BRAIN_ES_USER=
BRAIN_ES_PASS=
```

如果你要跑真实 L2 / L3 retrieval，这组配置就是必填的。

典型本地配置：

- 从 `fullstack-product/docker compose` 启 Elasticsearch
- 然后把 `BRAIN_ES_URL` 指到 `http://localhost:9200`

## 快速启动

### A. Skeleton 模式

如果你只想确认仓库能启动、测试能过，就用这个模式。

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
pytest -q
uvicorn src.api.main:app --host 127.0.0.1 --port 8090 --reload
curl -s http://127.0.0.1:8090/v1/health | jq
```

期望：

- 服务能启动
- `/v1/health` 返回 `status=degraded`
- 没有模型凭据时 `modelReachable=false`

### B. 真实 LLM 模式

如果你要验证真实模型调用：

1. 在 `.env` 里配至少一个 provider
2. 可选启动 Langfuse
3. 启服务
4. 调真实 endpoint

示例：

```bash
curl -s http://127.0.0.1:8090/v1/judge \
  -H 'Content-Type: application/json' \
  -d @judge-sample.json | jq

curl -s http://127.0.0.1:8090/v1/summarize \
  -H 'Content-Type: application/json' \
  -d @summarize-sample.json | jq
```

### C. 与主产品联调模式

如果你要验证真实产品集成：

1. 在 `fullstack-product` 启基础设施
2. 确认 Elasticsearch 可达
3. 确认本地 embedding / reranker 模型目录存在
4. 在 `8090` 启 Brain
5. 在 `fullstack-product` backend 中启用：

```dotenv
HOTINTEL_BRAIN_ENABLED=true
HOTINTEL_BRAIN_URL=http://127.0.0.1:8090
HOTINTEL_BRAIN_FOLLOW_UP_HINT_ENABLED=true
```

6. 在真实产品页面中验证：
   - L1 / L2 scan / summarize 路径
   - L3 event detail 中的 follow-up suggestion

## 验证方式

### 自动化验证

```bash
source .venv/bin/activate
pytest -q
ruff check src tests
```

### 健康检查

```bash
curl -s http://127.0.0.1:8090/v1/health | jq
```

解读方式：

- `status=degraded`
  - 服务已启动，但模型 / ES / Langfuse 可能还没就绪
- `status=ok`
  - 当前配置下依赖都可达

### 手动验证

如果你要走产品侧的手动验证，请读：

- [fullstack-product 手动验证 runbook](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/runbooks/project-manual-verification-and-demo.md)

如果你只想看 Brain 仓本地开发细节，请读：

- [docs/runbooks/local-dev.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/runbooks/local-dev.md)

## 当前状态

当前高层结论：

- L1 / L2 / L3 代码路径都已实现
- HotPulse 产品侧集成已经接通
- 在本地缺少模型凭据时，AI 相关路径预期依赖结构化 fallback

权威状态日志请看：

- [docs/STATUS.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/STATUS.md)

## 建议继续阅读

- 文档索引：[docs/INDEX.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/INDEX.md)
- API 契约：[docs/api/contract.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/api/contract.md)
- 本地开发 runbook：[docs/runbooks/local-dev.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/runbooks/local-dev.md)
- 架构说明：[docs/architecture.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/architecture.md)
- ADR：[docs/adr/0003-structured-output-and-agent-framework.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/adr/0003-structured-output-and-agent-framework.md)
