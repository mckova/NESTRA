# NESTRA repository guidance

- This is a Python 3.10+ project. Production code belongs under `src/nestra`; tests belong under `tests`.
- Keep NESTRA independent from Agent Hive: no imports across project directories.
- Use NESTRA terminology for runtime roles and benchmark arms.
- Shared ideas require a local implementation, contract, and provenance note.
- Treat the 50–100 token path as research-only until a disjoint non-inferiority evaluation passes.
- Keep memory trust, visibility, decay, deletion, audit redaction, and tool allow-lists deterministic.
- Run `python -m pytest` and `python scripts/validate_release.py` before handing off changes.
