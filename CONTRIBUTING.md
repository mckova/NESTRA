# Contributing

Thank you for improving NESTRA. Contributions should preserve its central contract: spend less only when quality and policy still pass.

## Development

```bash
git clone <your-fork>
cd NESTRA
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python scripts/validate_release.py
```

The project intentionally has no runtime dependencies. Discuss a new production dependency before adding it.

## Pull requests

1. Keep production code independent from `benchmarks` and Agent Hive.
2. Add tests for behavior and an adversarial test for security fixes.
3. Preserve backward compatibility or document a semantic-versioning change.
4. Update schemas, OpenAPI, examples, and docs when a public contract changes.
5. Support token/latency/quality claims with reproducible raw results and configuration.
6. Use synthetic data; never commit credentials, private prompts, or production memory.
7. Run `python -m pytest` and `python scripts/validate_release.py`.

## Design rules

- Deterministic checks own trust, sensitivity, path, budget, and stopping policy.
- Retriever score does not imply trust.
- A more capable model does not bypass evidence policy.
- Retrieval-only must report zero provider calls and tokens.
- Failed Micro/Meso guards escalate within budget; failed Full guards fail closed by default.
- Monitoring records metadata, not request or evidence content.

Use the issue forms for bugs and feature proposals. Security reports follow `SECURITY.md`, never the public issue tracker.
