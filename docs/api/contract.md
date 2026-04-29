# HotIntel Brain API 契约

最近更新：2026-04-29（对齐已落地 judge/summarize + error mapping）
状态：Draft
适用版本：v1（含 V1/V2/V3/V4 阶段标注）

所有接口默认走 `application/json`，请求 / 响应都是 Pydantic v2 schema 锁定。Brain 内部用 `instructor` 自动处理 LLM 输出 schema 校验与 retry / repair；返回到 HotPulse 时再进一步序列化。

## 通用约定

- Base URL：`http://localhost:8090/v1`（本地）
- 鉴权：V1 不做（信任网络层）；V2 加 `X-Brain-Token` header
- Trace：所有调用返回 `traceId`；在 Langfuse 尚未配置的阶段，该字段允许为 `null`
- 强制层级 / 模型：所有 endpoint 都接受可选 `forceLayer = L1 | L2 | L3` 与 `forceModel`，方便对比测试与降级
- 错误响应：

```json
{
  "code": "SCHEMA_INVALID",
  "message": "Model output failed schema validation after instructor retry",
  "layer": "L1",
  "model": "gpt-4o-mini",
  "promptVersion": "judge-v1.0",
  "traceId": "br_2026..."
}
```

---

## V1 接口

### 1. POST /v1/judge

#### 用途

对单条 `raw_document` 做研判，返回结构化 `JudgementResult`。

#### 请求

```json
{
  "rawDocument": {
    "id": "rd_001",
    "title": "Anthropic releases Claude Sonnet 4.6",
    "content": "Anthropic announced ...",
    "source": "hackernews",
    "publishedAt": "2026-04-17T08:00:00Z",
    "author": "anthropic",
    "url": "https://example.com"
  },
  "topicContext": {
    "topicId": "tp_001",
    "topicName": "AI Coding Models",
    "primaryKeyword": "Claude Sonnet 4.6",
    "expandedKeywords": ["Claude Sonnet", "Claude Code"],
    "rule": {
      "minRelevanceScore": 60,
      "requireDirectKeywordMention": false
    }
  },
  "forceLayer": "L1",
  "forceModel": null
}
```

#### 响应

```json
{
  "rawDocumentId": "rd_001",
  "layer": "L1",
  "model": "gpt-4o-mini",
  "promptVersion": "judge-v1.0",
  "relevanceScore": 92,
  "isReal": true,
  "isRealConfidence": 0.88,
  "importance": "high",
  "summary": "Anthropic 发布 Claude Sonnet 4.6，性能与代价平衡新基线。",
  "keywordMentioned": true,
  "reasoning": "标题与正文直接命中 Claude Sonnet 4.6。",
  "expandedKeywords": ["Claude Sonnet 4.6", "Anthropic Sonnet"],
  "latencyMs": 820,
  "tokenUsage": {
    "promptTokens": 612,
    "completionTokens": 180,
    "totalTokens": 792
  },
  "traceId": "br_2026..."
}
```

#### 错误码

- `400 INVALID_REQUEST` — 请求体不合规
- `400 INVALID_MODEL` — `forceModel` 不在 V1 白名单
- `408 LLM_TIMEOUT` — 模型调用超时
- `429 RATE_LIMITED` — LiteLLM 上游限流
- `503 MODEL_UNAVAILABLE` — 当前模型不可达

降级响应：

```json
{
  "rawDocumentId": "rd_001",
  "layer": "L1",
  "model": "gpt-4o-mini",
  "promptVersion": "judge-v1.0",
  "partial": true,
  "errorCode": "SCHEMA_INVALID",
  "errorMessage": "Output failed schema validation after instructor retry",
  "rawModelOutput": "...",
  "traceId": "br_2026..."
}
```

HotPulse 收到 `partial=true` 后走规则 fallback。

#### 错误码

- `400 INVALID_REQUEST` — 请求体不合规
- `400 INVALID_MODEL` — `forceModel` 不在 V1 白名单
- `408 LLM_TIMEOUT` — 模型调用超时
- `429 RATE_LIMITED` — LiteLLM 上游限流
- `503 MODEL_UNAVAILABLE` — 当前模型不可达
- 200 + `partial=true` — schema 校验失败但已尽力返回

### 2. POST /v1/summarize

#### 用途

为 event detail / topic report / digest 三种场景生成摘要。HotPulse `report` / `digest` 链路与 event detail 页都调用。

#### 请求

