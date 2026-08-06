"""Live Python oracle comparing Direct, RAG, NESTRA, Adaptive, and Micro routes.

This command requires network access and an OpenAI API key. Historical result JSON
is retained in ``benchmarks/nestra-oracle/results`` and is never rewritten implicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmarks.nestra_oracle.lib import (  # noqa: E402
    aggregate_methods,
    answer_metrics,
    bm25_rank,
    enforce_answer_contract,
)
from nestra import (  # noqa: E402
    compile_atomic_evidence,
    compile_project_memory,
    evaluate_accuracy_lock,
    evaluate_pre_call_gate,
    ground_answer_span,
    micro_prompt,
)
from nestra.providers import OpenAIResponsesProvider  # noqa: E402

METHODS = (
    "directGpt56",
    "ragGpt56",
    "fixedNestra",
    "adaptiveMemoryNestra",
    "preGatedMicroNestra",
    "microNestra100",
    "accuracyLockedMicroNestra",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--pool-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1618033)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--methods", default=",".join(METHODS))
    parser.add_argument("--output", default="benchmarks/nestra-oracle/results/latest.json")
    parser.add_argument("--reasoning-effort", default="none")
    parser.add_argument("--max-output-tokens", type=int, default=96)
    args = parser.parse_args(argv)
    requested = tuple(filter(None, args.methods.split(",")))
    unknown = set(requested) - set(METHODS)
    if unknown:
        raise ValueError(f"Unknown methods: {', '.join(sorted(unknown))}")
    provider = OpenAIResponsesProvider(
        api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
    )
    dataset = _fetch_hotpot(args.pool_size)
    examples = _choose(dataset, args.limit, args.seed)
    output = []
    for position, example in enumerate(examples):
        documents = _documents(example)
        runners = _runners(provider, args, example["question"], documents)
        systems = {}
        order = [*requested[position % len(requested) :], *requested[: position % len(requested)]]
        for name in order:
            systems[name] = runners[name]()
            systems[name]["quality"] = answer_metrics(systems[name]["answer"], example["answer"])
        output.append(
            {
                "id": example["id"],
                "question": example["question"],
                "answer": example["answer"],
                "type": example.get("type"),
                "systems": systems,
            }
        )
        print(f"[{position + 1}/{len(examples)}] {example['id']}", file=sys.stderr)
    result = {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "oracle": {
            "dataset": "hotpotqa/hotpot_qa",
            "config": "distractor",
            "split": "validation",
            "examples": len(output),
            "seed": args.seed,
            "model": args.model,
            "reasoningEffort": args.reasoning_effort,
            "implementation": "python",
            "methods": list(requested),
        },
        "methods": aggregate_methods(output),
        "examples": output,
    }
    target = (ROOT / args.output).resolve()
    if ROOT not in target.parents:
        raise ValueError("Output must stay inside the repository.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"output": str(target), "examples": len(output), "methods": result["methods"]}, indent=2
        )
    )
    return 0


def _runners(
    provider: OpenAIResponsesProvider,
    args: argparse.Namespace,
    question: str,
    documents: list[dict[str, Any]],
) -> dict[str, Callable[[], dict[str, Any]]]:
    def call(name: str, prompt: str, max_tokens: int | None = None) -> dict[str, Any]:
        response = provider.generate(
            {
                "name": name,
                "model": args.model,
                "instructions": "Answer with only the shortest supported answer. Do not explain.",
                "input": prompt,
                "maxOutputTokens": max_tokens or args.max_output_tokens,
                "reasoningEffort": args.reasoning_effort,
            }
        )
        return {**response, "name": name}

    def direct():
        return _one(call, "direct", question)

    def rag():
        selected = [documents[index] for index in bm25_rank(question, documents)[:3]]
        return _one(
            call, "rag", f"Question: {question}\n\nEvidence:\n{_render(selected)}", retrieval=True
        )

    def fixed():
        started = time.perf_counter()
        calls = []
        context = _render(documents)
        for role, instruction in (
            ("scout", "State the information needed."),
            ("forager", "Select the relevant facts."),
            ("builder", "Produce the shortest answer."),
            ("guard", "Return the final shortest supported answer."),
        ):
            response = call(
                f"fixed-{role}",
                f"Question: {question}\n{instruction}\nCorpus:\n{context}\nPrior:\n"
                + "\n".join(row["text"] for row in calls),
                64,
            )
            calls.append(response)
        return _result(enforce_answer_contract(question, calls[-1]["text"]), calls, started)

    def adaptive():
        started = time.perf_counter()
        index = compile_project_memory(
            {
                "projectId": "oracle",
                "documents": [{**row, "trust": "trusted"} for row in documents],
            },
            default_trust="trusted",
        )
        recall = index.recall(question, limit=16, max_atoms=6)
        response = call(
            "adaptive-memory", f"Question: {question}\nEvidence:\n{recall['evidenceText']}", 96
        )
        return _result(
            enforce_answer_contract(question, response["text"]),
            [response],
            started,
            {"memory": {"facts": len(recall["factIds"]), "documents": len(recall["documentIds"])}},
        )

    def micro_only():
        return _micro(call, question, documents, fallback=False)

    def accuracy_locked():
        return _micro(call, question, documents, fallback=True)

    def pre_gated():
        index = compile_project_memory(
            {
                "projectId": "oracle",
                "documents": [{**row, "trust": "trusted"} for row in documents],
            },
            default_trust="trusted",
        )
        recall = index.recall(question, max_atoms=2)
        gate = evaluate_pre_call_gate(question, recall, maxEvidenceTokens=80)
        if gate["route"] != "micro":
            result = adaptive()
            result["preCallGate"] = gate
            return result
        selected = [documents[index] for index in bm25_rank(question, documents)[:2]]
        result = _micro(call, question, selected, fallback=True)
        result["preCallGate"] = gate
        return result

    return {
        "directGpt56": direct,
        "ragGpt56": rag,
        "fixedNestra": fixed,
        "adaptiveMemoryNestra": adaptive,
        "preGatedMicroNestra": pre_gated,
        "microNestra100": micro_only,
        "accuracyLockedMicroNestra": accuracy_locked,
    }


def _one(call: Callable, name: str, prompt: str, retrieval: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    response = call(name, prompt)
    return _result(
        enforce_answer_contract(prompt.split("\n", 1)[0], response["text"]),
        [response],
        started,
        {"retrieval": retrieval},
    )


def _micro(
    call: Callable, question: str, documents: list[dict[str, Any]], fallback: bool
) -> dict[str, Any]:
    started = time.perf_counter()
    compilation = compile_atomic_evidence(
        question, documents, target_total_tokens=100, max_output_tokens=16
    )
    compact = call("micro-100", micro_prompt(question, compilation), 16)
    answer = ground_answer_span(compact["text"], compilation["evidenceText"])
    lock = evaluate_accuracy_lock(question, answer, compilation)
    calls = [compact]
    if fallback and not lock["accepted"]:
        repair = call(
            "micro-accuracy-fallback",
            f"Question: {question}\nCorpus:\n{_render(documents)}\nRejected draft: {answer}",
            96,
        )
        calls.append(repair)
        answer = enforce_answer_contract(question, repair["text"])
    return _result(
        answer,
        calls,
        started,
        {
            "micro": {
                "accuracyLockWouldAccept": lock,
                "estimatedCompactCallTokens": compilation["estimatedTotalTokens"],
                "queryCoverage": compilation["queryCoverage"],
                "intentCoverage": compilation["intentCoverage"],
                "structuralChain": compilation["structuralChain"],
                "evidenceAtoms": compilation["atoms"],
            }
        },
    )


def _result(
    answer: str, calls: list[dict[str, Any]], started: float, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "answer": answer,
        "calls": [
            {
                "name": row["name"],
                "model": row["model"],
                "latencyMs": row["latencyMs"],
                "usage": row["usage"],
            }
            for row in calls
        ],
        "latencyMs": (time.perf_counter() - started) * 1000,
        **(extra or {}),
    }


def _fetch_hotpot(limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "dataset": "hotpotqa/hotpot_qa",
            "config": "distractor",
            "split": "validation",
            "offset": 0,
            "length": limit,
        }
    )
    with urllib.request.urlopen(
        f"https://datasets-server.huggingface.co/rows?{params}", timeout=60
    ) as response:
        payload = json.loads(response.read())
    return [row["row"] for row in payload["rows"]]


def _choose(rows: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    selected = []
    for type_ in ("bridge", "comparison"):
        selected.extend(
            row
            for row in shuffled
            if row.get("type") == type_ and row not in selected and len(selected) < limit
        )
    selected.extend(row for row in shuffled if row not in selected and len(selected) < limit)
    return selected[:limit]


def _documents(row: dict[str, Any]) -> list[dict[str, str]]:
    titles = row.get("context", {}).get("title", [])
    sentences = row.get("context", {}).get("sentences", [])
    return [
        {"title": title, "text": " ".join(parts)}
        for title, parts in zip(titles, sentences, strict=False)
    ]


def _render(documents: list[dict[str, Any]]) -> str:
    return "\n\n".join(f"[{row['title']}]\n{row['text']}" for row in documents)


if __name__ == "__main__":
    raise SystemExit(main())
