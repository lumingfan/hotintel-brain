# L2 Gap Closure Before L3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two confirmed L2 gaps that would destabilize L3: missing embedding enrichment during search reindex, and async judge acceptance semantics drifting from sync judge semantics.

**Architecture:** Keep the scope inside existing L2 seams. Centralize search embedding enrichment at the search indexing layer so live sync and reindex share one path, and centralize Brain accepted-judgement semantics in the intelligence module so sync and async judge reuse one rule gate. Do not introduce any L3 runtime code in this round.

**Tech Stack:** Spring Boot 3, Java 21, Elasticsearch, RabbitMQ, JUnit/WireMock/Testcontainers, FastAPI/Python docs only, Maven, npm, pytest, ruff.

---

## File Structure

- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/search/service/HotspotSearchIndexService.java`
  - Move embedding enrichment into the indexing service so both single upsert and reindex share the same path.
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/search/service/HotspotSearchSyncListener.java`
  - Stop enriching outside the indexing service once the service owns that concern.
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainEmbeddingService.java`
  - Add any minimal helper needed to support shared enrichment behavior without duplicating logic.
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAcceptedJudgementResolver.java`
  - Hold the single source of truth for topic-rule acceptance semantics shared by sync and async Brain judge paths.
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainBackedIntelligenceJudgementService.java`
  - Reuse the shared acceptance resolver instead of private acceptance logic.
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeListener.java`
  - Reuse the shared acceptance resolver before writing `hotspot_item`.
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/test/java/com/lumingfan/hotintel/search/HotspotSearchVectorIntegrationTest.java`
  - Prove reindex keeps embedding fields.
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/test/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeIntegrationTest.java`
  - Prove async judge respects topic rule thresholds and direct-keyword requirements.
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/tasks/T-035-hotintel-brain-l2-rag-and-async-integration.md`
  - Record the specific L2 gap closure work and verification.
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/STATUS.md`
  - Update milestone wording and verification results.
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/STATUS.md`
  - Record that L2 blocker closure completed and L3 remains pending.

## Task 1: Lock In Reindex Embedding Parity

**Files:**
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/test/java/com/lumingfan/hotintel/search/HotspotSearchVectorIntegrationTest.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/search/service/HotspotSearchIndexService.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/search/service/HotspotSearchSyncListener.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainEmbeddingService.java`

- [ ] **Step 1: Write the failing integration test for reindex**

Add a test that:

- seeds a topic and hotspot visible to search reindex
- stubs Brain `/v1/embed`
- triggers the reindex path, not the live listener path
- reads the resulting search document
- asserts `embedding`, `embeddingModel`, and `embeddingDimension` are present after reindex

Test shape:

```java
@Test
void reindex_keeps_embedding_fields_when_brain_embed_is_enabled() {
    stubFor(post(urlEqualTo("/v1/embed"))
            .willReturn(okJson("""
                {
                  "model":"models/bge-m3",
                  "dimension":2,
                  "items":[{"text":"...", "vector":[0.12,0.34]}]
                }
                """)));

    SearchReindexExecutionResult result =
            hotspotSearchIndexService.reindexUserHotspots(userId, topicId, "TEST");

    HotspotSearchDocument indexed = loadIndexedDocument(hotspotId);

    assertThat(result.reindexed()).isEqualTo(1);
    assertThat(indexed.embedding()).containsExactly(0.12f, 0.34f);
    assertThat(indexed.embeddingModel()).isEqualTo("models/bge-m3");
    assertThat(indexed.embeddingDimension()).isEqualTo(2);
}
```

- [ ] **Step 2: Run the new test and confirm RED**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=HotspotSearchVectorIntegrationTest test
```

Expected:

- FAIL because reindex currently bulk-upserts plain `HotspotSearchDocument.from(...)` without embedding enrichment

- [ ] **Step 3: Implement shared enrichment in the indexing layer**

Adjust the indexing service so both `upsert(...)` and reindex/bulk paths enrich documents before writing them.

Implementation shape:

```java
public void upsert(HotspotSearchDocument document) {
    if (!isEnabled()) {
        return;
    }
    ensureIndex();
    indexOne(enrich(document));
}

private void bulkUpsert(List<HotspotSearchDocument> documents) {
    List<HotspotSearchDocument> enriched = documents.stream()
            .map(this::enrich)
            .toList();
    // existing bulk request
}
```

and the sync listener becomes:

```java
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void onHotspotIndexed(SearchIndexSyncRequestedEvent event) {
    hotspotSearchIndexService.upsert(event.document());
}
```

- [ ] **Step 4: Re-run the reindex test and confirm GREEN**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=HotspotSearchVectorIntegrationTest test
```

Expected:

- PASS

