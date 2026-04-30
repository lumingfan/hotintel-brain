# L2 Full Product Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `llm-project` 和 `fullstack-product` 两个仓内完成 L2 的真实产品化集成，接通真实 embedding / reranker、同步 HTTP 与 RabbitMQ 异步两条 Brain 链路，并把能力嵌进现有 topic / event / overview 产品流程。

**Architecture:** 先在 `llm-project` 中补齐 L2 检索栈、HTTP 接口和异步 MQ judge 能力，再在 `fullstack-product` 中按现有 intelligence / search / hotspot / analytics / topic 模块边界接入：`embed` 进入 ES 读模型写链路，`aggregate-hint` 进入 event 聚合边界判断，`triage-hint` 进入 triage 与 work queue，`expand` 进入 topic settings。同步链路保留即时反馈，异步链路承接 scan 主吞吐。

**Tech Stack:** FastAPI, Pydantic v2, instructor, LiteLLM, sentence-transformers, transformers, PyTorch (MPS/CPU), Elasticsearch 8, RabbitMQ, Spring Boot, MyBatis-Plus, React, pytest, JUnit, WireMock

---

## File Structure Map

### `llm-project` new files

- `src/retrieval/__init__.py`
- `src/retrieval/embeddings.py`
- `src/retrieval/es_client.py`
- `src/retrieval/retriever.py`
- `src/retrieval/reranker.py`
- `src/chains/l2_rag.py`
- `src/api/routes_embed.py`
- `src/api/routes_judge_batch.py`
- `src/api/routes_expand.py`
- `src/api/routes_aggregate_hint.py`
- `src/api/routes_triage_hint.py`
- `src/mq/__init__.py`
- `src/mq/messages.py`
- `src/mq/consumer.py`
- `src/mq/publisher.py`
- `prompts/expand_v1.md`
- `prompts/aggregate_hint_v1.md`
- `prompts/triage_hint_v1.md`
- `tests/test_retrieval.py`
- `tests/test_embed.py`
- `tests/test_judge_batch.py`
- `tests/test_expand.py`
- `tests/test_aggregate_hint.py`
- `tests/test_triage_hint.py`
- `tests/test_brain_mq.py`

### `llm-project` modified files

- `pyproject.toml`
- `src/common/config.py`
- `src/common/models.py`
- `src/api/main.py`
- `src/api/routes_judge.py`
- `src/chains/l1_singleshot.py`
- `src/llm/client.py`
- `src/observability/langfuse_client.py`
- `docs/api/contract.md`
- `docs/architecture.md`
- `docs/STATUS.md`
- `docs/runbooks/local-dev.md`

### `fullstack-product` new files

