# L2 Full Product Integration Design

创建时间：2026-04-30
状态：Draft
适用范围：`llm-project` + `fullstack-product`

## 1. 背景与目标

当前 `HotIntel Brain` 已完成 L1 闭环骨架，`fullstack-product` 也已通过 `T-034` 接通最小同步 Brain stub。下一步目标不是单独把 RAG 做出来，而是把 **L2 作为真实产品能力完整接回 HotPulse**，并且满足以下展示标准：

- 现场可演示 **同步 HTTP** 链路
- 现场可演示 **RabbitMQ 异步** 链路
- 前端呈现必须是正常产品入口，不做面试专页
- 使用真实 embedding / reranker 模型链路，不使用 stub 或伪结果

本轮按用户最新要求执行两项约束：

1. 优先完成 L2 全功能，再推进 L3
2. 本轮实现与演示以 **20 条 sanity 样本 + 端到端联调** 为验收基线，不以 200 条正式标注集作为启动前置

## 2. 设计原则

### 2.1 产品优先，而非 demo 优先

L2 的前端入口必须嵌在现有产品流中：

- `expand` 进入 topic 配置体验
- `aggregate-hint` 进入 event 聚合内部逻辑
- `triage-hint` 进入 event triage / overview work queue
- `judge` 同时支持同步和异步，但 UI 不暴露 transport 细节

用户看到的是：

- topic 配置更省力
- event 聚合更稳定
- triage 更高效
- scan 异步链路更稳

而不是“这里有一个 AI 页面”。

### 2.2 跨仓职责清晰

`llm-project` 负责：

- embedding / retrieval / rerank / prompt / structured output
- L2 HTTP API 与 MQ consumer / publisher
- Langfuse trace、L2 observability、评测与 smoke

`fullstack-product` 负责：

- 业务流程编排
- 结果落库
- ES 索引写入与回填
- RabbitMQ 调度与消费
- 降级与 UI 呈现

### 2.3 真实链路，但先服务 Apple M1 本地开发

本轮真实模型链路基于 Apple M1 本机运行：

- embedding：`BAAI/bge-m3`
- reranker：`BAAI/bge-reranker-v2-m3`
- judge / summarize：继续沿用现有远端 OpenAI-compatible / OpenAI / Anthropic 路径

实现必须优先尝试 `mps`，不可用时自动退回 CPU。任何首次大模型下载由用户手动执行，assistant 只提供命令并在下载完成后继续。

## 3. 范围

### 3.1 `llm-project` 范围

- 新增 L2 检索栈：
  - embeddings provider
  - ES hybrid retriever
  - reranker
  - retrieved context formatter
- 让 `POST /v1/judge` 在 `forceLayer=L2` 或默认 L2 模式下真正走 RAG
- 新增 / 完成以下接口：
  - `POST /v1/embed`
  - `POST /v1/judge/batch`
  - `POST /v1/expand`
  - `POST /v1/aggregate-hint`
  - `POST /v1/triage-hint`
- 新增 Brain MQ 入口：
  - 消费 `hotintel.judge.requested`
  - 发布 `hotintel.judge.completed`
- Langfuse trace 中补 L2 检索信息
- 测试、runbook、状态文档同步

### 3.2 `fullstack-product` 范围

- 新建 `T-035`，承接 `T-034`
- `hotspot_search` mapping 增加向量字段
- hotspot 写链路同步调用 Brain `/v1/embed`，写回 ES 向量
- scan pipeline 在现有同步 Brain judge 基础上，补可配置异步模式
- event 聚合链路调用 `aggregate-hint`
- triage / overview work queue 接 `triage-hint`
- topic 配置页接 `expand`
- 同步前后端、任务文档、API 文档、数据模型文档、runbook

### 3.3 范围外

- 不进入 L3 agent、follow-up-hint、MCP server
- 不本地部署大语言模型
- 不新建 AI 专用页面、AI 工作台或面试模式开关
- 不以 200 条正式标注集作为本轮实现 gate

