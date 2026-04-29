# ADR 0004 — Observability 选 Langfuse

状态：Accepted
日期：2026-04-27

## Context

LLM 工程的"可观测性"是 2024–2025 年新生态，专门解决：

- 每条 LLM 调用的完整 prompt + 输入 + 输出 + 评分要可追溯
- prompt 版本切换时 trace 能 diff
- token 成本与延迟在不同模型之间能对比
- 评测分数能挂回 trace 找到典型样本

V1 spec 之前完全没覆盖 observability，是个明显漏。补上的方式有：

候选：

1. **Langfuse 自托管**（本 ADR 选项）
2. LangSmith（LangChain 自家商业版）
3. Phoenix（Arize 开源）
4. 不上专用工具，自己打结构化日志 + Grafana / OpenTelemetry GenAI

## Decision

采用方案 1：**Langfuse 自托管，V1 起步即接入**。

具体：

- 部署：`infra/langfuse/compose.yaml`，含 `langfuse-web / langfuse-worker / langfuse-db (Postgres) / clickhouse`
- 接入：所有 LLM 调用通过 instructor + LiteLLM 时挂 `@observe()` 装饰器
- prompt 管理：在 Langfuse UI 里建 prompt（`judge-v1.0` 等），代码侧通过 `langfuse.get_prompt(name, version)` 拉取，不在代码里硬编码 prompt 字面量
- 评分回写：DeepEval / ragas 跑完每条样本，将分数挂到对应 trace ID
- 错误处理：Langfuse 不可达时服务不阻塞，本地 stderr 落 fallback 日志

## Consequences

### 正面

- 全链路可视化：prompt 改动 / 模型切换 / RAG 上下文 / Agent 多步调用全部能在 trace 里点开
- prompt 版本切换天然 A/B：同一 endpoint 不同 prompt 版本各自挂自己的 trace 集
- 评测时"哪些样本翻车了 / 翻车时 prompt 长什么样"一键追到现场
- 简历讲述："我用 Langfuse 自托管做 LLM observability，prompt 版本 / token 成本 / 延迟全部可追溯，eval 分数挂回 trace" 是个清晰的工程故事
- 开源 / 自托管，不锁厂商

### 负面

- 多一个服务：Postgres + ClickHouse 起来约 600MB 内存
- 学习曲线（虽然不长）
- prompt 管理双轨：本地文件 + Langfuse UI；要明确哪边是事实来源

### 缓解

- 本地开发环境充足，600MB 内存 acceptable
- prompt 的事实来源约定为 Langfuse UI；代码侧 `prompts/` 目录只放"模板初稿和 README"，不参与运行时
- 服务级开关 `LANGFUSE_ENABLED`，单元测试 / CI 时可关闭

## 不选其他方案的理由

### 不选 LangSmith

- LangChain 商业版，绑 LangChain 生态；我们决定不用 LangChain（详见 ADR 0003）
- 闭源 SaaS，定价不透明
- 简历上容易被"为什么用 LangSmith 不用 Langfuse"反问

### 不选 Phoenix

- Phoenix 偏"评测 + dashboards"，trace UI 没 Langfuse 工程化
- prompt 管理能力较弱

### 不选自己打结构化日志 + OTel GenAI

- 重复造轮子，且 OTel GenAI semantic convention 还在草案阶段
- 简历讲述："我自己打日志做 LLM observability" 是负信号
- 真要做 observability，挑成熟工具是更工程化的选择

## 验证条件（V1 启动时）

- Langfuse 容器能稳定起 24 小时不 OOM
- judge / summarize 调用 100% 落到 trace
- 至少能在 UI 里跑一次"按 promptVersion 过滤 + 按 score 排序" 的实战 query
- DeepEval 跑完后，至少 80% trace 上挂着评测分数

任何一条不达标，回到本 ADR 重新评估或简化接入方式。

## 关联文档

- `architecture.md` 第 2-5 节
- `runbooks/local-dev.md` 第 1 节
- `eval/protocol.md`
