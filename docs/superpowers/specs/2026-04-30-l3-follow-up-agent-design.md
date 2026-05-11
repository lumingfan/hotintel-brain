# L3 Follow-Up Agent Design

创建时间：2026-04-30
状态：Accepted for next-thread implementation

## 1. 目标

在 L2 已收口的前提下，把系统升级到 L3：

- 只在 **L2 不确定样本** 上触发
- 只用 **单 Agent**
- 只提供 **有限步、多工具、可回退** 的 follow-up intelligence
- 只接入 **真实产品路径**
- recommendation 只辅助用户，不取代现有 triage / follow-up 人工动作

本轮设计结束后：

- 本 thread 只完成设计、spec、plan、下载/依赖预备
- 下一个 thread 直接按 plan 执行，不再为普通实现细节反复交互

## 2. 当前上下文

### 2.1 已确认的基础能力

`llm-project`

- L2 已有：
  - `judge` / `judge-batch`
  - `embed`
  - `expand`
  - `aggregate-hint`
  - `triage-hint`
  - async judge worker
- Langfuse tracing 已在项目内建立
- Elasticsearch 共享索引与 embedding / reranker 路径已具备可复用基础

`fullstack-product`

- 已有 event detail、follow-up form、overview work queue、topic settings
- 已有 `triage-hint` recommendation 展示
- 已有 follow-up workflow 正式入口
- 本轮已收掉两处会阻塞 L3 的 L2 缺口：
  - reindex embedding parity
  - sync / async judge acceptance parity

### 2.2 本轮不做

- 不做多 Agent / A2A
- 不做 AI 独立导航或面试专用页
- 不做 MCP server
- 不做 Milvus ablation
- 不做 suggestion 持久化缓存层
- 不对 overview / work queue 默认大面积主动跑 Agent

## 3. 方案比较

### 方案 A：event detail 按需触发，overview 只给入口

做法：

- `follow-up-hint` 真正调用只发生在 event detail
- overview / work queue 只显示“可获取 AI 下一步建议”的入口或提示
- 用户进入 detail 后手动触发建议
- 建议结果可一键带入现有 follow-up form，但仍需用户确认提交

优点：

- 成本最低
- 产品侵入最小
- 最符合“辅助而不替代”
- 最容易把 L3 讲成真实产品增强，而不是 AI takeover

缺点：

- overview 无法直接展示完整建议正文

### 方案 B：首次生成后缓存 suggestion snapshot

做法：

- event detail 第一次请求 `follow-up-hint` 后，把结果存到 HotPulse
- overview / work queue 可以直接展示缓存摘要

优点：

- 用户跨页能看到建议结果
- 减少重复请求 Agent

缺点：

- 需要新增持久化字段或表
- 需要额外缓存失效策略
- 范围从“L3 主线”扩成“L3 + 持久化设计”

### 方案 C：后台预生成所有边界事件建议

做法：

- scan / triage 后后台批量对 eligible event 生成 follow-up hint
- 前端只读已有结果

优点：

- 用户打开即看

缺点：

- 成本最高
- 最容易把产品变成“AI 主导队列”
- 难以控制 L3 触发占比

### 推荐

选 **方案 A**。

理由：

- 最贴合当前产品结构：overview 负责派发，event detail 负责深看和采纳
- 最容易满足“有限步、多工具、可回退、产品优先”的目标
- 可以先把 L3 的 agent 核心价值讲清楚，后续如果确实需要缓存，再单独扩展

## 4. 最终设计

## 4.1 用户路径

标准路径：

1. 用户在 `/app` 或 `/topics/:id/events/:eventId` 看到一个边界事件
2. 如果事件满足 L3 eligibility，detail 区显示“获取 AI 下一步建议”
3. 用户点击后，HotPulse 后端组织 event payload，调用 Brain `POST /v1/follow-up-hint`
4. Brain 在 L3 agent 内有限步执行，返回：
   - `recommendedFollowUpStatus`
   - `suggestedActions`
   - `confidence`
   - `reasoning`
