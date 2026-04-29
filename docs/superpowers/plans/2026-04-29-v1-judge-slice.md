# V1 Judge Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对齐当前文档事实来源，并落地 V1 第二批里最小可验证的 `POST /v1/judge` 链路骨架。

**Architecture:** 先把 README / roadmap / runbook / workflow 中与 accepted spec 不一致的内容修正到同一口径，再新增 `routes_judge -> chains/l1_singleshot -> llm/client` 的单向调用链。链路保持薄封装：route 只做 HTTP 映射，chain 只做 prompt/render/error downgrade，LLM client 只负责 `instructor + LiteLLM` 调用与 provider 校验。

**Tech Stack:** FastAPI, Pydantic v2, instructor, LiteLLM, pytest, respx

---

### Task 1: Align project docs with accepted direction

**Files:**
- Modify: `README.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/runbooks/local-dev.md`
- Modify: `docs/WORKFLOW.md`
- Modify: `docs/specs/three-layer-capability.md`

- [ ] **Step 1: Update README to match current delivery reality**

Edit the README so it says V1 defaults to sync HTTP, references ADR `0001 ~ 0006`, and describes the current repository layout as already present rather than “planned later”.

- [ ] **Step 2: Update roadmap V1 model scope**

Edit `docs/roadmap.md` so V1 model scope matches ADR 0006: GPT + Claude only, with domestic-model comparison deferred to V2.

- [ ] **Step 3: Update local-dev runbook**

Replace placeholder commands and stale env var names with the current `.env.example` names:

```text
BRAIN_DEFAULT_MODEL
OPENAI_API_KEY
ANTHROPIC_API_KEY
LANGFUSE_HOST
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
```

Also make the health-check expectation explicit:

```text
No keys configured -> degraded
Keys + Langfuse configured -> ok
```

- [ ] **Step 4: Update workflow/spec prompt naming rules**

Make docs distinguish prompt file path from prompt version:

```text
file: prompts/judge_v1.md
frontmatter version: judge-v1.0
```

- [ ] **Step 5: Verify doc references**

Run: `rg -n 'BRAIN_MODEL|BRAIN_API_KEY|prompts/<task>-<version>|prompts/judge-v1\.0\.md' README.md docs`

Expected: no stale references remain.

### Task 2: Add the first failing judge endpoint tests

**Files:**
- Create: `tests/test_judge.py`
- Test: `tests/test_judge.py`

- [ ] **Step 1: Write the failing route-availability test**

Add a test posting a valid `JudgeRequest` payload to `/v1/judge` and expecting `503 MODEL_UNAVAILABLE` when no provider credentials are configured.

```python
def test_judge_returns_503_without_model_credentials(client: TestClient) -> None:
    response = client.post("/v1/judge", json=_sample_judge_request())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_UNAVAILABLE"
```

- [ ] **Step 2: Run the focused test to verify RED**

Run: `.venv/bin/pytest tests/test_judge.py::test_judge_returns_503_without_model_credentials -q`

Expected: FAIL because `/v1/judge` does not exist yet (404 / router missing).

- [ ] **Step 3: Add the success-path test**

Add a second test that monkeypatches the judge chain to return a successful `JudgementResult`, then asserts the HTTP response shape.

```python
def test_judge_returns_chain_result(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    async def fake_run_judge(request: JudgeRequest) -> JudgementResult:
        ...
```

- [ ] **Step 4: Run the success-path test to verify RED**

Run: `.venv/bin/pytest tests/test_judge.py::test_judge_returns_chain_result -q`

Expected: FAIL because the route or patch target does not exist yet.

### Task 3: Implement the judge route and wire it into FastAPI

**Files:**
- Create: `src/api/routes_judge.py`
- Modify: `src/api/main.py`
- Test: `tests/test_judge.py`

- [ ] **Step 1: Write the minimal route**

Create an async route that:

