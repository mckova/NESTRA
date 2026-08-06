from __future__ import annotations

from datetime import datetime, timedelta, timezone

from nestra import (
    GoalController,
    ScopedMemory,
    create_fixed_nestra_plan,
    retention_score,
    validate_nestra_plan,
)


def test_memory_scope_visibility_and_trust_do_not_cross():
    memory = ScopedMemory()
    memory.write(
        scope="project",
        namespace="alpha",
        content="trusted",
        trust="trusted",
        visibility=["builder"],
    )
    memory.write(scope="project", namespace="beta", content="other", trust="trusted")
    memory.write(scope="project", namespace="alpha", content="unsafe", trust="untrusted")
    rows = memory.query(scope="project", namespace="alpha", role="builder", trusted_only=True)
    assert [row["content"] for row in rows] == ["trusted"]
    assert memory.query(scope="project", namespace="alpha", role="guard", trusted_only=True) == []


def test_decay_reinforcement_and_scope_deletion():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    memory = ScopedMemory(clock=lambda: created)
    row = memory.write(
        scope="session", namespace="s1", content="short", trust="trusted", ttlMs=1_000
    )
    before = memory.reinforce(row["id"], verified=False, successful=True)
    assert before["reuseCount"] == 0
    assert memory.decay(now=created + timedelta(seconds=2))["deleted"] == 1
    memory.write(scope="session", namespace="s2", content="delete", trust="trusted")
    assert memory.delete_scope(scope="session", namespace="s2") == 1


def test_memory_default_ttl_and_explicit_permanent_record():
    memory = ScopedMemory()
    default = memory.write(scope="project", namespace="alpha", content="expires")
    permanent = memory.write(scope="project", namespace="alpha", content="kept", ttlMs=None)
    assert default["ttlMs"] == 86_400_000
    assert permanent["ttlMs"] is None


def test_retention_and_goal_controller_are_bounded():
    now = datetime.now(timezone.utc)
    assert (
        0
        <= retention_score(
            {
                "createdAt": now.isoformat(),
                "lastUsedAt": now.isoformat(),
                "halfLifeMs": 1000,
                "confidence": 1,
                "relevance": 1,
                "sourceQuality": 1,
                "verifiedUtility": 1,
                "reuseCount": 0,
                "sensitivity": 0,
            },
            now,
        )
        <= 1
    )
    goal = GoalController("answer", max_model_calls=1, max_steps=2, token_budget=100)
    assert goal.authorize(model_call=True, estimated_tokens=50)["allowed"]
    goal.record(model_call=True, tokens=50)
    assert not goal.authorize(model_call=True)["allowed"]
    goal.record(successful=True)
    assert not goal.authorize()["allowed"]


def test_topology_has_every_role_and_exact_budget():
    plan = create_fixed_nestra_plan(100)
    assert validate_nestra_plan(plan)
    assert sum(row["budget"] for row in plan["roles"]) == 100
