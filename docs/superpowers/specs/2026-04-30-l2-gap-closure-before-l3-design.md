# L2 Gap Closure Before L3 Design

创建时间：2026-04-30
状态：Accepted for implementation

## 1. 背景

本轮用户目标不是直接进入 L3，而是先确认并收尾任何会阻塞 L3 的 L2 缺口；L2 收口完成并验证后，再进入 L3 设计与实现。

在实际阅读两个仓库文档、代码和当前工作树后，已经确认：

- `llm-project` 的 L2 主链路已经具备：
  - `embed`
  - `expand`
  - `aggregate-hint`
  - `triage-hint`
  - `judge/batch`
  - async judge worker 入口
- `fullstack-product` 的 L2 产品接线已经具备：
  - topic settings 扩词入口
  - event detail / overview work queue 的 triage recommendation 展示
  - search projection 的 embedding 接线骨架
  - async judge request/completed skeleton

当前不缺 L2 主能力骨架，缺的是两处会直接影响 L3 可靠性和讲述一致性的收尾问题。

## 2. 已确认的 L2 阻塞缺口

### 2.1 Reindex 路径没有回填 embedding

当前 `fullstack-product` 的实时索引同步路径会通过 `BrainEmbeddingService` 给 `HotspotSearchDocument` 回填 embedding，再写入 Elasticsearch。

但 topic / user reindex 路径在批量重建时直接把 `HotspotCardResponse` 转成 `HotspotSearchDocument` 后 bulk upsert，没有经过 `BrainEmbeddingService`。结果是：

- 新写入的热点文档有 embedding
- reindex 后重建出的热点文档可能没有 embedding
- L2 检索对“同一个索引在不同时刻”的语义能力不一致

这会让：

- `llm-project` 的 L2 dense retrieval 在重建后退化
- L3 未来依赖 `search_history` 工具时，历史检索质量不稳定

### 2.2 Async judge 回写与同步 judge 的 accepted 语义不一致

当前同步 judge 会在 HotPulse 侧按 topic rule 计算 accepted：

- `isReal == true`
- `relevanceScore >= minRelevanceScore`
- 如规则要求，`keywordMentioned == true`

但 async judge completed listener 目前只检查：

- 结果非 `partial`
- `isReal == true`

然后就可能直接插入 / 更新 `hotspot_item`

这意味着同一条样本：

- 同步模式下可能被 topic rule 拦住
- 异步模式下却会被 accepted 并进入 event / search / overview

这会导致：

- L2 sync / async 行为不一致
- 后续 L3 的升级触发基础样本不稳定
- 产品演示时难以解释“为什么同样的规则下结果不同”

## 3. 本轮范围

### 3.1 `fullstack-product`

只做 L2 缺口收尾，不做 L3 运行时代码。

需要完成：

1. 让 reindex 路径与实时写入路径对齐，保证批量重建后的 `hotspot_search` 文档继续带 embedding。
2. 让 async judge completed 回写与同步 judge 共用同一 accepted 判定语义。
3. 补齐与上述行为直接相关的测试、smoke、任务文档、状态文档和契约说明。

### 3.2 `llm-project`

本轮不新增：

- `l3_agent.py`
- `routes_follow_up_hint.py`
- L3 tools
- `Pydantic AI` runtime

只允许做与下轮准备直接相关的轻量文档同步：

- 记录 L2 已收口到什么程度
- 记录 L3 进入前的环境准备结论

## 4. 范围外

本轮明确不做：

- L3 单 Agent 运行时代码
- `POST /v1/follow-up-hint`
- event detail 的 L3 建议卡
- MCP server
- Milvus ablation
- 任何面试专用页面或 AI 独立导航入口

## 5. 设计

### 5.1 Reindex embedding 对齐

目标是让：

- 实时写入
- 手动 reindex
- 异步 / 批量重建

都写出同样结构的 `HotspotSearchDocument`

设计原则：

- 不在多个地方重复拼 embedding 逻辑
- 不改变现有 `BrainEmbeddingService` 的职责
- 尽量保持 `HotspotSearchIndexService` 继续作为 search 写入主入口

建议方案：

- 在 `HotspotSearchIndexService` 的 reindex/bulk 路径中，调用同一个 embedding enrichment 流程，而不是只在 `HotspotSearchSyncListener` 的事件监听里调用
- 让 “文档 -> enriched document -> upsert/bulkUpsert” 成为一致流程

这样做的结果：

- reindex 后的文档仍然有 embedding / embeddingModel / embeddingDimension
- dense retrieval 不会因为重建而静默退化

### 5.2 Async judge accepted 语义对齐

目标是让 async completed listener 不再单独发明一套 accepted 条件，而是复用与同步 judge 相同的判定逻辑。

设计原则：

- accepted 规则必须只有一个事实来源
- async listener 只负责“收到 Brain 结果后如何回写”，不负责维护独立业务规则
- 不引入和 L3 无关的新持久化字段

建议方案：

- 在 `intelligence` 模块里提炼一个可复用的 accepted 判定 helper / mapper
- 输入：
  - topic rule
  - Brain judgement response/result
- 输出：
  - 是否 accepted
  - 规范化后的 judgement 字段

同步 judge 和 async listener 都走这套语义。

这样做的结果：

- 同步 / 异步 judge 面向同一 topic rule 时结果一致
- 之后 L3 若仍保留 async 回写，也不会出现基础层行为分叉

### 5.3 文档和 smoke 同步

本轮实现后需要同步更新：

- `fullstack-product/docs/tasks/T-035-hotintel-brain-l2-rag-and-async-integration.md`
- `fullstack-product/docs/STATUS.md`
- 必要时更新 `fullstack-product/docs/api/hot-intel-v1-contract-baseline.md`
- `llm-project/docs/STATUS.md`

Smoke 要求：

- 至少一条真实验证 reindex 后 embedding 仍在
- 至少一条真实验证 async judge 仍遵守 topic rule 语义

## 6. 验收标准

### 6.1 行为

- 触发 search reindex 后，`hotspot_search` 中重建出的文档继续带 embedding 字段
- async judge completed 回写不会绕过 topic rule 的 accepted 门槛
- sync judge 与 async judge 对同一条样本的 accepted 语义一致

### 6.2 产品影响

- topic settings 的扩词入口继续可用
- event detail / overview work queue 的 triage recommendation 继续可见
- 不新增任何 L3 UI 或 AI 独立入口

### 6.3 验证

至少实际运行：

- `llm-project`
  - `pytest -q`
  - `ruff check src tests`
- `fullstack-product/backend`
  - `mvn -q -DskipTests compile`
  - 与本轮直接相关的定向测试
- `fullstack-product/frontend`
  - `npm run build`
- `smoke`
  - 至少一条 L2 真实产品 smoke，不是 mock 页面

## 7. 用户交互与依赖准备

本轮没有发现需要用户手动执行的大下载或重依赖安装：

- `bge-m3` 和 `bge-reranker-v2-m3` 本地目录已存在
- `llm-project` 当前不进入 `Pydantic AI` runtime，因此不需要为了 L2 收口先安装 L3 依赖

结论：本轮可直接进入实现，不再需要用户侧准备动作。

## 8. 下一步

本 spec 通过后，直接写 implementation plan，并按 TDD 先补失败测试，再做最小实现，最后用真实命令验证。
