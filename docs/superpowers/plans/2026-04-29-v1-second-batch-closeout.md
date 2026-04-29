# V1 Second Batch Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 V1 第二批从“judge 已接通”推进到“L1 服务闭环可演示、可 trace、可开始 baseline eval”的状态。

**Architecture:** 以现有 `judge` 链路为模板，补齐 `summarize` endpoint，并把 prompt 加载、Langfuse tracing、真实 provider smoke 和最小 eval scaffold 串成一条完整的 L1 工作流。优先保持边界清晰：route 负责 HTTP，chain 负责 prompt/render/fallback，LLM client 负责 provider 调用，observability 负责 trace 与 prompt 来源。

**Tech Stack:** FastAPI, Pydantic v2, instructor, LiteLLM, Langfuse, pytest, respx

---

### Task 1: Finish the `summarize` HTTP path

**Files:**
- Create: `tests/test_summarize.py`
- Create: `src/api/routes_summarize.py`
- Create: `src/chains/summarize_singleshot.py`
- Modify: `src/api/main.py`
- Modify: `src/llm/client.py`

- [ ] **Step 1: Write the failing route test**

Add a test mirroring `tests/test_judge.py`:

```python
def test_summarize_returns_503_without_model_credentials(client: TestClient) -> None:
    response = client.post("/v1/summarize", json=_sample_summarize_request())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_UNAVAILABLE"
```

- [ ] **Step 2: Run it to verify RED**

Run: `.venv/bin/pytest tests/test_summarize.py::test_summarize_returns_503_without_model_credentials -q`

Expected: FAIL with `404 Not Found`.

- [ ] **Step 3: Add the success-path test**

Monkeypatch the summarize chain and assert:

```python
assert body["summary"]
assert body["promptVersion"] == "summarize-v1.0"
assert body["partial"] is False  # if partial is added to summarize result
```

- [ ] **Step 4: Implement the minimal route and chain**

Follow the same shape as judge:

```python
@router.post("/summarize", response_model=SummarizeResult)
async def summarize(request: SummarizeRequest) -> SummarizeResult:
    ...
```

Chain requirements:
- read `prompts/summarize_v1.md`
- parse frontmatter version
- render system/user prompt
- call a new `summarize_document(...)` helper in `src/llm/client.py`

- [ ] **Step 5: Verify GREEN**

Run: `.venv/bin/pytest tests/test_summarize.py -q`

Expected: PASS.

### Task 2: Make Langfuse real instead of placeholder

**Files:**
- Create: `tests/test_langfuse_client.py`
- Modify: `src/observability/langfuse_client.py`
- Modify: `src/chains/l1_singleshot.py`
- Modify: `src/chains/summarize_singleshot.py`
- Modify: `src/common/config.py` if extra Langfuse config is needed

- [ ] **Step 1: Write the failing health-ping test**

Use `respx` to fake `GET /api/public/health`:

```python
@respx.mock
def test_langfuse_is_reachable_pings_public_health(monkeypatch: pytest.MonkeyPatch) -> None:
    ...
    assert is_reachable() is True
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/test_langfuse_client.py::test_langfuse_is_reachable_pings_public_health -q`

Expected: FAIL because current implementation only checks key presence.

- [ ] **Step 3: Add prompt-fetch fallback test**

Test the decision order:

```python
prompt = get_prompt("judge", fallback_path="prompts/judge_v1.md")
```

Expected behavior:
- if Langfuse configured and prompt fetch succeeds, use Langfuse prompt
- otherwise fall back to the local markdown file

- [ ] **Step 4: Implement `is_reachable()` and prompt fetch**

Add:
- real HTTP ping to `LANGFUSE_HOST/api/public/health`
- optional `get_prompt(name, version, fallback_path)` helper
- graceful fallback if Langfuse is down or keys are missing

- [ ] **Step 5: Thread trace metadata through chains**

Add a minimal trace wrapper so `judge` and `summarize` can return a real `traceId` when Langfuse is configured, while still working with `traceId=None` when it is not.

- [ ] **Step 6: Verify GREEN**

Run: `.venv/bin/pytest tests/test_langfuse_client.py -q`

Expected: PASS.

### Task 3: Harden upstream behavior with smoke and error-mapping tests

