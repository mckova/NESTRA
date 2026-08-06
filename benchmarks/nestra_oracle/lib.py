"""Provider-neutral benchmark metrics and lexical retrieval."""

from __future__ import annotations

import math
import re
from collections import Counter
from statistics import mean, median
from typing import Any


def tokenize(text: object) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def bm25_rank(
    query: str, documents: list[dict[str, Any]], *, k1: float = 1.5, b: float = 0.75
) -> list[int]:
    terms = set(tokenize(query))
    tokenized = [tokenize(row["text"]) for row in documents]
    average = mean([len(row) for row in tokenized]) if tokenized else 1
    frequency = {term: sum(term in row for row in tokenized) for term in terms}
    scores = []
    for index, tokens in enumerate(tokenized):
        counts = Counter(tokens)
        score = 0.0
        for term in terms:
            count = counts[term]
            if not count:
                continue
            df = frequency[term]
            idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            score += (
                idf * count * (k1 + 1) / (count + k1 * (1 - b + b * len(tokens) / max(1, average)))
            )
        scores.append((score, index))
    return [index for _score, index in sorted(scores, key=lambda row: (-row[0], row[1]))]


def answer_metrics(prediction: object, expected: object) -> dict[str, float]:
    predicted = _normalize_answer(prediction).split()
    wanted = _normalize_answer(expected).split()
    exact = float(predicted == wanted)
    if not predicted or not wanted:
        return {
            "exactMatch": exact,
            "tokenF1": exact,
            "taskLoss": 1 - exact,
            "exactLoss": 1 - exact,
        }
    available = Counter(predicted)
    overlap = 0
    for token in wanted:
        if available[token] > 0:
            available[token] -= 1
            overlap += 1
    precision, recall = overlap / len(predicted), overlap / len(wanted)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {"exactMatch": exact, "tokenF1": f1, "taskLoss": 1 - f1, "exactLoss": 1 - exact}


def enforce_answer_contract(question: str, answer: object) -> str:
    text = str(answer or "").strip().strip('"').removesuffix(".")
    if re.match(
        r"^(?:are|is|was|were|do|does|did|can|could|has|have|had)\b", question.strip(), re.I
    ):
        match = re.search(r"\b(yes|no)\b", text, re.I)
        return match.group(1).capitalize() if match else text
    return text.split("\n", 1)[0].strip()


def aggregate_usage(calls: list[dict[str, Any]]) -> dict[str, int]:
    keys = ("inputTokens", "outputTokens", "reasoningTokens", "totalTokens", "cachedInputTokens")
    return {key: sum(call.get("usage", {}).get(key, 0) for call in calls) for key in keys}


def aggregate_methods(examples: list[dict[str, Any]]) -> dict[str, Any]:
    names = sorted({name for example in examples for name in example.get("systems", {})})
    output = {}
    for name in names:
        rows = [
            example["systems"][name] for example in examples if name in example.get("systems", {})
        ]
        usage = aggregate_usage([call for row in rows for call in row.get("calls", [])])
        output[name] = {
            "examples": len(rows),
            "calls": sum(len(row.get("calls", [])) for row in rows),
            "exactMatch": mean(row["quality"]["exactMatch"] for row in rows),
            "tokenF1": mean(row["quality"]["tokenF1"] for row in rows),
            "exactLoss": mean(row["quality"]["exactLoss"] for row in rows),
            "taskLoss": mean(row["quality"]["taskLoss"] for row in rows),
            "averageEndToEndLatencyMs": mean(row["latencyMs"] for row in rows),
            "p50EndToEndLatencyMs": median(row["latencyMs"] for row in rows),
            "usage": usage,
            "averageTokensPerExample": usage["totalTokens"] / len(rows),
        }
    return output


def _normalize_answer(value: object) -> str:
    text = re.sub(r"\b(a|an|the)\b", " ", str(value or "").lower())
    return " ".join(re.findall(r"[a-z0-9]+", text))