- `docs/tasks/T-035-hotintel-brain-l2-rag-and-async-integration.md`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainEmbedRequest.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainEmbedResponse.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainExpandRequest.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainExpandResponse.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAggregateHintRequest.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAggregateHintResponse.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainTriageHintRequest.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainTriageHintResponse.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeRequestedMessage.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeCompletedMessage.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainEmbeddingService.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/TopicKeywordExpansionService.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/EventAggregationHintService.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/EventTriageHintService.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeDispatchService.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeListener.java`
- `backend/src/test/java/com/lumingfan/hotintel/intelligence/BrainL2ContractIntegrationTest.java`
- `backend/src/test/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeIntegrationTest.java`
- `backend/src/test/java/com/lumingfan/hotintel/search/HotspotSearchVectorIntegrationTest.java`
- `scripts/topic_brain_l2_smoke.sh`
- `scripts/topic_brain_async_scan_smoke.sh`

### `fullstack-product` modified files

- `docs/STATUS.md`
- `docs/api/hot-intel-v1-contract-baseline.md`
- `docs/data-model/hot-intel-core-entities.md`
- `docs/runbooks/topic-analytics-and-event-triage.md`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainClient.java`
- `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainProperties.java`
- `backend/src/main/java/com/lumingfan/hotintel/hotspot/service/TopicScanExecutionService.java`
- `backend/src/main/java/com/lumingfan/hotintel/search/model/HotspotSearchDocument.java`
- `backend/src/main/java/com/lumingfan/hotintel/search/service/HotspotSearchIndexService.java`
- `backend/src/main/java/com/lumingfan/hotintel/search/service/HotspotSearchSyncListener.java`
- `backend/src/main/java/com/lumingfan/hotintel/search/service/SearchIndexSyncRequestedEvent.java`
- `backend/src/main/java/com/lumingfan/hotintel/analytics/service/TopicEventTriageService.java`
- `backend/src/main/java/com/lumingfan/hotintel/analytics/service/OverviewDashboardService.java`
- `backend/src/main/java/com/lumingfan/hotintel/analytics/dto/response/TopicEventDetailResponse.java`
- `backend/src/main/java/com/lumingfan/hotintel/analytics/dto/response/TopicEventListItemResponse.java`
- `backend/src/main/java/com/lumingfan/hotintel/analytics/dto/response/OverviewDashboardResponse.java`
- `backend/src/main/java/com/lumingfan/hotintel/topic/service/TopicService.java`
- `backend/src/main/java/com/lumingfan/hotintel/topic/controller/TopicController.java`
- `backend/src/main/resources/application.yml`
- `frontend/src/pages/TopicSettingsPage.tsx`
- `frontend/src/pages/TopicEventsPage.tsx`
- `frontend/src/pages/OverviewDashboardPage.tsx`
- `frontend/src/services/api.ts`

## Operator Prerequisite

这一轮唯一必须由用户手动完成的交互点是 **真实模型与大依赖下载**。在开始 Task 1 之前，用户需要执行这些命令：

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project

uv venv
source .venv/bin/activate

uv pip install -e ".[dev]"
uv pip install \
  "torch>=2.4" \
  "transformers>=4.46" \
  "sentence-transformers>=3.3" \
  "huggingface_hub>=0.26" \
  "elasticsearch>=8.15" \
  "aio-pika>=9.5"

mkdir -p models

python - <<'PY'
from huggingface_hub import snapshot_download

targets = {
    "BAAI/bge-m3": "models/bge-m3",
    "BAAI/bge-reranker-v2-m3": "models/bge-reranker-v2-m3",
}

for repo_id, local_dir in targets.items():
    path = snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
    )
    print(f"{repo_id} -> {path}")
PY
```

如果用户的本机没有提前起依赖，也需要在 `fullstack-product` 根目录确认：

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product
docker compose up -d mysql redis rabbitmq elasticsearch
```

---

### Task 1: Add L2 runtime foundation to `llm-project`

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/common/config.py`
- Modify: `src/common/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing config/model tests**

Add tests covering:

```python
def test_settings_expose_l2_model_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_EMBED_MODEL_PATH", "models/bge-m3")
    monkeypatch.setenv("BRAIN_RERANK_MODEL_PATH", "models/bge-reranker-v2-m3")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.brain_embed_model_path == "models/bge-m3"
    assert settings.brain_rerank_model_path == "models/bge-reranker-v2-m3"
```

```python
def test_embed_request_accepts_texts_and_topic_hint() -> None:
    request = EmbedRequest(texts=["Claude Code ships"], topicId="tp_001")
    assert request.texts == ["Claude Code ships"]
    assert request.topicId == "tp_001"
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `.venv/bin/pytest tests/test_models.py -q`

Expected: FAIL because the L2 config fields and request/response schemas do not exist.

- [ ] **Step 3: Add minimal L2 settings and schema types**

Implement the smallest useful additions:

```python
class Settings(BaseSettings):
    ...
    brain_embed_model_path: str = Field(default="models/bge-m3")
    brain_rerank_model_path: str = Field(default="models/bge-reranker-v2-m3")
    brain_device: str = Field(default="auto")
    brain_rabbitmq_url: str = Field(default="")
    brain_es_index_name: str = Field(default="hotspot_search")
```

```python
class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    topicId: str | None = None