**Files:**
- Create: `tests/test_judge_smoke.py`
- Modify: `src/api/routes_judge.py`
- Modify: `src/api/routes_summarize.py`
- Modify: `src/llm/client.py`

- [ ] **Step 1: Write a timeout mapping test**

Use `respx` or monkeypatch to force an upstream timeout:

```python
def test_judge_maps_upstream_timeout_to_408(...):
    assert response.status_code == 408
    assert response.json()["detail"]["code"] == "LLM_TIMEOUT"
```

- [ ] **Step 2: Write a rate-limit mapping test**

```python
def test_judge_maps_rate_limit_to_429(...):
    assert response.status_code == 429
```

- [ ] **Step 3: Write an invalid-response downgrade test**

This should prove we still return `200 + partial=true` for schema-invalid outputs.

- [ ] **Step 4: Verify RED**

Run: `.venv/bin/pytest tests/test_judge_smoke.py -q`

Expected: FAIL because explicit timeout / rate-limit mapping is not implemented yet.

- [ ] **Step 5: Implement minimal exception translation**

In `src/llm/client.py`, normalize LiteLLM / provider exceptions into small local runtime exceptions such as:

```python
class UpstreamTimeoutError(RuntimeError): ...
class UpstreamRateLimitError(RuntimeError): ...
```

Map them in routes to:
- `408 LLM_TIMEOUT`
- `429 RATE_LIMITED`

- [ ] **Step 6: Verify GREEN**

Run: `.venv/bin/pytest tests/test_judge_smoke.py -q`

Expected: PASS.

### Task 4: Add the first eval bootstrap, but keep it minimal

**Files:**
- Create: `scripts/sample_from_hotpulse.py`
- Create: `eval/__init__.py`
- Create: `eval/harness.py`
- Create: `eval/metrics.py`
- Create: `eval/reports/.gitkeep` if needed
- Create: `tests/test_eval_harness.py`
- Modify: `pyproject.toml` if test discovery or tooling needs a small tweak

- [ ] **Step 1: Write the failing harness smoke test**

The first harness test should not call a real model. It should only verify:
- dataset file can be loaded
- one runner function can iterate samples
- report path can be created

```python
def test_eval_harness_runs_with_mock_runner(tmp_path: Path) -> None:
    ...
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/test_eval_harness.py -q`

Expected: FAIL because `eval/harness.py` does not exist.

- [ ] **Step 3: Implement the smallest useful harness**

Scope:
- accept dataset path
- accept a callable or layer name
- accumulate counts
- emit a markdown report skeleton with metadata + placeholders for metrics

No real DeepEval integration yet; that is a follow-up inside the same milestone only if time remains.

- [ ] **Step 4: Add the HotPulse sampling script shell**

This script can stay as a documented placeholder if main-repo DB access is unavailable, but it must:
- define CLI args
- define expected output schema
- fail clearly when required connection info is absent

- [ ] **Step 5: Verify GREEN**

Run: `.venv/bin/pytest tests/test_eval_harness.py -q`

Expected: PASS.

### Task 5: Reconcile docs and declare the V1 exit target

**Files:**
- Modify: `docs/STATUS.md`
- Modify: `docs/api/contract.md`
- Modify: `docs/runbooks/local-dev.md`
- Modify: `README.md`

- [ ] **Step 1: Update status after each landed slice**

Keep `docs/STATUS.md` as the single source of truth for:
- what is already real
- what still depends on keys or Langfuse
- what still blocks baseline eval

- [ ] **Step 2: Update runbook with exact working local gateway example**

Document the known-good pattern:

```text
OPENAI_BASE_URL=http://localhost:17654/v1
OPENAI_API_KEY=<local gateway key>
BRAIN_DEFAULT_MODEL=gpt-4o-mini
```

- [ ] **Step 3: Update contract docs for real errors**

Document:
- `400 INVALID_MODEL`
- `408 LLM_TIMEOUT`
- `429 RATE_LIMITED`
- `200 + partial=true`

- [ ] **Step 4: Verify the whole repository**

Run:

```bash
.venv/bin/pytest
.venv/bin/ruff check src tests
```

Expected:
- all tests pass
- all lint checks pass

- [ ] **Step 5: Record the repository constraint**

Current workspace is not an initialized git repository, so commit steps remain blocked. Keep conventional-commit suggestions in docs, but do not assume branch-based workflow until the repo is initialized.
