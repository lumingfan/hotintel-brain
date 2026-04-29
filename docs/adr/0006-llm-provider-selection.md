# ADR 0006 — V1 LLM Provider 选型：GPT + Claude

状态：Accepted
日期：2026-04-27

## Context

V1 启动需要明确接哪些 LLM provider。可选范围广，但每接一个都意味着 prompt 调试 / API key 管理 / 评测对比 / 工程兼容多一份成本。需要在"覆盖广度"和"工程聚焦"之间做权衡。

候选：

1. **V1 只接 GPT + Claude，V2+ 再考虑国产**（本 ADR 选项）
2. V1 同时接 GPT + Claude + DeepSeek + Qwen（一次到位）
3. V1 只接 1 个（如 GPT 或 Claude）

## Decision

V1 只接两条 provider：

- **OpenAI**：`gpt-4o-mini`（默认）/ `gpt-4o`（对比实验）
- **Anthropic**：`claude-3-5-haiku-latest`（默认）/ `claude-3-5-sonnet-latest`（对比实验）

通过 LiteLLM 抽象，请求体里允许 `forceModel` 显式指定模型，方便评测对比。

国产模型（DeepSeek / Qwen / Doubao 等）**推到 V2 之后**作为对照实验引入。

## Consequences

### 正面

**生态成熟度**

OpenAI 与 Anthropic 在以下能力上是 LiteLLM + instructor 的一等公民，国产模型仍在追赶：

- JSON Mode / Tool Calling 原生支持稳定
- Anthropic prompt caching 原生支持（V1 调通后启用，对 HotPulse topic context 复用场景天然契合）
- instructor 的自动 retry / repair 在这两家上跑得最稳
- LiteLLM 的 token 计费 / 模型路由对这两家测试覆盖最充分

**简历语境**

大模型实习面试官对 GPT / Claude 的预期最稳，能聊到具体 model 级别（`gpt-4o-mini` 的成本 / `claude-3-5-haiku` 的速度 / `claude-3-5-sonnet` 的质量），具体的"我用了哪个 model 跑了哪批 eval" 比"我接了 N 个国产模型" 信号更强。

**评测可比性**

国际顶级模型作为 baseline 锚点：副项目简历段如果未来要讲"我对比了 X / Y / Z 模型在我们标注集上的表现"，先有 GPT + Claude 这个公认 baseline 是必需的。后续接国产模型时也以这两条线作为对照轴。

**工程聚焦**

V1 的核心是"L1 baseline + Langfuse + DeepEval + HotPulse 对接"四件事跑稳，每多一条 provider 就多一份 prompt 适配 / API key 管理 / 评测对比 / 故障排查的负担。V1 不需要承载"国产模型也支持"这件事。

### 负面

- 简历上"国产模型也接过"是个常见加分点，V1 起步暂时没有
- 真实生产环境如果对国产合规有强需求（如政企客户），V1 不覆盖；但本项目是个人 portfolio，不在乎这条

### 缓解

- **V2 接国产模型作为对比实验**：在 V2 RAG / 业务扩展期间，把同一 prompt 在 DeepSeek-Chat / Qwen-Plus / Doubao-Pro 上跑同份评测集，输出"国际 vs 国产"质量 × 成本对比报告，这本身就是简历亮点
- LiteLLM 抽象层让 V2 接国产模型时只是改配置 + 几个适配点，不需要改 chain 代码

## V1 默认配置

环境变量：

```
BRAIN_DEFAULT_MODEL=gpt-4o-mini    # V1 默认起步模型
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

请求体可选字段：

- `forceModel`：可选，覆盖默认；允许值见 `llm/client.py` 中 `SUPPORTED_MODELS_V1`
- 不在白名单的模型直接拒绝（`400 INVALID_MODEL`），避免 V1 期间误调到不可控的 provider

## 不选其他方案的理由

### 不选 V1 一次接 GPT + Claude + DeepSeek + Qwen

- V1 工程聚焦最重要，多 2 条 provider 意味着多 2 份 prompt / eval / 故障排查负担
- 国产模型在 instructor + Anthropic prompt caching 等高级能力上仍需特殊处理，V1 起步时会拖慢 baseline
- 同样是"接国产"，放到 V2 + 完整对比实验里讲故事比 V1 起步堆词更有价值

### 不选 V1 只接 1 个

- 单 provider 没法在 V1 就建立"对比实验"基础
- DeepEval / Langfuse 的多模型能力直接闲置
- 简历上"我跑过两个模型对比"和"我只用了一个" 是两档信号

## 验证条件（V1 启动时）

- 两条 provider 都能在 LiteLLM 下调通（先用 `/v1/health` 的 ping check）
- `forceModel` 切换在评测脚本里能跑（同份 200 条样本分别跑 `gpt-4o-mini` 与 `claude-3-5-haiku`）
- 第一份 v1 baseline 报告至少给出 GPT 与 Claude 双轨结果（哪怕只是简单 macro-F1 对比）

## 关联文档

- `architecture.md` 第 2 节技术栈
- `runbooks/local-dev.md` 第 1-3 节
- `eval/protocol.md` 第 2.6 节工程指标
- ADR 0001（语言选型）
- ADR 0003（结构化输出与 Agent 框架）