5. 前端渲染 AI 建议卡
6. 用户点击“应用建议”时：
   - 推荐状态带入现有 follow-up status 选择
   - 推荐动作和解释拼成默认备注草稿
   - 但 **不自动提交**
7. 用户仍通过现有 `PATCH /api/topics/:id/events/:eventId/follow-up` 完成正式更新

## 4.2 L3 eligibility

L3 必须只跑在 L2 不确定样本上。

本轮采用 **HotPulse 侧 eligibility gate**，而不是让 Brain 对所有 event 盲跑后再自行放弃。

推荐资格规则：

- `triageStatus` 在 `NEW` 或 `REVIEWING`
- 且满足以下任一项：
  - `topRelevanceScore` 在中间区间，建议 `[40, 65]`
  - `recommendedTriageConfidence` 为空或 `< 0.75`
  - `sourceCount <= 2` 且 `followUpStatus == NONE`

说明：

- 这里不用回头给 event 增加 `isRealConfidence` 持久化字段
- 优先复用当前 HotPulse 已有 event summary 和 L2 recommendation 字段
- 如果 next thread 落实现时发现某一条件难以稳定获取，可以保留 `topRelevanceScore + triage confidence` 这一最小版本

## 4.3 llm-project 设计

### 新增模块

- `src/chains/l3_agent.py`
- `src/api/routes_follow_up_hint.py`
- `src/tools/expand_keyword.py`
- `src/tools/search_history.py`
- `src/tools/fetch_doc.py`
- `src/tools/score_one.py`
- `prompts/follow_up_hint_v1.md`

### Agent 框架

使用 `Pydantic AI Agent`。

理由：

- 与 ADR 0003 一致
- 原生支持 tools
- 可直接使用官方 `UsageLimits`
- 能把“受限 ReAct”落成真实代码约束而不是口头设计

### 模型与 provider

- 默认沿用当前 OpenAI-compatible 路由
- 不在 L3 设计阶段扩 provider 面
- 保留 `forceModel` 便于后续对比

### 工具定义

1. `expand_keyword(topic_name, primary_keyword) -> list[str]`
   - 作用：补充候选查询词
   - 数据来源：优先复用本仓 `expand` 逻辑
   - 建议上限：最多 1 次

2. `search_history(topic_id, query, top_k) -> list[HistoryDoc]`
   - 作用：检索当前 topic 的历史热点 / event 相关记录
   - 数据来源：共享 Elasticsearch / `hotspot_search`
   - 建议上限：最多 2 次

3. `fetch_doc(doc_id) -> RawDocument`
   - 作用：拉某条 history hit 的完整原文
   - 数据来源：通过已有检索文档或 fetch adapter
   - 建议上限：最多 2 次

4. `score_one(doc, context) -> FollowUpSubScore`
   - 作用：对某条候选材料做局部 follow-up 价值评分
   - 数据来源：小模型 / 当前 LiteLLM 封装
   - 建议上限：最多 2 次

### 预算与步数

本轮把预算定义成**真实运行约束**：

- `request_limit = 6`
- `tool_calls_limit = 6`
- `total_tokens_limit = 2000`

工具级补充限制：

- `expand_keyword <= 1`
- `search_history <= 2`
- `fetch_doc <= 2`
- `score_one <= 2`

实现上：

- 先用 `Pydantic AI` 官方 `UsageLimits` 限总 request / tool / total tokens
- 再在工具层加 per-tool counter
- 超限立即抛出本地受控异常，转成 fallback

### fallback

任一情况都必须回退而不是阻塞产品：

- `UsageLimitExceeded`
- tool 异常
- retrieval / fetch 为空
- 结构化输出失败
- provider timeout / rate limit

fallback 输出语义：

- 不返回 500 给 HotPulse
- 返回结构化建议结果，但标记：
  - `fallbackUsed = true`
  - `fallbackReason`
