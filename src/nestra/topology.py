"""Fixed colony roles used as ownership boundaries, not chatty agents."""

from __future__ import annotations

from typing import Any

NESTRA_ROLES = {
    "queen": "goal, route, budget, and stop conditions",
    "scout": "minimum information need",
    "forager": "evidence retrieval and ranking",
    "builder": "candidate answer generation",
    "guard": "evidence and output contracts",
    "caretaker": "memory retention and deletion",
}


def create_fixed_nestra_plan(total_budget: int) -> dict[str, Any]:
    budget = max(1, int(total_budget))
    weights = {
        "queen": 0.05,
        "scout": 0.10,
        "forager": 0.20,
        "builder": 0.45,
        "guard": 0.15,
        "caretaker": 0.05,
    }
    rows = []
    assigned = 0
    for index, (role, weight) in enumerate(weights.items()):
        value = budget - assigned if index == len(weights) - 1 else round(budget * weight)
        assigned += value
        rows.append(
            {"id": role, "role": role, "budget": value, "dependencies": _dependencies(role)}
        )
    plan = {"schemaVersion": 1, "totalBudget": budget, "roles": rows}
    validate_nestra_plan(plan)
    return plan


def validate_nestra_plan(plan: dict[str, Any]) -> bool:
    roles = plan.get("roles") if isinstance(plan, dict) else None
    if not isinstance(roles, list) or {row.get("role") for row in roles} != set(NESTRA_ROLES):
        raise ValueError("NESTRA plan must contain every colony role exactly once.")
    if sum(row.get("budget", 0) for row in roles) != plan.get("totalBudget"):
        raise ValueError("NESTRA role budgets must equal the total budget.")
    return True


def _dependencies(role: str) -> list[str]:
    return {
        "scout": ["queen"],
        "forager": ["scout"],
        "builder": ["forager"],
        "guard": ["builder"],
        "caretaker": ["guard"],
    }.get(role, [])
