"""Compact evidence compilation and deterministic post-call accuracy locks."""

from __future__ import annotations

import re
from typing import Any

from .project_memory import compile_project_memory, estimate_tokens, tokenize_project_text


def compile_atomic_evidence(
    question: str,
    documents: list[dict[str, Any]],
    *,
    target_total_tokens: int = 100,
    max_output_tokens: int = 16,
    instruction: str = "Evidence only. Return answer span.",
    provider_reserve_tokens: int = 25,
) -> dict[str, Any]:
    if len(documents) < 2:
        raise ValueError("Atomic evidence requires at least two documents.")
    trusted = [{**row, "trust": "trusted"} for row in documents]
    recall = compile_project_memory(
        {"projectId": "evidence", "documents": trusted}, default_trust="trusted"
    ).recall(question, max_atoms=2, limit=12)
    title_to_index = {str(row.get("title")): index for index, row in enumerate(documents)}
    fixed = (
        estimate_tokens(f"Q:{question}\nE:\n{instruction}")
        + max_output_tokens
        + provider_reserve_tokens
    )
    evidence_budget = max(12, target_total_tokens - fixed)
    per_atom = max(6, evidence_budget // 2)
    atoms = []
    for atom in recall["atoms"]:
        words = atom["text"].split()
        char_budget = per_atom * 4
        text = (
            atom["text"]
            if len(atom["text"]) <= char_budget
            else " ".join(words[: max(1, per_atom)])
        )
        prompt_text = text if atom["title"].lower() in text.lower() else f"{atom['title']}:{text}"
        atoms.append(
            {
                "id": atom["id"],
                "title": atom["title"],
                "text": text,
                "promptText": prompt_text,
                "originalText": atom["text"],
                "docIndex": title_to_index.get(atom["title"], len(atoms)),
                "sentenceIndex": atom["provenance"].get("sentenceIndex", 0),
                "estimatedTokens": estimate_tokens(prompt_text),
                "truncated": text != atom["text"],
            }
        )
    evidence_text = "\n".join(f"{atom['id']}:{atom['promptText']}" for atom in atoms)
    question_normalized = _normalize(question)
    question_mentions_both = len(atoms) == 2 and all(
        _normalize(atom["title"]) in question_normalized for atom in atoms
    )
    intent_terms = _intent_terms(question)
    atom_intent = [_coverage(intent_terms, atom["text"]) for atom in atoms]
    return {
        "atoms": atoms,
        "evidenceText": evidence_text,
        "estimatedTotalTokens": estimate_tokens(f"Q:{question}\nE:\n{evidence_text}\n{instruction}")
        + max_output_tokens,
        "targetTotalTokens": target_total_tokens,
        "maxOutputTokens": max_output_tokens,
        "instruction": instruction,
        "evidenceBudget": evidence_budget,
        "structuralChain": recall["structuralChain"] or question_mentions_both,
        "questionMentionsBoth": question_mentions_both,
        "linked": recall["structuralChain"],
        "queryCoverage": recall["queryCoverage"],
        "intentCoverage": _coverage(intent_terms, evidence_text),
        "atomIntentCoverage": atom_intent,
        "pairScore": sum(atom.get("retrievalScore", 0) for atom in recall["atoms"]),
        "localLexicalTokensScanned": sum(
            len(tokenize_project_text(row.get("text", ""))) for row in documents
        )
        + len(tokenize_project_text(question)),
        "providerReserveTokens": provider_reserve_tokens,
    }


def evaluate_accuracy_lock(
    question: str,
    answer: object,
    compilation: dict[str, Any],
    *,
    max_answer_tokens: int = 12,
    minimum_coverage: float = 0.45,
) -> dict[str, Any]:
    reasons: list[str] = []
    normalized = _normalize_answer(answer)
    answer_tokens = tokenize_project_text(normalized)
    binary = bool(
        re.match(
            r"^(are|is|was|were|do|does|did|can|could|will|would|has|have|had)\b",
            question.strip(),
            re.I,
        )
    )
    evidence = _normalize_answer(compilation.get("evidenceText", ""))
    grounded = bool(normalized and normalized in evidence)
    if not normalized or normalized == "unknown":
        reasons.append("empty_or_unknown")
    if len(answer_tokens) > max_answer_tokens:
        reasons.append("answer_too_long")
    if (
        len(compilation.get("atoms", [])) < 2
        or len({row.get("docIndex") for row in compilation.get("atoms", [])}) < 2
    ):
        reasons.append("missing_second_document")
    if not compilation.get("structuralChain"):
        reasons.append("no_structural_chain")
    if compilation.get("queryCoverage", 0) < minimum_coverage and not grounded:
        reasons.append("low_query_coverage")
    if (
        re.search(r"\bwho\b|\bwhat is the name\b|\bname of (?:the )?", question, re.I)
        and not re.search(r"\bmiddle name\b", question, re.I)
        and len(answer_tokens) == 1
        and not normalized[:1].isdigit()
    ):
        reasons.append("possibly_incomplete_name")
    if binary:
        if normalized not in {"yes", "no"}:
            reasons.append("invalid_binary_answer")
        if not compilation.get("questionMentionsBoth"):
            reasons.append("binary_entities_not_covered")
        if any(value < 0.08 for value in compilation.get("atomIntentCoverage", [])):
            reasons.append("binary_evidence_incomplete")
    elif not grounded:
        reasons.append("answer_not_grounded")
    return {
        "accepted": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "grounded": grounded,
        "binary": binary,
    }


def micro_prompt(question: str, compilation: dict[str, Any]) -> str:
    return f"Q:{question}\nE:\n{compilation['evidenceText']}"


def ground_answer_span(answer: object, evidence_text: str) -> str:
    trimmed = str(answer or "").strip().removesuffix(".")
    evidence = _normalize_answer(evidence_text)
    if not trimmed or _normalize_answer(trimmed) in evidence:
        return trimmed
    parts = [part.strip() for part in trimmed.split(",") if part.strip()]
    for length in range(len(parts) - 1, 0, -1):
        candidate = ", ".join(parts[:length])
        if len(_normalize_answer(candidate)) > 1 and _normalize_answer(candidate) in evidence:
            return candidate
    return trimmed


def _intent_terms(question: str) -> set[str]:
    terms = set(tokenize_project_text(question))
    cues = {
        "name",
        "middle",
        "located",
        "location",
        "date",
        "year",
        "country",
        "city",
        "born",
        "portrayed",
        "producer",
    }
    return terms & cues or terms


def _coverage(terms: set[str], text: str) -> float:
    return len(terms & set(tokenize_project_text(text))) / max(1, len(terms))


def _normalize(value: object) -> str:
    return " ".join(tokenize_project_text(value))


def _normalize_answer(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().removesuffix("."))