## 4. 目标产品形态

### 4.1 Topic 配置中的推荐扩词

用户在 topic 设置页维护主关键词和扩展关键词时，可以触发 Brain `expand`：

- 输入：`topicName + primaryKeyword + 已有 expandedKeywords`
- 输出：推荐扩展关键词列表
- 呈现：以“可采纳建议”的形式加入 UI，用户手动选择是否写回

系统不会自动覆盖用户已有关键词集合。

### 4.2 Event 聚合更稳，而不是更花哨

HotPulse 现有 event 体系来自规则聚合。L2 在此基础上引入 `aggregate-hint` 作为语义补充层：

- 先跑现有规则 / hash / 标题归一快路径
- 对边界 case 调用 Brain `aggregate-hint`
- 输出用于决定：
  - merge into existing
  - create new
  - uncertain -> 回退现有规则路径

前端不专门展示 aggregate-hint 卡片。用户感知是 event 粒度更合理、误拆分更少。

### 4.3 Triage recommendation 进入现有工作流

`triage-hint` 不取代人工 triage，而是为现有 triage workflow 提供 recommendation：

- event detail triage 区显示：
  - recommended status
  - confidence
  - short reasoning
- overview work queue 在 event 项上可带 recommendation 摘要

最终 triage 状态仍然由用户显式执行现有动作写回。

### 4.4 双链路共存

系统保留同步 HTTP，并新增异步 MQ judge 主链路：

- 同步 HTTP 适合：
  - topic 配置页扩词
  - report / digest summarize
  - triage recommendation
- 异步 MQ 适合：
  - scan 后热点研判
  - 批量热点落库
  - 需要削峰填谷的主吞吐路径

UI 不需要暴露“你现在走的是同步还是异步”，但 runbook 和本地演示脚本必须能分别演示两条链路。

## 5. 系统边界与主流程

### 5.1 `llm-project` 系统边界

#### 同步接口

- `POST /v1/judge`
- `POST /v1/summarize`
- `POST /v1/embed`
- `POST /v1/judge/batch`
- `POST /v1/expand`
- `POST /v1/aggregate-hint`
- `POST /v1/triage-hint`

#### 异步能力

- RabbitMQ consumer：`hotintel.judge.requested`
- RabbitMQ producer：`hotintel.judge.completed`

#### 内部模块

- `retrieval/embeddings.py`
- `retrieval/es_client.py`
- `retrieval/retriever.py`
- `retrieval/reranker.py`
- `chains/l2_rag.py`
- `api/routes_*.py`
- `mq/consumer.py` / `mq/publisher.py`（或同等职责模块）

### 5.2 `fullstack-product` 系统边界

#### 同步使用 Brain 的链路

- topic 配置页请求 AI 扩词
- report / digest summarize
- triage recommendation
- 必要时保留同步 judge fallback

#### 异步使用 Brain 的链路

- scan -> publish `hotintel.judge.requested`
- Brain 完成后 publish `hotintel.judge.completed`
- HotPulse listener 回写 `hotspot_item`
- 回写后继续触发搜索索引同步、event 聚合、overview 刷新

## 6. 数据与索引设计

### 6.1 ES `hotspot_search`

继续复用现有 `hotspot_search`，新增向量字段用于 L2 dense retrieval。

设计要求：

- 不新引入独立向量库
- 向量维度由 embedding provider 单点定义，并在写入前校验
- Brain 与 HotPulse 必须共识同一 embedding 维度
- mapping 变更通过 `fullstack-product` 文档与任务记录落地

### 6.2 `hotspot_item`

`hotspot_item` 新增最小 Brain 元数据字段，用于状态、trace 与对比，不承载新的业务对象语义：

- `brain_layer`
- `brain_trace_id`
- `brain_status`
- 可选 `brain_context_hit_count`

如现有表结构不宜扩字段，可接受放入独立 metadata 表，但默认优先少量字段直挂。

