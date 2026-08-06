# Support

Use GitHub Issues for reproducible bugs and scoped feature requests. Include the NESTRA version, Python version, operating system, route, redacted telemetry, and a minimal synthetic fixture.

Before filing, run:

```bash
python -m pytest
python scripts/validate_release.py
nestra route --project YOUR_PROJECT --question "YOUR QUESTION"
```

Do not post API keys, bearer tokens, private prompts, retrieved customer content, production audits, or project snapshots containing private data.

Security vulnerabilities follow `SECURITY.md`. General deployment and architecture consulting is not guaranteed by the volunteer project.