```json
{
  "topicId": "tp_001",
  "topicName": "AI Coding Models",
  "hotspots": [
    {
      "id": "hs_001",
      "title": "Anthropic releases Claude Sonnet 4.6",
      "content": "...",
      "source": "hackernews",
      "publishedAt": "2026-04-17T08:00:00Z"
    }
  ],
  "style": "digest",
  "lengthHint": "short",
  "forceModel": null
}
```

`style` 取值：

- `digest` — 用于 digest 订阅的简报口吻
- `report` — 用于 topic report 的复盘口吻
- `event_detail` — 用于 event detail 页的事实摘要口吻

`lengthHint` 取值：`short` (≤ 100 字) / `medium` (≤ 200 字) / `long` (≤ 400 字)。

#### 响应

```json
{
  "summary": "Anthropic 发布 Sonnet 4.6 ...",
  "keyPoints": ["发布时间", "主要更新", "与 4.5 对比"],
  "model": "gpt-4o-mini",
  "promptVersion": "summarize-v1.0",
  "latencyMs": 1100,
  "tokenUsage": {...},
  "traceId": "br_2026..."
}
```

### 3. GET /v1/health

#### 响应

```json
{
  "status": "ok",
  "version": "0.1.0",
  "model": "gpt-4o-mini",
  "modelReachable": true,
  "esReachable": true,
  "langfuseReachable": true,
  "defaultLayer": "L1",
  "supportedModels": [
    "claude-3-5-haiku-latest",
    "claude-3-5-sonnet-latest",
    "gpt-4o",
    "gpt-4o-mini"
  ]
}
```

---

## V2 接口

### 4. POST /v1/judge/batch

#### 用途

批量研判，节省请求开销。

#### 请求

```json
{
  "items": [
    {"rawDocument": {...}, "topicContext": {...}}
  ],
  "forceLayer": "L2",
  "maxConcurrency": 4
}
```

#### 响应

```json
{
  "results": [
    {"rawDocumentId": "rd_001", "result": {...JudgementResult...}}
  ],
  "totalLatencyMs": 4200,
  "successCount": 9,
  "partialCount": 1
}
```

### 5. POST /v1/expand

#### 用途

为 topic 创建 / 调整阶段做关键词扩展。

#### 请求

```json
{
  "topicId": "tp_001",
  "topicName": "AI Coding Models",
  "primaryKeyword": "Claude Sonnet 4.6",
  "limit": 10,
  "forceModel": null
}
```

#### 响应

```json
{
  "expandedKeywords": [
    "Claude Sonnet",
    "Claude Code",
    "Anthropic Sonnet",
    "Claude 4.6"
  ],
  "model": "gpt-4o-mini",
  "promptVersion": "expand-v1.0",
  "latencyMs": 540,
  "traceId": "br_2026..."
}
```

### 6. POST /v1/aggregate-hint

#### 用途

判断新 hotspot 是否与候选 event 是同一事件，HotPulse 用作语义聚合补充层（现有 sha256 hash 仍是快路径）。

#### 请求

```json
{
  "newHotspot": {
    "id": "hs_002",
    "title": "Anthropic 发布 Sonnet 4.6",
    "content": "...",
    "source": "weibo",
    "publishedAt": "2026-04-17T09:00:00Z"
  },
  "candidateEvents": [
    {
      "eventId": "evt_001",
      "canonicalTitle": "Anthropic releases Claude Sonnet 4.6",
      "canonicalSummary": "...",
      "sources": ["hackernews"],
      "firstSeenAt": "2026-04-17T08:00:00Z",
      "lastSeenAt": "2026-04-17T08:30:00Z"
    }
  ],
  "forceModel": null
}
```

#### 响应

```json
{
  "decision": "MERGE_INTO_EXISTING",
  "matchedEventId": "evt_001",
  "confidence": 0.91,
  "reasoning": "标题指向同一发布事件；微博为新来源补充。",
  "alternativeMatches": [],
  "model": "gpt-4o-mini",
  "promptVersion": "aggregate-hint-v1.0",
  "latencyMs": 720,
  "traceId": "br_2026..."
}
```

`decision` 取值：

- `MERGE_INTO_EXISTING` — 与某 candidate 同一事件，`matchedEventId` 必填
- `CREATE_NEW` — 创建新 event
- `UNCERTAIN` — 置信度不足，HotPulse 应回退到 hash 链路

### 7. POST /v1/triage-hint

#### 用途

给一个 event，输出推荐 triage 状态与理由。HotPulse work queue 用作智能预排。