### 6.3 `hotspot_event`

event 增加 recommendation 字段，但保持 triage 主权在用户：

- `recommended_triage_status`
- `recommended_triage_confidence`
- `recommended_triage_reason`

这些字段服务于 UI 推荐与 overview 聚合，不取代现有：

- `triage_status`
- `latest_triage_note`
- `triage_updated_at`

### 6.4 topic 关键词

推荐扩词不会改变 `topic_keyword` 的主从语义：

- `PRIMARY` 仍由用户显式维护
- 新采纳的推荐词写入 `EXPANDED`
- 不自动覆盖或删除原有 expanded keywords

## 7. 接口与业务映射

### 7.1 `POST /v1/embed`

用途：

- HotPulse 在热点写入 / 搜索索引同步时请求 embedding

调用方：

- `fullstack-product` search/index sync 链路

输出：

- 向量
- model name
- vector dimension
- trace id

### 7.2 `POST /v1/judge`

用途：

- 单条热点研判

L2 行为：

- embedding + hybrid retrieval + rerank + context injection + structured judgement

### 7.3 `POST /v1/judge/batch`

用途：

- Brain 侧批量跑分 / 小批量处理

本轮不要求前端直接使用，但需要真实实现与测试，避免后续批处理路径二次返工。

### 7.4 `POST /v1/expand`

产品映射：

- topic settings 中的推荐扩词

### 7.5 `POST /v1/aggregate-hint`

产品映射：

- event 聚合边界 case 的语义判断

### 7.6 `POST /v1/triage-hint`

产品映射：

- event detail triage recommendation
- overview work queue recommendation summary

## 8. 前端产品化落点

### 8.1 Topic 配置页

推荐落点：`TopicSettingsPage` 或现有 topic 编辑体验中的关键词区域。

新增能力：

- “AI 推荐扩展关键词”触发按钮
- 建议词列表
- 逐项采纳 / 批量采纳

不新增独立 AI 页面。

### 8.2 Event detail

在现有 triage 动作区补 recommendation 区块：

- `Recommended`
- confidence
- short reason

推荐内容必须服务于 triage 动作本身，不能喧宾夺主。

### 8.3 Overview work queue

在 event 类型的待处理项上补轻量 recommendation 摘要，帮助用户快速决策，但不替代跳转到 event detail。

### 8.4 Event list / global event center

首版只允许最小增量，例如：

- 列表项增加 recommendation badge 或 recommendation 状态摘要

不扩成“AI 批量处置中心”。

## 9. 同步 / 异步链路设计

### 9.1 同步 HTTP 演示链路

至少演示以下一条：

- topic settings -> `expand` -> 用户采纳推荐扩词

建议额外可演示：

- report/digest summarize
- event detail triage recommendation

### 9.2 异步 MQ 演示链路

必须演示：

1. 触发一次 topic scan
2. HotPulse publish `hotintel.judge.requested`
3. Brain consume message 并跑真实 L2 judge
4. Brain publish `hotintel.judge.completed`
5. HotPulse listener 回写 hotspot / event / search projection
6. 页面或 API 能看到更新后的真实结果

### 9.3 失败与降级

同步失败：

- HTTP timeout / 503 / schema invalid -> 回退到现有规则路径或已有内容生成路径

异步失败：

- consumer 失败 -> MQ 可重试 / DLQ
- Brain 失败 -> 回写失败状态并触发 fallback metrics

## 10. 模型与运行方式

### 10.1 本轮模型选择

- embedding：`BAAI/bge-m3`
- reranker：`BAAI/bge-reranker-v2-m3`
- judge/summarize：保留现有远端 provider 方案

### 10.2 本地运行策略

- 首选 Apple Silicon `mps`
- 失败或不可用时自动退回 CPU
- 运行方式以 Python 本地依赖为主，不额外引入本地模型服务容器

### 10.3 下载协作约定

凡首次下载以下大体积资产，assistant 仅提供命令，由用户手动执行：

