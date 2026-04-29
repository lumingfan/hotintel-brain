# 本地开发 runbook

最近更新：2026-04-29（对齐 V1 第二批已落地链路）
状态：Draft（judge/summarize/health 已可执行，eval 与 Langfuse trace 仍在补完）

## 0. 前置

- 已能在 `fullstack-product/` 用 `docker compose up -d` 起 MySQL / Redis / RabbitMQ / Elasticsearch
- 如要验证真实 LLM 调用，需准备 OpenAI 与/或 Anthropic API key，具体模型范围见 ADR 0006
- Python 3.11
- Node.js（仅供 Langfuse 自托管时拉容器）
- 本地 8GB+ 空闲内存（Langfuse + 主仓 compose 共存时）

## 1. 起 Langfuse 自托管

V1 起就需要 Langfuse 跑起来，所有 LLM 调用都走 trace。

```bash
# 当前仓库已提供 `infra/langfuse/compose.yaml`
docker compose -f infra/langfuse/compose.yaml up -d

# 默认 UI: http://localhost:3000
# 第一次进去注册账号，建一个 project，拿 publicKey + secretKey 写到 .env
```

## 2. 启动 Brain 服务

```bash
cd llm-project
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest

# 配置 .env（不进 git）
cp .env.example .env
# 必填：
#   BRAIN_DEFAULT_MODEL=gpt-4o-mini
#   OPENAI_API_KEY=sk-...              # 或只填 ANTHROPIC_API_KEY
#   OPENAI_BASE_URL=http://localhost:17654/v1   # 若使用 OpenAI-compatible 本地网关，注意带 `/v1`
#   ANTHROPIC_API_KEY=sk-ant-...
#   LANGFUSE_HOST=http://localhost:3000
#   LANGFUSE_PUBLIC_KEY=...
#   LANGFUSE_SECRET_KEY=...

# 起服务
uvicorn src.api.main:app --port 8090 --reload
```

健康检查：

```bash
curl -s http://localhost:8090/v1/health | jq
# 不配任何 key 时：status=degraded，modelReachable=false，langfuseReachable=false
# 配好模型 key + Langfuse 后：status=ok
```

## 3. 跑 eval

当前仓库已经有最小 `eval/` scaffold，但真实 baseline 仍依赖标注集与 runner 接线。

```bash
pytest tests/test_health.py -q
pytest tests/test_eval_harness.py -q

# 完整跑分（含 ragas + 自写 metric + 报告渲染）
python -m eval.run \
  --dataset data/labeled-v1.jsonl \
  --layer L1 \
  --model gpt-4o-mini \
  --prompt-version judge-v1.0 \
  --output eval/reports/2026-MM-DD-l1-baseline.md
```

等第二批接通真实 LLM 与 Langfuse trace 后，再到 Langfuse UI 看 trace 列表（filter by `tag=eval-v1`）。

本地 smoke 示例：

```bash
curl -s http://localhost:8090/v1/health | jq

curl -s http://localhost:8090/v1/judge \
  -H 'Content-Type: application/json' \
  -d @judge-sample.json | jq

curl -s http://localhost:8090/v1/summarize \
  -H 'Content-Type: application/json' \
  -d @summarize-sample.json | jq
```

## 4. 与 HotPulse 联调

V1 默认走同步 HTTP：

1. 在 `fullstack-product/` 启 backend + 依赖
2. 在 `llm-project/` 启 Brain（监听 8090）
3. HotPulse `intelligence` 客户端读环境变量 `INTELLIGENCE_BRAIN_URL=http://localhost:8090`
4. 触发一次 topic scan，观察 `hotspot_item.summary` 是否被 Brain 生成的内容覆盖
5. 故意把 Brain 关掉，再触发 scan，验证 HotPulse 走规则 fallback 不报错
6. 在 Langfuse UI 里能看到这次 scan 触发的 trace 链

V2 异步路径（V2 起再做）：

- 启 RabbitMQ（HotPulse compose 已有）
- Brain 起 consumer 监听 `hotintel.judge.requested`
- HotPulse `intelligence` 改为发布消息而非同步 HTTP
- 观察队列长度 / Brain consumer 消费 / HotPulse listener 写回

## 5. 常用命令片段（V1 实现后回填）

```bash
# 包管理（uv）
uv pip install -e ".[dev]"        # 装当前项目（dev extras）

# 代码质量
ruff check src/                   # lint
ruff format src/                  # format
pytest -v                         # 测试

# Pydantic AI agent 调试（V3 起）
python -m chains.l3_agent --debug --doc-id rd_001

# Langfuse 操作
# 在 UI 里建 prompt（"判断热点研判输入" 这一类），代码侧通过 prompt_name 拉取
```

## 6. 故障排查

| 现象 | 优先排查 |
| --- | --- |
| `/v1/health` 返回 modelReachable=false | API key 是否配置；模型名是否在 V1 白名单；当前第一批只做 key presence 检查 |
| `/v1/health` 返回 langfuseReachable=false | Langfuse 容器是否起来；publicKey/secretKey 是否一致 |
| schema 校验高频失败 | prompt 是否漏掉 instructor + Pydantic 约束；模型是否过弱；尝试切换 forceModel 对比 |
| eval 跑分卡住 | 单条样本 timeout 是否设了；并发数是否过高被 LiteLLM 限流；Langfuse 是否在写 trace 但堵塞 |
| HotPulse 看不到 Brain 输出 | 网络、URL 配置、Brain 是否真的在 8090 上、HotPulse fallback 是否提前触发 |
| L2 检索召回为 0 | `dense_vector` 是否真的写到 ES；embedding 维度是否一致；topic_id filter 是否匹配 |
| L3 总是触底 budget | prompt 是否引导得当；工具 schema 是否清晰；step / token budget 是否配置错位 |

## 7. 验收 checklist（每个 PR 都过）

- [ ] `pytest` 通过（含 DeepEval 用例）
- [ ] `ruff check src/` 与 `ruff format --check src/` 通过
- [ ] `/v1/health` 返回 ok（含 langfuseReachable）
- [ ] 改 prompt 的 PR 必须附 eval 报告 + Langfuse trace 截图链接
- [ ] 改契约的 PR 必须同步更新 `docs/api/contract.md` 和主仓 `fullstack-product/docs/api/`
- [ ] 改 chain 结构的 PR 必须同步更新 `docs/architecture.md`
- [ ] 改 ADR 触发的 PR 必须同步在 STATUS.md 留一行
