"""Access the bundled experimental router artifact."""

from __future__ import annotations

import json
from importlib.resources import files


def load_bundled_router_model() -> dict:
    resource = files(__package__).joinpath("micro-safety-demo.json")
    return json.loads(resource.read_text(encoding="utf-8"))


__all__ = ["load_bundled_router_model"]