class EmbedVector(BaseModel):
    text: str
    vector: list[float]

class EmbedResponse(BaseModel):
    model: str
    dimension: int
    items: list[EmbedVector]
    traceId: str | None = None
```

Also add request/response models for:
- `JudgeBatchRequest`
- `JudgeBatchResult`
- `ExpandRequest` / `ExpandResult`
- `AggregateHintRequest` / `AggregateHintResult`
- `TriageHintRequest` / `TriageHintResult`

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/test_models.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/common/config.py src/common/models.py tests/test_models.py
git commit -m "feat: add l2 runtime config and schemas"
```

### Task 2: Build the retrieval stack and make `judge` truly support L2

**Files:**
- Create: `src/retrieval/__init__.py`
- Create: `src/retrieval/embeddings.py`
- Create: `src/retrieval/es_client.py`
- Create: `src/retrieval/retriever.py`
- Create: `src/retrieval/reranker.py`
- Create: `src/chains/l2_rag.py`
- Modify: `src/chains/l1_singleshot.py`
- Modify: `src/api/routes_judge.py`
- Modify: `src/api/main.py` only if shared dependencies are needed
- Test: `tests/test_retrieval.py`
- Test: `tests/test_judge.py`

- [ ] **Step 1: Write the first failing retrieval test**

```python
async def test_retriever_returns_ranked_context_from_hybrid_hits() -> None:
    retriever = HybridRetriever(
        embedding_provider=FakeEmbeddingProvider([[0.1, 0.2]]),
        es_client=FakeEsClient([...]),
        reranker=FakeReranker([0.91, 0.73]),
    )
    result = await retriever.retrieve(
        topic_id="tp_001",
        query_text="Claude Code remote MCP",
        top_k=2,
    )
    assert [item.doc_id for item in result.items] == ["hs_1", "hs_2"]
    assert "Claude Code" in result.context
```

- [ ] **Step 2: Write the L2 judge route RED test**

```python
async def test_judge_l2_uses_rag_chain(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    async def fake_run_l2(request: JudgeRequest) -> JudgementResult:
        return JudgementResult(
            rawDocumentId=request.rawDocument.id,
            layer=JudgementLayer.L2,
            model="gpt-4o-mini",
            promptVersion="judge-v1.0",
            relevanceScore=88,
            isReal=True,
            isRealConfidence=0.8,
            importance=ImportanceLevel.HIGH,
            summary="retrieved context summary",
            keywordMentioned=True,
            reasoning="reranked history confirmed the signal",
        )
    monkeypatch.setattr("src.api.routes_judge.run_judge_l2", fake_run_l2)
    ...
    assert response.json()["layer"] == "L2"
```

- [ ] **Step 3: Run the RED tests**

Run:

```bash
.venv/bin/pytest tests/test_retrieval.py::test_retriever_returns_ranked_context_from_hybrid_hits -q
.venv/bin/pytest tests/test_judge.py::test_judge_l2_uses_rag_chain -q
```

Expected: FAIL because retrieval modules and the L2 dispatch path do not exist.

- [ ] **Step 4: Implement the minimal retrieval modules**

`src/retrieval/embeddings.py`:

```python
class EmbeddingProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...
```

`src/retrieval/retriever.py`:

```python
class HybridRetriever:
    async def retrieve(self, topic_id: str, query_text: str, top_k: int = 5) -> RetrievalResult:
        query_vector = (await self.embedding_provider.embed([query_text]))[0]
        candidates = await self.es_client.hybrid_search(topic_id=topic_id, query_text=query_text, query_vector=query_vector)
        ranked = await self.reranker.rerank(query_text, candidates)
        return format_retrieval_result(ranked[:top_k])
```

`src/chains/l2_rag.py`:

```python
async def run_judge_l2(request: JudgeRequest) -> JudgementResult:
    retrieval = await get_retriever().retrieve(
        topic_id=request.topicContext.topicId,
        query_text=f"{request.rawDocument.title}\n{request.rawDocument.content}",
        top_k=5,
    )
    user_prompt = render_l2_user_prompt(request, retrieval.context)
    ...
```