- HuggingFace 模型权重
- 大型 Docker 镜像
- 长时间依赖安装

下载完成后再继续接线与测试。

## 11. 文档策略

### 11.1 `llm-project`

本轮需要同步更新：

- `docs/api/contract.md`
- `docs/architecture.md`
- `docs/STATUS.md`
- `docs/runbooks/local-dev.md`
- 必要时新增 L2 runbook / eval 记录

### 11.2 `fullstack-product`

本轮需要同步新增 / 更新：

- `docs/tasks/T-035-...`
- `docs/api/`
- `docs/data-model/hot-intel-core-entities.md`
- `docs/STATUS.md`
- `docs/runbooks/` 中的联调与演示步骤

如果最终确认 `bge-m3` 为长期默认 embedding 方案，且与当前 ADR 文字不一致，则在实现阶段补相应 ADR / 决策记录。

## 12. 实现顺序

1. 在 `llm-project` 完成 L2 检索栈、接口与测试
2. 在 `llm-project` 完成 MQ judge consumer / producer 与 smoke
3. 在 `fullstack-product` 建 `T-035` 并补 backend 对接：
   - embed
   - aggregate-hint
   - triage-hint
   - async judge path
4. 在 `fullstack-product` 完成前端自然入口增强
5. 跑同步与异步两条联调链路
6. 更新 runbook 与演示脚本

## 13. 验收标准

### 13.1 `llm-project`

- `POST /v1/judge` 的 L2 路径真实使用 hybrid retrieval + rerank
- `POST /v1/embed`
- `POST /v1/judge/batch`
- `POST /v1/expand`
- `POST /v1/aggregate-hint`
- `POST /v1/triage-hint`
  都已真实实现、测试覆盖、可本地联调
- Langfuse trace 可看到 L2 retrieval 与上下文信息

### 13.2 `fullstack-product`

- 同步 HTTP 链路可真实演示：
  - topic 扩词
  - triage recommendation
  - summarize 相关路径至少一条
- RabbitMQ 异步链路可真实演示：
  - scan -> request queue -> Brain -> completed queue -> HotPulse 回写
- ES 向量字段已真实写入并被 Brain 检索使用

### 13.3 产品体验

- 不存在面试专用页面
- topic / event / overview 的增强都符合正常产品逻辑
- recommendation 只辅助决策，不替代用户现有 triage 操作

### 13.4 本轮验证基线

本轮不要求 200 条正式标注集闭环后才算 L2 可开工或可验收。

本轮实现完成的判据是：

- 20 条 sanity 数据可支撑基本效果检查
- 同步 / 异步联调链路可演示
- 关键接口、测试、文档、runbook 都齐

## 14. 风险与缓解

### 14.1 M1 本地性能不足

缓解：

- 先保证正确性与演示性
- embedding / rerank 支持自动退 CPU
- 将高吞吐 judge 主链路放到 MQ 异步

### 14.2 跨仓范围过大

缓解：

- 先写完整 `T-035`
- 先锁接口和数据变更，再分步实现

### 14.3 前端容易变成 AI 展示层

缓解：

- 所有新增 UI 只能挂在 topic settings、event detail、overview work queue 等现有产品对象上
- 不创建 AI 独立导航入口

### 14.4 文档与现有 ADR 偏差

缓解：

- 实现时同步更新 contract / task / data-model / status
- 遇到长期选型偏差再补 ADR，而不是口头默认

## 15. 成功定义

L2 完成后，这个项目对外讲述应变成：

“HotPulse 通过独立的 HotIntel Brain 服务完成热点研判与检索增强。Brain 在 L2 阶段已经接入真实 embedding、hybrid retrieval、reranker、topic 扩词、语义 event 聚合提示和 triage recommendation；主链路同时支持同步 HTTP 与 RabbitMQ 异步回写，前端只通过正常产品入口暴露这些能力，而不是做一套面试专用 AI 页面。”