#### 请求

```json
{
  "event": {
    "eventId": "evt_001",
    "topicId": "tp_001",
    "topicName": "AI Coding Models",
    "canonicalTitle": "Claude Sonnet 4.6 发布",
    "canonicalSummary": "...",
    "topImportanceLevel": "high",
    "topRelevanceScore": 91,
    "hotspotCount": 4,
    "sourceCount": 3,
    "firstSeenAt": "2026-04-17T08:00:00Z",
    "lastSeenAt": "2026-04-17T12:00:00Z"
  },
  "forceModel": null
}
```

#### 响应

```json
{
  "recommendedTriageStatus": "CONFIRMED",
  "confidence": 0.82,
  "reasoning": "多来源命中 + 高 importance + 来自官方账号。",
  "alternativeStatuses": [
    {"status": "REVIEWING", "score": 0.14}
  ],
  "model": "gpt-4o-mini",
  "promptVersion": "triage-hint-v1.0",
  "latencyMs": 600,
  "traceId": "br_2026..."
}
```

---

## V3 接口

### 8. POST /v1/follow-up-hint

#### 用途

给 event，输出推荐的 follow-up 状态与下一步动作建议，HotPulse event detail 页用作"AI 建议"卡片。

#### 请求

```json
{
  "event": {
    "eventId": "evt_001",
    "topicId": "tp_001",
    "canonicalTitle": "Claude Sonnet 4.6 发布",
    "canonicalSummary": "...",
    "triageStatus": "CONFIRMED",
    "currentFollowUpStatus": "WATCHING",
    "currentFollowUpNote": "继续观察。",
    "hotspotCount": 4,
    "lastSeenAt": "2026-04-17T12:00:00Z"
  },
  "forceModel": null
}
```

#### 响应

```json
{
  "recommendedFollowUpStatus": "NEEDS_FOLLOW_UP",
  "suggestedActions": [
    "查阅 Anthropic 官方 release notes 确认 4.6 与 4.5 的能力差异",
    "搜索 HackerNews 二次评论判断社区初步反馈"
  ],
  "confidence": 0.74,
  "reasoning": "事件已 confirmed 且来源跨度大，具备进一步归档前的核验价值。",
  "model": "gpt-4o-mini",
  "promptVersion": "follow-up-hint-v1.0",
  "latencyMs": 780,
  "traceId": "br_2026..."
}
```

---

## V4 接口

### 9. GET /v1/feedback/reports

#### 用途

列出历史 feedback eval 报告（每周一份）。

#### 响应

```json
{
  "reports": [
    {
      "id": "fbr_2026_W17",
      "weekOf": "2026-04-20",
      "totalEvents": 124,
      "agreementRate": 0.71,
      "promptSuggestionsCount": 3,
      "generatedAt": "2026-04-27T01:00:00Z"
    }
  ]
}
```

### 10. GET /v1/feedback/reports/:id

#### 用途

单份 feedback report 详情。

#### 响应

```json
{
  "id": "fbr_2026_W17",
  "weekOf": "2026-04-20",
  "totalEvents": 124,
  "agreementRate": 0.71,
  "confusionMatrix": {
    "predictedHigh_userConfirmedHigh": 32,
    "predictedHigh_userDismissed": 8,
    "...": "..."
  },
  "topMisclassificationCases": [
    {
      "eventId": "evt_xxx",
      "predicted": {"importance": "high", "relevanceScore": 85},
      "actual": {"triageStatus": "DISMISSED", "followUpStatus": "RESOLVED"},
      "userNote": "实际上是营销噪音"
    }
  ],
  "promptSuggestions": [
    {
      "promptName": "judge-v1.0",
      "suggestion": "在系统 prompt 中增加'忽略明显商业合作 / 推广文案'的判断准则",
      "supportingCases": ["evt_xxx", "evt_yyy"]
    }
  ],
  "generatedAt": "2026-04-27T01:00:00Z"
}
```

---

## 与 HotPulse 的对接路径

- `POST /v1/judge` + `POST /v1/summarize` 的对接见主仓 `T-034`
- `POST /v1/expand` / `aggregate-hint` / `triage-hint` 的对接见 `T-035`
- `POST /v1/follow-up-hint` 的对接见 `T-036`
- feedback `GET` endpoint 不被 HotPulse 主动调用，主要面向 Brain 仓内自看

任何契约变更必须双写：本仓 + `fullstack-product/docs/api/`。