- [ ] **Step 5: Route L1 vs L2 explicitly**

Update `src/api/routes_judge.py` or chain dispatch so:

```python
layer = request.forceLayer or JudgementLayer(get_settings().brain_default_layer)
if layer == JudgementLayer.L2:
    return await run_judge_l2(request)
return await run_judge(request)
```

- [ ] **Step 6: Verify GREEN**

Run:

```bash
.venv/bin/pytest tests/test_retrieval.py tests/test_judge.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/retrieval src/chains/l2_rag.py src/api/routes_judge.py tests/test_retrieval.py tests/test_judge.py
git commit -m "feat: add l2 retrieval stack and judge dispatch"
```

### Task 3: Add the L2 endpoint family in `llm-project`

**Files:**
- Create: `src/api/routes_embed.py`
- Create: `src/api/routes_judge_batch.py`
- Create: `src/api/routes_expand.py`
- Create: `src/api/routes_aggregate_hint.py`
- Create: `src/api/routes_triage_hint.py`
- Create: `prompts/expand_v1.md`
- Create: `prompts/aggregate_hint_v1.md`
- Create: `prompts/triage_hint_v1.md`
- Modify: `src/api/main.py`
- Modify: `src/llm/client.py`
- Test: `tests/test_embed.py`
- Test: `tests/test_judge_batch.py`
- Test: `tests/test_expand.py`
- Test: `tests/test_aggregate_hint.py`
- Test: `tests/test_triage_hint.py`

- [ ] **Step 1: Write failing endpoint tests**

Examples:

```python
def test_embed_returns_vectors(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr("src.api.routes_embed.embed_texts", AsyncMock(return_value=EmbedResponse(...)))
    response = client.post("/v1/embed", json={"texts": ["Claude Code"], "topicId": "tp_001"})
    assert response.status_code == 200
    assert response.json()["dimension"] > 0
```

```python
def test_expand_returns_suggested_keywords(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    ...
    assert response.json()["expandedKeywords"] == ["Claude CLI", "Anthropic MCP"]
```

```python
def test_aggregate_hint_returns_merge_decision(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    ...
    assert response.json()["decision"] == "MERGE_INTO_EXISTING"
```

- [ ] **Step 2: Run the endpoint RED tests**

Run:

```bash
.venv/bin/pytest tests/test_embed.py tests/test_judge_batch.py tests/test_expand.py tests/test_aggregate_hint.py tests/test_triage_hint.py -q
```

Expected: FAIL with missing routes / missing chain helpers.

- [ ] **Step 3: Implement the endpoint and chain surfaces**

Create minimal routes:

```python
@router.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    return await embed_texts(request)
```

```python
@router.post("/judge/batch", response_model=JudgeBatchResult)
async def judge_batch(request: JudgeBatchRequest) -> JudgeBatchResult:
    ...
```

Implement prompt-driven helpers in `src/llm/client.py`:

```python
async def expand_keywords(...): ...
async def aggregate_hint(...): ...
async def triage_hint(...): ...
```

Each should reuse the existing `instructor.from_litellm(...)` pattern rather than invent a second client abstraction.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/pytest tests/test_embed.py tests/test_judge_batch.py tests/test_expand.py tests/test_aggregate_hint.py tests/test_triage_hint.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api src/llm/client.py prompts tests
git commit -m "feat: add l2 brain endpoints"
```

### Task 4: Add RabbitMQ judge request/complete flow to `llm-project`

**Files:**
- Create: `src/mq/__init__.py`
- Create: `src/mq/messages.py`
- Create: `src/mq/consumer.py`
- Create: `src/mq/publisher.py`
- Test: `tests/test_brain_mq.py`
- Modify: `src/common/config.py`
- Modify: `docs/runbooks/local-dev.md`

- [ ] **Step 1: Write the failing MQ round-trip test**

```python
async def test_brain_consumer_processes_request_and_publishes_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    publisher = FakePublisher()
    consumer = BrainJudgeConsumer(publisher=publisher, judge_runner=fake_judge_runner)
    await consumer.handle(BrainJudgeRequestedMessage(...))
    assert publisher.messages[0].routing_key == "hotintel.judge.completed"
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/test_brain_mq.py -q`

Expected: FAIL because MQ message types and consumer do not exist.

- [ ] **Step 3: Implement the minimal MQ adapter**

```python
class BrainJudgeRequestedMessage(BaseModel):
    jobId: str
    topicId: str
    rawDocument: RawDocument
    topicContext: TopicContext

