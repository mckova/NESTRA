"""Hooks and bounded goal/loop control."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable


class HookBus:
    def __init__(
        self, *, clock: Callable[[], datetime] | None = None, max_trace: int = 500
    ) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.max_trace = max(1, max_trace)
        self.handlers: defaultdict[str, list[Callable[[dict[str, Any]], Any]]] = defaultdict(list)
        self.events: list[dict[str, Any]] = []

    def on(self, name: str, handler: Callable[[dict[str, Any]], Any]) -> Callable[[], None]:
        self.handlers[name].append(handler)
        return lambda: self.handlers[name].remove(handler)

    def emit(self, name: str, payload: dict[str, Any] | None = None) -> None:
        event = {
            "name": name,
            "at": self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            **(payload or {}),
        }
        self.events.append(event)
        self.events = self.events[-self.max_trace :]
        for handler in tuple(self.handlers[name]):
            handler(deepcopy(event))

    def trace(self) -> list[dict[str, Any]]:
        return deepcopy(self.events)


class GoalController:
    def __init__(
        self, goal: str, *, max_model_calls: int = 3, max_steps: int = 8, token_budget: int = 2_400
    ) -> None:
        if not str(goal).strip():
            raise ValueError("goal must be non-empty.")
        self.goal = str(goal).strip()
        self.max_model_calls = max(0, int(max_model_calls))
        self.max_steps = max(1, int(max_steps))
        self.token_budget = max(1, int(token_budget))
        self.model_calls = 0
        self.steps = 0
        self.tokens = 0
        self.done = False

    def authorize(self, *, model_call: bool = False, estimated_tokens: int = 0) -> dict[str, Any]:
        reasons = []
        if self.done:
            reasons.append("goal_complete")
        if self.steps >= self.max_steps:
            reasons.append("step_budget_exhausted")
        if model_call and self.model_calls >= self.max_model_calls:
            reasons.append("model_call_budget_exhausted")
        if self.tokens + max(0, estimated_tokens) > self.token_budget:
            reasons.append("token_budget_exhausted")
        return {"allowed": not reasons, "reasons": reasons}

    def record(
        self, *, model_call: bool = False, tokens: int = 0, successful: bool = False
    ) -> dict[str, Any]:
        self.steps += 1
        self.model_calls += int(model_call)
        self.tokens += max(0, int(tokens))
        self.done = self.done or successful
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": self.steps,
            "modelCalls": self.model_calls,
            "tokens": self.tokens,
            "done": self.done,
        }
