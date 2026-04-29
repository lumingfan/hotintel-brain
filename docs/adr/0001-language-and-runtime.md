# ADR 0001 — 语言与运行形态选型

状态：Accepted
最近更新：2026-04-27（栈锁定后扩展）

## Context

`HotIntel Brain` 作为 HotPulse 的 intelligence 层供给方，需要决定：

- 用什么语言写
- 以什么形态部署
- 与 HotPulse 主项目（Java + Spring Boot）怎样对接
- 配套的工程基建（包管理、lint、测试）

候选方案：

1. **Python 独立服务，HotPulse HTTP 调用**（本 ADR 选项）
2. Java + Spring AI，跟主项目同技术栈
3. Python，以 MCP server / Skill 形式交付

## Decision

采用方案 1：**Python 3.11 + FastAPI 独立服务，HotPulse 通过 HTTP / RabbitMQ 调用**。

具体：

- 服务框架：FastAPI + Pydantic v2
- 模型抽象：LiteLLM
- 异步：FastAPI 原生 async + RabbitMQ（V2 起）
- 包管理：**uv**（2025 年事实标准，替代 pip / poetry）
- Lint / format：**ruff**（替代 black + isort + flake8）
- 测试：pytest + httpx
- 运行：本地 Python 进程；可选打包为 Docker 加入主仓 `compose.yaml`
- 与 HotPulse 隔离：独立进程、独立日志、独立配置

## Consequences

### 正面

- Python 在 LLM 工程生态（LiteLLM / instructor / Pydantic AI / sentence-transformers / DeepEval / ragas / Langfuse SDK）几乎所有工具都是一等公民
- 标注 / eval / 数据处理脚本在 Python 写起来代价低
- 服务独立后，副项目能独立讲、独立打分、独立替换
- 与 HotPulse 故障域隔离，Brain 挂掉不会拖垮主项目
- uv + ruff 两件套让代码质量门槛低、CI 跑得快

### 负面

- 跨语言对接（Java ↔ Python）需要明确 HTTP / 队列契约
- 部署多一个进程
- 配置（API key、ES 地址）双仓维护

### 缓解

- 契约用 OpenAPI（FastAPI 自动生成）+ `docs/api/contract.md` 双写
- 共用环境变量命名前缀 `BRAIN_*`，主仓只需配 `INTELLIGENCE_BRAIN_URL`
- HotPulse 侧加降级路径，Brain 不可用时不阻塞主链路

## 不选其他方案的理由

### 不选 Java + Spring AI

- LLM 工程生态在 Java 上明显落后；instructor / Pydantic AI / Langfuse / DeepEval 等核心工具都没有等价物
- prompt 管理、eval、向量化、agent 框架在 Java 端要么手写，要么调 Python 进程，绕远
- "副项目"放在主项目同一仓 / 同一技术栈会让两个项目难以独立讲述

### 不选 MCP / Skill 形式作为主交付

- MCP 在 2025 年起来很快，但作为**主交付形态**会丢掉"系统化评测 / RAG / Agent 编排"的工程信号
- Skill 形态适合"工具 / 插件"，不适合承载完整研判 + 评测
- **保留 MCP 作为 V3 之后的可选加分项**：在 HTTP 主交付不变的前提下，多暴露一份 MCP server，让 Brain 也能被 Cursor / Claude Code 当工具用

## 关联文档

- `architecture.md` 第 1-3 节
- `specs/direction.md` 第 3-4 节
- `runbooks/local-dev.md`
- ADR 0003（结构化输出与 agent 框架）
- ADR 0004（observability 选型）
- ADR 0005（评测工具栈）
