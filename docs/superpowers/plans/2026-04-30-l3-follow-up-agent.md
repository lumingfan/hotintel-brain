# L3 Follow-Up Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the L3 single-agent follow-up intelligence flow in `llm-project` and connect it to `fullstack-product` event detail without further design churn.

**Architecture:** Keep L3 narrowly scoped: Brain owns the single-agent orchestration and `follow-up-hint` API, while HotPulse owns eligibility gating, product endpoint adaptation, and the “apply suggestion to existing form” UX. No multi-agent flow, no separate AI page, no persistence cache in this round.

**Tech Stack:** Python 3.11, FastAPI, Pydantic AI, LiteLLM/OpenAI-compatible model routing, Langfuse, Spring Boot 3, React/Vite, pytest, Maven, npm.

---

## Preflight

- [ ] **Step 1: Ensure `pydantic-ai` is available in the local Brain venv**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
uv pip install pydantic-ai
python - <<'PY'
import pydantic_ai
print("pydantic_ai ok")
PY
```

Expected:

- last line prints `pydantic_ai ok`

- [ ] **Step 2: Verify local runtime assumptions before coding**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
test -d models/bge-m3 && echo "embed model ready"
test -d models/bge-reranker-v2-m3 && echo "reranker ready"
```

Expected:

- both lines print

## File Structure

- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/chains/l3_agent.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/api/routes_follow_up_hint.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/tools/expand_keyword.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/tools/search_history.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/tools/fetch_doc.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/tools/score_one.py`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/common/models.py`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/api/main.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/prompts/follow_up_hint_v1.md`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/tests/test_follow_up_hint.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/tests/test_l3_agent.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/test/java/com/lumingfan/hotintel/intelligence/BrainFollowUpHintIntegrationTest.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainClient.java`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainFollowUpHintRequest.java`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainFollowUpHintResponse.java`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/EventFollowUpHintService.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/topic/controller/TopicController.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/analytics/dto/response/TopicEventDetailResponse.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/services/api.ts`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/pages/TopicEventsPage.tsx`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/pages/OverviewDashboardPage.tsx`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/api/contract.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/api/hot-intel-v1-contract-baseline.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/tasks/T-036-hotintel-brain-l3-follow-up-agent-integration.md`

## Task 1: Add Brain Follow-Up Hint Contract and Failing Tests

**Files:**
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/common/models.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/tests/test_follow_up_hint.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/prompts/follow_up_hint_v1.md`

- [ ] **Step 1: Write failing API-level tests for `POST /v1/follow-up-hint`**

Cover:

- success response shape
- fallback response shape
- `suggestedActions` capped at 3

- [ ] **Step 2: Run the new follow-up tests and verify RED**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
pytest tests/test_follow_up_hint.py -q
```

Expected:

- FAIL because route/model does not exist yet

- [ ] **Step 3: Add follow-up request/result models and prompt skeleton**

Define:

- request payload based on event summary
- result payload with:
  - `recommendedFollowUpStatus`
  - `suggestedActions`
  - `confidence`
  - `reasoning`
  - `model`
  - `promptVersion`
  - `latencyMs`
  - `traceId`
  - `fallbackUsed`
  - `fallbackReason`

- [ ] **Step 4: Re-run the API-level tests**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
pytest tests/test_follow_up_hint.py -q
```

Expected:

- still FAIL, but now on missing route/chain implementation rather than missing schema

## Task 2: Build the L3 Agent and Tool Limits

**Files:**
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/chains/l3_agent.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/tools/expand_keyword.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/tools/search_history.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/tools/fetch_doc.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/tools/score_one.py`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/tests/test_l3_agent.py`

- [ ] **Step 1: Write failing unit tests for L3 limits and fallback**

Cover:

- `UsageLimits(request_limit=6, tool_calls_limit=6, total_tokens_limit=2000)` is enforced
- per-tool caps are enforced
- exceptions return fallback result, not crash

- [ ] **Step 2: Run the agent tests and verify RED**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
pytest tests/test_l3_agent.py -q
```

Expected:

- FAIL on missing agent/tools

- [ ] **Step 3: Implement the single-agent follow-up chain**

