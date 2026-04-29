# Langfuse self-hosted

Local self-hosted Langfuse stack for HotIntel Brain trace + prompt observability.
Status: scaffolded; not yet activated.

## Prerequisites

- Docker + Docker Compose
- ~1 GB free RAM
- Ports `3000` (UI) free; ensure no collision with HotPulse compose

## First-time setup

1. Generate secrets locally and write them into `compose.yaml`:

```bash
# pick three random hex strings
openssl rand -hex 32   # → NEXTAUTH_SECRET
openssl rand -hex 32   # → SALT
openssl rand -hex 32   # → ENCRYPTION_KEY (must be exactly 64 hex chars)
```

2. Replace the three `REPLACE_WITH_*` placeholders in `compose.yaml` with the
   generated values. Do **not** commit real secrets.

3. Bring the stack up:

```bash
docker compose -f infra/langfuse/compose.yaml up -d
```

4. Open `http://localhost:3000`, register the first admin account, create a
   project (e.g. `hotintel-brain-dev`), then copy that project's
   `Public key` and `Secret key`.

5. Write those keys into the parent `.env`:

```
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

## Health check

```bash
curl -s http://localhost:3000/api/public/health
```

Expected: `200 OK` with `{"status": "ok"}` body.

## Tear down

```bash
docker compose -f infra/langfuse/compose.yaml down
# add -v to also drop volumes (loses all traces)
docker compose -f infra/langfuse/compose.yaml down -v
```

## Upstream reference

- Langfuse self-hosting docs: https://langfuse.com/self-hosting/docker-compose
- Pin `langfuse/langfuse:3` and `langfuse/langfuse-worker:3` to a specific minor
  version before relying on this in serious work.
