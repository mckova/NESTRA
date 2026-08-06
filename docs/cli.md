# CLI

The package installs the `nestra` command.

```bash
python -m pip install -e .
```

```text
nestra ingest --project ID --file documents.json [--trust trusted|untrusted]
nestra route --project ID --question "..." [--mode auto|retrieval] [--router-model model.json]
nestra query --project ID --question "..." [--mode auto|retrieval] [--router-model model.json]
nestra inspect --project ID
nestra list
nestra serve [--host HOST] [--port PORT] [--router-model model.json]
```

All object results are JSON, making the CLI suitable for shell pipelines and CI fixtures.

Without installation, the equivalent entry point is `python -m nestra` when `src` is on `PYTHONPATH`.

## State

The default state directory is `.nestra` in the current directory. Override it with `--store PATH` or `NESTRA_STORE_DIR`. Projects are stored as versioned JSON snapshots under `projects/`; audit metadata is appended to `audit.jsonl`.

## Credentials

`query` needs `OPENAI_API_KEY` or `OPENAI_KEY` only when the planned route requires a model. Blocked and Retrieval-only requests work without a provider key. `serve` requires `NESTRA_API_TOKEN`; unauthenticated mode is available only with `--allow-unauthenticated` on a loopback host.

## Trust

Documents without trust metadata compile as untrusted. For a local, reviewed fixture, `--trust trusted` fills missing document trust values. Do not use that flag for arbitrary uploads or external search results.

## Learned routing

`--router-model` opts into a validated local model artifact. The committed demo is experimental; it is not loaded automatically. `route` shows the deterministic route, selected route, model ID, probability, thresholds, and any deterministic veto without making a provider call.