- 内容退回到最保守建议：
  - follow-up 状态优先 `WATCHING` 或 `LATER`
  - suggested actions 降到 1 条保守动作

## 4.4 `follow-up-hint` contract

在现有 `docs/api/contract.md` 的 V3 段基础上，补充实现侧约束：

响应字段保持：

- `recommendedFollowUpStatus`
- `suggestedActions`
- `confidence`
- `reasoning`
- `model`
- `promptVersion`
- `latencyMs`
- `traceId`

新增可选字段：

- `fallbackUsed`
- `fallbackReason`

原因：

- HotPulse 前端可以决定是否展示“本次建议为回退版本”
- 方便下轮 smoke / trace / debug

## 4.5 fullstack-product 设计

### 后端

新增产品内 endpoint：

- `POST /api/topics/:id/events/:eventId/follow-up-hint`

职责：

1. 鉴权并加载 event detail
2. 判断 eligibility
3. 组织 Brain 请求
4. 返回产品侧 response 给前端

不做：

- 不持久化 suggestion snapshot
- 不自动更新 `follow_up_status`

### 前端

接在现有 `TopicEventsPage` detail 右侧 / 下方卡片区：

- 空态：
  - `当前可获取 AI 下一步建议`
  - CTA：`获取 AI 建议`
- 成功态：
  - 推荐 follow-up status badge
  - 1-3 条 suggested actions
  - reasoning / confidence
  - CTA：`应用建议到跟进表单`
- fallback 态：
  - 明确说明“当前建议为保守回退版本”

“应用建议”行为：

- 带入 `followUpStatus`
- 将 `suggestedActions` 与 `reasoning` 拼成默认备注
- 聚焦到现有 follow-up 编辑区
- 不自动 submit

### overview / work queue

本轮不在 overview 主动请求 L3。

只做最小入口增强：

- 对 eligible event，增加一句轻提示：
  - `可在详情中获取 AI 下一步建议`

## 4.6 观测与评测

### Langfuse

L3 trace 必须记录：

- eligibility input
- tool 调用序列
- usage limits 命中情况
- fallback 原因

### Eval

本轮只设计，不跑 eval。

但 next thread 实现后必须补：

- 50 条 `follow-up-hint` 小评测集
- 三层对比报告里新增：
  - 升 L3 样本占比
  - 平均 tool calls
  - fallback rate

## 5. 下载与预备工作

### 已确认不需要的大下载

- `bge-m3` 已在本地
- `bge-reranker-v2-m3` 已在本地

### 需要的轻量依赖

下个 thread 开工前，建议先保证：

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
uv pip install pydantic-ai
python - <<'PY'
import pydantic_ai
print("pydantic_ai ok")
PY
```

### 运行时环境

如果要让下个 thread 直接进入实现+本地联调，需保证：

`llm-project`

- `OPENAI_API_KEY` 或等价 OpenAI-compatible key
- 如走本地网关：`OPENAI_BASE_URL`
- 如保留 trace：`LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`

`fullstack-product`

- `backend/.env.local` 里已存在本地 infra 配置
- 如要直接联调 L3，需补 Brain URL / enable flags

## 6. 验收标准

实现完成时至少满足：

- 只有 eligible event 才会触发 L3
- `follow-up-hint` 通过单 Agent + 4 工具工作
- 6 步 / 2000 tokens / per-tool 上限是硬约束
- 超预算 / tool 异常时能回退
- event detail 能展示建议卡
- “应用建议”只带入表单，不自动提交
- overview / work queue 没有新增 AI 独立页面

## 7. Next Thread 执行约定

下一个 thread 默认直接执行 implementation plan，不再为普通实现细节反复交互。

只有以下场景才允许再次打断用户：

- 本 spec 里列出的依赖还没准备好
- 本地服务 / 凭据 / env 与当前假设不一致
- 出现真正无法自行绕开的外部阻塞