class BrainJudgeCompletedMessage(BaseModel):
    jobId: str
    topicId: str
    result: JudgementResult
```

```python
class BrainJudgeConsumer:
    async def handle(self, message: BrainJudgeRequestedMessage) -> None:
        result = await run_judge_l2(...)
        await self.publisher.publish_completed(...)
```

Do not start a long-running daemon in tests. Keep the transport adapter injectable and unit-testable.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/test_brain_mq.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mq src/common/config.py tests/test_brain_mq.py docs/runbooks/local-dev.md
git commit -m "feat: add brain mq judge flow"
```

### Task 5: Open `T-035` and update `fullstack-product` docs before backend coding

**Files:**
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/tasks/T-035-hotintel-brain-l2-rag-and-async-integration.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/STATUS.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/api/hot-intel-v1-contract-baseline.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/data-model/hot-intel-core-entities.md`

- [ ] **Step 1: Write the task doc before code**

The new task doc must explicitly scope:

```md
- embed -> search projection
- aggregate-hint -> event aggregation
- triage-hint -> triage + overview work queue
- async judge -> scan pipeline
- topic expand -> topic settings
```

- [ ] **Step 2: Update the data model doc with exact L2 fields**

Add the planned fields verbatim:

```md
- hotspot_search.embedding
- hotspot_item.brain_layer
- hotspot_item.brain_trace_id
- hotspot_item.brain_status
- hotspot_event.recommended_triage_status
- hotspot_event.recommended_triage_confidence
- hotspot_event.recommended_triage_reason
```

- [ ] **Step 3: Verify the doc diff**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product
git diff -- docs/tasks/T-035-hotintel-brain-l2-rag-and-async-integration.md docs/STATUS.md docs/api/hot-intel-v1-contract-baseline.md docs/data-model/hot-intel-core-entities.md
```

Expected: only the new task and the L2 contract/data-model additions are present.

