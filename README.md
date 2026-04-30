# HotIntel Brain

HotIntel Brain is the LLM / RAG / agent sidecar for HotPulse. It receives `raw_document` or `event` context from the main product, produces structured intelligence outputs, and degrades safely back to conservative behavior when models, retrieval, or tool chains are unavailable.

Current scope:

- L1 single-shot judgement and summarize
- L2 retrieval-augmented expansion / aggregation / triage hints
- L3 single-agent follow-up hint with strict budgets and fallback

## What This Service Exposes

HTTP endpoints currently implemented:

- `GET /v1/health`
- `POST /v1/judge`
- `POST /v1/judge/batch`
- `POST /v1/summarize`
- `POST /v1/embed`
- `POST /v1/expand`
- `POST /v1/aggregate-hint`
- `POST /v1/triage-hint`
- `POST /v1/follow-up-hint`

The service is designed to be useful in three modes:

1. **Skeleton mode**
   - boot the service
   - run tests
   - hit `/v1/health`
   - no model keys required
2. **Real LLM mode**
   - configure OpenAI-compatible and/or Anthropic credentials
   - exercise real judgement / summarize / hint generation
3. **Full product integration mode**
   - connect Brain to `fullstack-product`
   - reuse HotPulse Elasticsearch and local embedding / reranker models
   - verify L2/L3 behavior from real product pages

## Relationship To HotPulse

```text
HotPulse collector / scan -> raw_document
                          -> HotIntel Brain
                          -> structured judgement / hints
                          -> hotspot_item / hotspot_event / report / follow-up UI
```

Rules of engagement:

- Brain is a sidecar, not a second product
- HotPulse owns the user workflow and fallback semantics
- Brain owns prompts, schemas, retrieval, agent budgets, and structured outputs

## Prerequisites

For actual local use, assume:

- Python `3.11`
- `uv`
- local virtualenv support

Optional but commonly needed:

- model credentials
  - `OPENAI_API_KEY`
  - and/or `ANTHROPIC_API_KEY`
- OpenAI-compatible gateway
  - `OPENAI_BASE_URL=http://localhost:17654/v1`
- Langfuse self-hosted
  - default UI: `http://localhost:3000`
- Elasticsearch reachable from Brain for L2/L3
  - usually the same Elasticsearch started by `fullstack-product/docker compose`
- local embedding / reranker models already available under:
  - `models/bge-m3`
  - `models/bge-reranker-v2-m3`

## Installation

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Then create your local env file:

```bash
cp .env.example .env
```

Template: [.env.example](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/.env.example)

## Configuration

### Core runtime

These are safe defaults for most local sessions:

```dotenv
BRAIN_DEFAULT_MODEL=gpt-4o-mini
BRAIN_DEFAULT_LAYER=L1
BRAIN_LOG_LEVEL=INFO
```

### LLM provider config

At least one provider path should be configured if you want real model calls:

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=
ANTHROPIC_API_KEY=
```

Notes:

- `OPENAI_BASE_URL` is required if you route through an OpenAI-compatible local gateway
- when using a gateway, include the trailing `/v1`
- if no model key is configured:
  - `/v1/health` will show `modelReachable=false`
  - L1/L2 routes that require real model calls will fail clearly
  - L3 follow-up hint can still return structured fallback if the product calls it through the agent path

### Langfuse config

```dotenv
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_PROMPT_FETCH_ENABLED=false
```

Behavior:

- no Langfuse keys: tracing disabled, service still boots
- keys configured: traces appear in Langfuse UI
- prompt fetch is off by default to avoid noisy 404s when no remote prompt exists yet

### Retrieval / L2-L3 config

```dotenv
BRAIN_ES_URL=
BRAIN_ES_USER=
BRAIN_ES_PASS=
```

These are required if you want real L2 / L3 retrieval behavior.

Typical local setup:

- start Elasticsearch from `fullstack-product/docker compose`
- point `BRAIN_ES_URL` to `http://localhost:9200`

## Quick Start

### A. Skeleton mode

Use this when you only want to verify the repo boots and tests pass.

```bash
cd /Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project
source .venv/bin/activate
pytest -q
uvicorn src.api.main:app --host 127.0.0.1 --port 8090 --reload
curl -s http://127.0.0.1:8090/v1/health | jq
```

Expected:

- service boots
- `/v1/health` returns `status=degraded`
- `modelReachable=false` without model credentials

### B. Real LLM mode

Use this when you want to exercise actual model-backed routes.

1. fill `.env` with at least one provider
2. optionally start Langfuse
3. start the service
4. call real endpoints

Example:

```bash
curl -s http://127.0.0.1:8090/v1/judge \
  -H 'Content-Type: application/json' \
  -d @judge-sample.json | jq

curl -s http://127.0.0.1:8090/v1/summarize \
  -H 'Content-Type: application/json' \
  -d @summarize-sample.json | jq
```

### C. Full product integration mode

Use this when you want to validate Brain through real HotPulse flows.

1. start infrastructure in `fullstack-product`
2. make sure Elasticsearch is reachable
3. make sure local embedding / reranker models exist
4. start Brain on `8090`
5. start `fullstack-product` backend with:

```dotenv
HOTINTEL_BRAIN_ENABLED=true
HOTINTEL_BRAIN_URL=http://127.0.0.1:8090
HOTINTEL_BRAIN_FOLLOW_UP_HINT_ENABLED=true
```

6. open the product and verify:
   - L1/L2 paths from scan / summarize
   - L3 follow-up suggestion inside event detail

## Verification

### Automated verification

```bash
source .venv/bin/activate
pytest -q
ruff check src tests
```

### Health check

```bash
curl -s http://127.0.0.1:8090/v1/health | jq
```

Interpretation:

- `status=degraded`
  - service is up, but model / ES / Langfuse may be unavailable
- `status=ok`
  - the configured dependencies are reachable

### Manual verification

If you want the manual product-side path, use:

- [fullstack-product manual verification runbook](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product/docs/runbooks/project-manual-verification-and-demo.md)

If you want the Brain-side local development details, use:

- [docs/runbooks/local-dev.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/runbooks/local-dev.md)

## Project Status

Current headline:

- L1 / L2 / L3 code paths are implemented
- HotPulse product integration is already wired
- local sessions without model credentials are expected to rely on graceful fallback for AI-specific behavior

For the authoritative status log, use [docs/STATUS.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/STATUS.md).

## Where To Read Next

- Docs index: [docs/INDEX.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/INDEX.md)
- API contract: [docs/api/contract.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/api/contract.md)
- Local dev runbook: [docs/runbooks/local-dev.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/runbooks/local-dev.md)
- Architecture: [docs/architecture.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/architecture.md)
- ADRs: [docs/adr/0003-structured-output-and-agent-framework.md](/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/llm-project/docs/adr/0003-structured-output-and-agent-framework.md)