Requirements:

- single Pydantic AI agent
- 4 tools only
- total request/tool/token limits
- fallback result on `UsageLimitExceeded` or tool failure

- [ ] **Step 4: Re-run agent tests**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
pytest tests/test_l3_agent.py -q
```

Expected:

- PASS

## Task 3: Expose Brain `follow-up-hint` Route and Verify Brain Repo

**Files:**
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/api/routes_follow_up_hint.py`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/src/api/main.py`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/api/contract.md`

- [ ] **Step 1: Wire route to `run_follow_up_hint(...)`**

- [ ] **Step 2: Re-run follow-up route tests**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
pytest tests/test_follow_up_hint.py tests/test_l3_agent.py -q
```

Expected:

- PASS

- [ ] **Step 3: Run full Brain verification**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
pytest -q
source .venv/bin/activate
ruff check src tests
```

Expected:

- both commands exit `0`

## Task 4: Connect HotPulse Backend Eligibility and Product Endpoint

**Files:**
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainFollowUpHintRequest.java`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainFollowUpHintResponse.java`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/EventFollowUpHintService.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/intelligence/BrainClient.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/topic/controller/TopicController.java`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/main/java/com/lumingfan/hotintel/analytics/dto/response/TopicEventDetailResponse.java`
- Create: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend/src/test/java/com/lumingfan/hotintel/intelligence/BrainFollowUpHintIntegrationTest.java`

- [ ] **Step 1: Write failing backend integration tests**

Cover:

- eligible event can call product endpoint and get suggestion
- ineligible event returns explicit “not eligible” response or empty suggestion
- fallback from Brain is surfaced without 500

- [ ] **Step 2: Run backend integration test and verify RED**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=BrainFollowUpHintIntegrationTest test
```

Expected:

- FAIL because endpoint/service/DTOs do not exist yet

- [ ] **Step 3: Implement eligibility gate and Brain client method**

Use:

- `triageStatus in (NEW, REVIEWING)`
- and one of:
  - `topRelevanceScore` in `[40, 65]`
  - `recommendedTriageConfidence < 0.75`
  - `sourceCount <= 2 && followUpStatus == NONE`

- [ ] **Step 4: Re-run backend L3 integration test**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -Dtest=BrainFollowUpHintIntegrationTest test
```

Expected:

- PASS

## Task 5: Connect Event Detail UI and Apply-to-Form UX

**Files:**
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/services/api.ts`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/pages/TopicEventsPage.tsx`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend/src/pages/OverviewDashboardPage.tsx`

- [ ] **Step 1: Add frontend API client types and method**

- [ ] **Step 2: Render AI suggestion card in event detail**

States:

- not eligible
- eligible but idle
- loading
- success
- fallback

- [ ] **Step 3: Implement “apply suggestion” behavior**

Rules:

- set `followUpStatus`
- compose a default note from `suggestedActions` + `reasoning`
- do not auto-submit

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/frontend
npm run build
```

Expected:

- exit `0`

## Task 6: Final Product Verification and Docs

**Files:**
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/api/hot-intel-v1-contract-baseline.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/tasks/T-036-hotintel-brain-l3-follow-up-agent-integration.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/STATUS.md`
- Modify: `/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/STATUS.md`

- [ ] **Step 1: Update docs to reflect final L3 contract**

- [ ] **Step 2: Run final backend verification**

Run:

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/backend
mvn -q -DskipTests compile
mvn -q -Dtest=BrainFollowUpHintIntegrationTest,BrainAsyncJudgeIntegrationTest,HotspotSearchVectorIntegrationTest,IntelligenceBrainStubIntegrationTest test
```

Expected:

- both commands exit `0`

- [ ] **Step 3: Run normal product-path smoke**

Suggested flow:

1. overview or events list -> open eligible event detail
2. click `获取 AI 建议`
3. verify AI suggestion card renders
4. click `应用建议到跟进表单`
5. verify form is populated but not submitted
6. submit through existing follow-up endpoint

- [ ] **Step 4: Record any residual risk explicitly**

If any pre-existing unstable integration test still fails, record it as residual rather than silently omitting it.