- [ ] **Step 4: Commit**

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product
git add docs/tasks/T-035-hotintel-brain-l2-rag-and-async-integration.md docs/STATUS.md docs/api/hot-intel-v1-contract-baseline.md docs/data-model/hot-intel-core-entities.md
git commit -m "docs: add t-035 brain l2 integration task"
```

### Task 6: Integrate Brain L2 into `fullstack-product` backend

**Files:**
- Create: the new `backend/src/main/java/com/lumingfan/hotintel/intelligence/*` request/response/service classes from the file map
- Modify: `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainClient.java`
- Modify: `backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainProperties.java`
- Modify: `backend/src/main/java/com/lumingfan/hotintel/hotspot/service/TopicScanExecutionService.java`
- Modify: `backend/src/main/java/com/lumingfan/hotintel/search/model/HotspotSearchDocument.java`
- Modify: `backend/src/main/java/com/lumingfan/hotintel/search/service/HotspotSearchIndexService.java`
- Modify: `backend/src/main/java/com/lumingfan/hotintel/search/service/HotspotSearchSyncListener.java`
- Modify: `backend/src/main/java/com/lumingfan/hotintel/search/service/SearchIndexSyncRequestedEvent.java`
- Modify: `backend/src/main/java/com/lumingfan/hotintel/analytics/service/TopicEventTriageService.java`
- Modify: `backend/src/main/java/com/lumingfan/hotintel/analytics/service/OverviewDashboardService.java`
- Modify: `backend/src/main/resources/application.yml`
- Test: `backend/src/test/java/com/lumingfan/hotintel/intelligence/BrainL2ContractIntegrationTest.java`
- Test: `backend/src/test/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeIntegrationTest.java`
- Test: `backend/src/test/java/com/lumingfan/hotintel/search/HotspotSearchVectorIntegrationTest.java`

- [ ] **Step 1: Write the failing backend integration tests**

`BrainL2ContractIntegrationTest` should cover:

```java
@Test
void shouldRequestExpandSuggestionsForTopicSettings() throws Exception { ... }

@Test
void shouldPersistTriageRecommendationWhenBrainResponds() throws Exception { ... }
```

`HotspotSearchVectorIntegrationTest` should cover:

```java
@Test
void shouldUpsertEmbeddingIntoHotspotSearchDocument() throws Exception { ... }
```

`BrainAsyncJudgeIntegrationTest` should cover:

```java
@Test
void shouldPublishJudgeRequestAndApplyCompletedResult() throws Exception { ... }
```

- [ ] **Step 2: Run the RED tests**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=BrainL2ContractIntegrationTest,BrainAsyncJudgeIntegrationTest,HotspotSearchVectorIntegrationTest test
```

Expected: FAIL because the new DTOs, search vector field, and async brain flow do not exist.

- [ ] **Step 3: Extend `BrainClient` with L2 methods**

Add:

```java
public BrainCallResult<BrainEmbedResponse> embed(BrainEmbedRequest request) { ... }
public BrainCallResult<BrainExpandResponse> expand(BrainExpandRequest request) { ... }
public BrainCallResult<BrainAggregateHintResponse> aggregateHint(BrainAggregateHintRequest request) { ... }
public BrainCallResult<BrainTriageHintResponse> triageHint(BrainTriageHintRequest request) { ... }
```

- [ ] **Step 4: Add embedding to search projection**

Update `HotspotSearchDocument`:

```java
public record HotspotSearchDocument(
        ...,
        List<Float> embedding,
        String embeddingModel,
        Integer embeddingDimension) { ... }
```

Update `HotspotSearchIndexService.indexMappings()`:

```java
.properties("embedding", property -> property.denseVector(vector -> vector.dims(1024)))
.properties("embeddingModel", property -> property.keyword(keyword -> keyword))
.properties("embeddingDimension", property -> property.integer(integer -> integer))
```

Use the actual dimension from `BrainEmbedResponse` when building the projection payload.

- [ ] **Step 5: Split sync vs async judge dispatch**

Refactor the scan path so `TopicScanExecutionService` does not hard-code synchronous Brain judge for every document.

Minimal shape:

```java
if (properties.isAsyncJudgeEnabled()) {
    brainAsyncJudgeDispatchService.publishRequested(...);
    persistPendingHotspot(...);
} else {
    IntelligenceJudgement evaluation = intelligenceJudgementService.resolveJudgement(...);
    persistAcceptedHotspot(...);
}
```

The completed-listener should later load the pending hotspot/raw document and apply the returned `JudgementResult`.

- [ ] **Step 6: Add `aggregate-hint` and `triage-hint` product services**

`EventAggregationHintService`:

```java
public AggregateDecision decide(...candidate events...) { ... }
```

`EventTriageHintService`:

```java
public TriageRecommendation recommend(...event summary...) { ... }
```

Wire them into:
- event aggregation boundary logic
- triage service / overview work queue enrichment

- [ ] **Step 7: Verify GREEN**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=BrainL2ContractIntegrationTest,BrainAsyncJudgeIntegrationTest,HotspotSearchVectorIntegrationTest,IntelligenceBrainStubIntegrationTest,TopicEventTriageIntegrationTest,OverviewDashboardIntegrationTest,HotspotSearchIntegrationTest test
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product
git add backend/src/main/java backend/src/main/resources/application.yml backend/src/test/java
git commit -m "feat: integrate brain l2 into backend flows"
```

### Task 7: Add the product-facing frontend entry points

**Files:**
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/pages/TopicSettingsPage.tsx`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/pages/TopicEventsPage.tsx`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/pages/OverviewDashboardPage.tsx`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/services/api.ts`

- [ ] **Step 1: Write the failing API/client tests or at least compile-time expectations**

Add or extend type expectations around:

```ts
export interface TopicExpandSuggestionResponse {
  expandedKeywords: string[];
  model: string;
  promptVersion: string;
}
```

```ts
export interface EventTriageRecommendation {
  recommendedTriageStatus: EventTriageStatus;
  confidence: number;
  reasoning: string;
}
```

If no isolated frontend test harness exists, use type-safe API additions plus page-level smoke expectations in the smoke script task below.

- [ ] **Step 2: Add AI expand entry point to topic settings**

UI shape:

```tsx
<button onClick={handleSuggestExpandedKeywords}>AI 推荐扩展关键词</button>
```

The handler should:
- call the new API
- render suggested terms as selectable chips
- append selected chips into `expandedKeywordsText`

- [ ] **Step 3: Add triage recommendation to event detail and work queue**

Minimal UI block in event detail:

```tsx
{detail?.recommendedTriageStatus ? (
  <section>
    <p>Recommended: {detail.recommendedTriageStatus}</p>
    <p>{detail.recommendedTriageReason}</p>
  </section>
) : null}
```

Minimal UI block in overview work queue:

```tsx
{item.recommendedTriageStatus ? <span>建议：{triageLabel(item.recommendedTriageStatus)}</span> : null}
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product
git add frontend/src/pages frontend/src/services/api.ts
git commit -m "feat: surface brain l2 in product flows"
```

### Task 8: Add the final runbooks, smoke scripts, and verification

**Files:**
- Modify: `docs/STATUS.md`
- Modify: `docs/runbooks/local-dev.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/STATUS.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/runbooks/topic-analytics-and-event-triage.md`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/scripts/topic_brain_l2_smoke.sh`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/scripts/topic_brain_async_scan_smoke.sh`

- [ ] **Step 1: Write the sync smoke script**

The script should prove:

```bash
# topic creation/update
# expand suggestions
# triage recommendation
# report or digest summarize
```

At minimum:

```bash
curl -s "$BASE_URL/api/topics/$TOPIC_ID" ...
curl -s "$BRAIN_URL/v1/expand" ...
```

and assert the response contains non-empty suggested keywords.

- [ ] **Step 2: Write the async smoke script**

The script should prove:

```bash
# trigger topic scan
# poll queue-processed result
# read updated hotspot/event state
```

At minimum:

```bash
POST /api/topics/{id}/scan
sleep / poll
GET /api/topics/{id}/events
```

and assert that at least one returned hotspot or event carries Brain-applied result fields.

- [ ] **Step 3: Run full verification**

Run in `llm-project`:

```bash
.venv/bin/pytest -q
ruff check src tests
```

Run in `fullstack-product/backend`:

```bash
mvn -q test
```

Run in `fullstack-product/frontend`:

```bash
npm run build
```

Run smokes:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product
BASE_URL=http://127.0.0.1:8080 BRAIN_URL=http://127.0.0.1:8090 ./scripts/topic_brain_l2_smoke.sh
BASE_URL=http://127.0.0.1:8080 ./scripts/topic_brain_async_scan_smoke.sh
```

Expected: both smoke scripts print a success line and exit `0`.

- [ ] **Step 4: Commit**

```bash
git add docs scripts
git commit -m "docs: record l2 integration verification"
```

## Self-Review Checklist

- [ ] `llm-project` 与 `fullstack-product` 的职责拆分清楚，没有把 LLM provider 逻辑塞回 Java
- [ ] `judge` 的 L2 路径在测试里真实走到 retrieval / rerank，而不是只改返回 layer
- [ ] 异步 MQ judge 是完整 request/complete 双向，不是单向 publish 后无 consumer
- [ ] 前端改动只落在 topic settings、event detail、overview work queue，不新增 AI 专用页面
- [ ] 所有大下载都只在 Operator Prerequisite 中出现一次，不在执行中途临时新增人工步骤