- [ ] **Step 5: Run compile to catch wiring regressions**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -DskipTests compile
```

Expected:

- exit code `0`

## Task 2: Lock In Async Judge Acceptance Parity

**Files:**
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/test/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeIntegrationTest.java`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAcceptedJudgementResolver.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainBackedIntelligenceJudgementService.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainAsyncJudgeListener.java`

- [ ] **Step 1: Write failing tests for async topic-rule enforcement**

Add at least two tests:

1. async completed result with `isReal=true` but `relevanceScore` below topic minimum does not create/update accepted hotspot
2. async completed result with `requireDirectKeywordMention=true` and `keywordMentioned=false` does not create/update accepted hotspot

Test shape:

```java
@Test
void async_completed_result_below_min_relevance_is_ignored() {
    BrainAsyncJudgeCompletedMessage message = completedMessage(45, true, true, "high");

    listener.handleCompleted(message);

    assertThat(findHotspot(topicId, rawDocumentId)).isEmpty();
}

@Test
void async_completed_result_missing_direct_keyword_is_ignored_when_rule_requires_it() {
    BrainAsyncJudgeCompletedMessage message = completedMessage(88, true, false, "high");

    listener.handleCompleted(message);

    assertThat(findHotspot(topicId, rawDocumentId)).isEmpty();
}
```

- [ ] **Step 2: Run the new async test class and confirm RED**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=BrainAsyncJudgeIntegrationTest test
```

Expected:

- FAIL because current listener only checks `partial` and `isReal`

- [ ] **Step 3: Introduce the shared acceptance resolver**

Create a resolver that owns:

- min relevance threshold check
- direct keyword requirement check
- normalization into `IntelligenceJudgement`

Implementation shape:

```java
public IntelligenceJudgement resolve(
        TopicRuleEntity rule,
        boolean isReal,
        Integer relevanceScore,
        String reasoning,
        Boolean keywordMentioned,
        String importance,
        String summary) {
    boolean accepted = isReal
            && relevanceScore != null
            && relevanceScore >= minRelevance(rule)
            && (!requireDirectKeywordMention(rule) || Boolean.TRUE.equals(keywordMentioned));
    return new IntelligenceJudgement(
            accepted,
            isReal,
            relevanceScore == null ? 0 : relevanceScore,
            reasoning,
            keywordMentioned,
            normalizeImportance(importance),
            summary);
}
```

- [ ] **Step 4: Switch sync and async flows to the shared resolver**

`BrainBackedIntelligenceJudgementService` should call the resolver after validating the Brain response, and `BrainAsyncJudgeListener` should call the same resolver before any insert/update:

```java
IntelligenceJudgement judgement = acceptedJudgementResolver.resolve(
        aggregate.rule(),
        Boolean.TRUE.equals(message.result().isReal()),
        message.result().relevanceScore(),
        message.result().reasoning(),
        message.result().keywordMentioned(),
        message.result().importance(),
        message.result().summary());

if (!judgement.accepted()) {
    return;
}
```

- [ ] **Step 5: Re-run async acceptance tests and confirm GREEN**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=BrainAsyncJudgeIntegrationTest test
```

Expected:

- PASS

- [ ] **Step 6: Run the existing intelligence and event-path tests**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=IntelligenceBrainStubIntegrationTest,BrainAsyncJudgeIntegrationTest,HotspotSearchVectorIntegrationTest,TopicEventAggregationIntegrationTest,HotspotLoopIntegrationTest test
```

Expected:

- all listed test classes PASS

## Task 3: Sync Docs, Product Smoke, and Final Verification

**Files:**
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/tasks/T-035-hotintel-brain-l2-rag-and-async-integration.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/STATUS.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/STATUS.md`

- [ ] **Step 1: Update task/status docs with the exact gap closures**

Document:

- reindex embedding parity is now closed
- async judge accepted semantics now match sync judge
- which tests/smokes were run
- that L3 is intentionally still pending

- [ ] **Step 2: Run the existing L2 product smoke**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product
BASE_URL=http://127.0.0.1:8080 ./scripts/topic_brain_l2_smoke.sh
```

Expected:

- returns at least one suggested expanded keyword
- exits `0`

- [ ] **Step 3: Re-run repo-level required verification commands**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate && pytest -q
source .venv/bin/activate && ruff check src tests

cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -DskipTests compile

cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend
npm run build
```

Expected:

- all commands exit `0`

- [ ] **Step 4: Do not create a git commit in the shared dirty worktree**

Because `fullstack-product` already contains unrelated in-progress changes, leave this work uncommitted unless the user explicitly asks for commit or PR preparation.

## Self-Review

- Spec coverage:
  - Reindex embedding parity: covered by Task 1
  - Async judge acceptance parity: covered by Task 2
  - Docs/status/smoke/verifications: covered by Task 3
  - No L3 runtime work: respected by all tasks
- Placeholder scan:
  - No `TODO`/`TBD`
  - All commands and target files are explicit
- Type consistency:
  - Shared resolver outputs `IntelligenceJudgement`
  - Sync and async paths both consume the same accepted judgement abstraction

Plan complete and saved to `docs/superpowers/plans/2026-04-30-l2-gap-closure-before-l3.md`. Per the user's latest instruction, proceed with inline execution in this session rather than stopping for an execution choice prompt.
