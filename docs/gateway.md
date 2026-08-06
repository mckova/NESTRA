# HTTP gateway and deployment

Start a local authenticated gateway:

```bash
NESTRA_API_TOKEN="long-random-value" OPENAI_API_KEY="..." nestra serve
```

The default address is `127.0.0.1:8787`. `/health` is public; every `/v1/*` endpoint requires `Authorization: Bearer …`. The full contract is in `openapi/nestra.openapi.yaml`.

## Endpoint summary

- `POST /v1/projects/{projectId}/ingest` compiles and persists documents.
- `POST /v1/route` returns a plan with no model call.
- `POST /v1/query` executes Retrieval, Micro, Meso, Full, or Blocked.
- `GET /v1/projects` and `GET /v1/projects/{projectId}` inspect stored state.
- `GET /v1/metrics` exposes aggregate process metrics without prompts.

## Docker Compose

```bash
cp .env.example .env
# Fill NESTRA_API_TOKEN and optionally OPENAI_API_KEY.
docker compose up --build
```

The Python container runs as an unprivileged user with a read-only root filesystem, dedicated data volume, `/tmp` tmpfs, bytecode writes disabled, and `no-new-privileges`.

## Production checklist

- Give each tenant a separate store or implement a tenant-aware store adapter.
- Terminate TLS and authenticate end users outside the reference bearer boundary.
- Load keys from a secret manager; never bake them into an image.
- Restrict outbound network access to approved provider and retrieval endpoints.
- Export audits to append-only storage and metrics to the platform monitor.
- Set rate, concurrency, latency, token, trust, and sensitivity thresholds for the workload.
- Back up project snapshots and test restore.
- Run representative accuracy, latency, token, and adversarial evaluations before changing routes or models.
- Keep learned-router artifacts opt-in, reviewed, versioned, and monitored.