```python
@router.post("/judge", response_model=JudgementResult)
async def judge(request: JudgeRequest) -> JudgementResult:
    ...
```

Behavior:
- call `run_judge(request)`
- translate `UnsupportedModelError` to `400 INVALID_MODEL`
- translate model-unavailable errors to `503 MODEL_UNAVAILABLE`
- otherwise return the `JudgementResult`

- [ ] **Step 2: Register the router**

Add `judge_router` to `src/api/main.py` with prefix `/v1`.

- [ ] **Step 3: Run the focused route tests**

Run: `.venv/bin/pytest tests/test_judge.py -q`

Expected: first test passes or moves to the next missing dependency; second test still fails if chain implementation is incomplete.

### Task 4: Add failing chain tests for success and downgrade behavior

**Files:**
- Create: `src/chains/__init__.py`
- Create: `src/chains/l1_singleshot.py`
- Modify: `tests/test_judge.py`
- Test: `tests/test_judge.py`

- [ ] **Step 1: Add a chain success test**

Write a test that monkeypatches the LLM client layer to return a `JudgementOutput`, then asserts the chain wraps it into `JudgementResult.from_output(...)`.

- [ ] **Step 2: Add a chain downgrade test**

Write a test that monkeypatches the LLM client layer to raise a schema-validation-style error, then asserts the chain returns `partial=True` with `errorCode="SCHEMA_INVALID"`.

- [ ] **Step 3: Run the chain tests to verify RED**

Run: `.venv/bin/pytest tests/test_judge.py -q`

Expected: FAIL because chain helpers and LLM client entrypoints are not implemented yet.

### Task 5: Implement the minimal L1 judge chain and LLM entrypoint

**Files:**
- Modify: `src/llm/client.py`
- Create: `src/chains/l1_singleshot.py`
- Modify: `src/observability/langfuse_client.py`
- Test: `tests/test_judge.py`

- [ ] **Step 1: Add explicit runtime errors in `src/llm/client.py`**

Implement small typed exceptions for:

```python
class ModelUnavailableError(RuntimeError): ...
class StructuredOutputError(RuntimeError): ...
```

And add an async `judge(...)` function that:
- resolves the model
- checks the relevant API key
- builds `AsyncInstructor` via `instructor.from_litellm(acompletion)`
- calls `create_with_completion(...)`
- maps completion usage into `TokenUsage`

- [ ] **Step 2: Add prompt loading + render in the chain**

Read `prompts/judge_v1.md`, extract the version from frontmatter, compose system/user messages, and call `src.llm.client.judge(...)`.

- [ ] **Step 3: Add downgrade handling**

If the LLM client raises `StructuredOutputError`, return:

```python
JudgementResult.downgrade(
    rawDocumentId=request.rawDocument.id,
    layer=JudgementLayer.L1,
    model=model_name,
    promptVersion=prompt_version,
    errorCode="SCHEMA_INVALID",
    errorMessage=...,
)
```

- [ ] **Step 4: Keep Langfuse optional**

Do not block the chain on Langfuse. If tracing is not configured, `traceId` may remain `None`.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/pytest tests/test_judge.py -q`

Expected: PASS.

### Task 6: Re-verify the project and update status docs

**Files:**
- Modify: `docs/STATUS.md`
- Modify: `docs/api/contract.md`
- Test: `tests/test_judge.py`
- Test: `tests/test_health.py`
- Test: `tests/test_llm_client.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Update STATUS**

Record that V1 第二批已启动，并明确这次已落地的切片是 `/v1/judge` route + L1 chain skeleton + TDD tests.

- [ ] **Step 2: Align API contract**

Document the implemented `/v1/judge` behavior and the current `GET /v1/health` fields, including `supportedModels`.

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/pytest`

Expected: all tests pass.

- [ ] **Step 4: Record repository limitation**

Because the current workspace is not an initialized git repository, skip commit steps and note that no branch/worktree workflow could be used in this session.
