"""Deterministic project-memory compilation and lexical multi-document recall."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from .memory import ScopedMemory

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "both",
    "but",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "how",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def compile_project_memory(
    input_: dict[str, Any],
    *,
    clock: Callable[[], datetime] | None = None,
    default_trust: str = "untrusted",
) -> "ProjectMemoryIndex":
    project_id = _non_empty(input_.get("projectId"), "projectId")
    documents = input_.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("documents must be a non-empty list.")
    at = (clock or (lambda: datetime.now(timezone.utc)))()
    rows = [
        _normalize_document(document, index, default_trust)
        for index, document in enumerate(documents)
    ]
    titles = [row["title"] for row in rows]
    entities: dict[str, dict[str, Any]] = {}
    facts: list[dict[str, Any]] = []
    for document in rows:
        for sentence_index, text in enumerate(document["sentences"]):
            labels = _entity_labels(text, document["title"], titles)
            entity_ids = []
            for label in labels:
                normalized = _normalize(label)
                entity_id = f"entity-{_digest(normalized)}"
                entities.setdefault(
                    entity_id,
                    {"id": entity_id, "label": label, "normalized": normalized, "factIds": []},
                )
                entity_ids.append(entity_id)
            fact_key = f"{document['id']}:{sentence_index}:{text}"
            fact_id = f"fact-{_digest(fact_key)}"
            fact = {
                "id": fact_id,
                "documentId": document["id"],
                "title": document["title"],
                "sentenceIndex": sentence_index,
                "text": text,
                "tokens": tokenize_project_text(text),
                "entityIds": entity_ids,
                "provenance": {
                    "projectId": project_id,
                    "documentId": document["id"],
                    "title": document["title"],
                    "contentHash": document["contentHash"],
                    "sentenceIndex": sentence_index,
                    "sourceUri": document["sourceUri"],
                },
                "trust": document["trust"],
                "sensitivity": document["sensitivity"],
                "sourceQuality": document["sourceQuality"],
            }
            facts.append(fact)
            for entity_id in entity_ids:
                entities[entity_id]["factIds"].append(fact_id)
    relations = _relations(facts, entities)
    public_documents = []
    for row in rows:
        public = {key: deepcopy(value) for key, value in row.items() if key != "sentences"}
        public["sentenceCount"] = len(row["sentences"])
        public_documents.append(public)
    snapshot = {
        "schemaVersion": 1,
        "projectId": project_id,
        "compiledAt": at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "documents": public_documents,
        "facts": facts,
        "entities": list(entities.values()),
        "relations": relations,
        "stats": {
            "documents": len(rows),
            "facts": len(facts),
            "entities": len(entities),
            "relations": len(relations),
            "lexicalTokensScanned": sum(len(tokenize_project_text(row["text"])) for row in rows),
        },
    }
    return ProjectMemoryIndex(snapshot)


class ProjectMemoryIndex:
    def __init__(self, snapshot: dict[str, Any]) -> None:
        _validate_snapshot(snapshot)
        self.snapshot = deepcopy(snapshot)
        self.documents = {row["id"]: row for row in self.snapshot["documents"]}
        self.facts = {row["id"]: row for row in self.snapshot["facts"]}
        self.entities = {row["id"]: row for row in self.snapshot["entities"]}

    def recall(
        self,
        question: str,
        *,
        trusted_only: bool = True,
        max_sensitivity: float = 0.5,
        limit: int = 8,
        max_atoms: int = 2,
    ) -> dict[str, Any]:
        query = _non_empty(question, "question")
        terms = _content_terms(query)
        candidates = []
        for fact in self.facts.values():
            if trusted_only and fact["trust"] != "trusted":
                continue
            if fact["sensitivity"] > _unit(max_sensitivity, 0.5):
                continue
            candidates.append(
                {"fact": fact, "score": _fact_score(query, terms, fact, self.entities)}
            )
        candidates.sort(key=lambda row: (-row["score"], row["fact"]["id"]))
        candidates = candidates[: max(limit, 2)]
        pair_rows, bridges = _select_pair(candidates)
        selected_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in [*pair_rows, *candidates]:
            if row["fact"]["id"] in seen:
                continue
            seen.add(row["fact"]["id"])
            selected_rows.append(row)
            if len(selected_rows) >= max(1, max_atoms):
                break
        atoms = []
        for index, row in enumerate(selected_rows):
            fact = row["fact"]
            prompt_text = (
                fact["text"]
                if _mentions(fact["text"], fact["title"])
                else f"{fact['title']}:{fact['text']}"
            )
            atoms.append(
                {
                    "id": f"e{index + 1}",
                    "factId": fact["id"],
                    "documentId": fact["documentId"],
                    "title": fact["title"],
                    "text": fact["text"],
                    "promptText": prompt_text,
                    "trust": fact["trust"],
                    "sensitivity": fact["sensitivity"],
                    "provenance": deepcopy(fact["provenance"]),
                    "retrievalScore": round(row["score"], 6),
                }
            )
        evidence_text = "\n".join(f"{atom['id']}:{atom['promptText']}" for atom in atoms)
        intent_terms = _intent_terms(query)
        return {
            "projectId": self.snapshot["projectId"],
            "question": query,
            "atoms": atoms,
            "evidenceText": evidence_text,
            "factIds": [row["fact"]["id"] for row in selected_rows],
            "documentIds": list(dict.fromkeys(row["fact"]["documentId"] for row in selected_rows)),
            "bridgeEntityIds": bridges,
            "bridgeEntities": [
                self.entities[item]["label"] for item in bridges if item in self.entities
            ],
            "structuralChain": bool(bridges),
            "queryCoverage": _coverage(terms, evidence_text),
            "intentCoverage": _coverage(intent_terms, evidence_text),
            "estimatedEvidenceTokens": estimate_tokens(evidence_text),
            "trusted": bool(atoms) and all(atom["trust"] == "trusted" for atom in atoms),
            "maximumSensitivity": max((atom["sensitivity"] for atom in atoms), default=0),
            "candidatesConsidered": len(candidates),
        }

    def to_scoped_memory(
        self,
        memory: ScopedMemory,
        *,
        namespace: str | None = None,
        visibility: list[str] | None = None,
        ttl_ms: int | None = None,
        half_life_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        if not isinstance(memory, ScopedMemory):
            raise ValueError("memory must be a ScopedMemory instance.")
        target = namespace or self.snapshot["projectId"]
        roles = visibility or ["queen", "scout", "forager", "builder", "guard", "caretaker"]
        return [
            memory.write(
                id=fact["id"],
                scope="project",
                namespace=target,
                kind="compiled_fact",
                content=fact["text"],
                trust=fact["trust"],
                sensitivity=fact["sensitivity"],
                sourceQuality=fact["sourceQuality"],
                verifiedUtility=0.8 if fact["trust"] == "trusted" else 0.4,
                visibility=roles,
                ttlMs=ttl_ms,
                halfLifeMs=half_life_ms,
                metadata={**fact["provenance"], "entityIds": fact["entityIds"]},
            )
            for fact in self.snapshot["facts"]
        ]

    def export(self) -> dict[str, Any]:
        return deepcopy(self.snapshot)


def restore_project_memory(snapshot: dict[str, Any]) -> ProjectMemoryIndex:
    return ProjectMemoryIndex(snapshot)


def evaluate_pre_call_gate(question: str, recall: dict[str, Any], **options: Any) -> dict[str, Any]:
    _non_empty(question, "question")
    reasons = []
    atoms = recall.get("atoms") if isinstance(recall, dict) else None
    require_multi = options.get("requireMultiDocument", True) is not False
    minimum_coverage = float(options.get("minimumCoverage", 0.45))
    minimum_intent = float(options.get("minimumIntentCoverage", 0.15))
    max_tokens = int(options.get("maxEvidenceTokens", 55))
    if not isinstance(atoms, list):
        reasons.append("invalid_recall")
    else:
        if len(atoms) < 2:
            reasons.append("insufficient_facts")
        if require_multi and len({atom["documentId"] for atom in atoms}) < 2:
            reasons.append("missing_second_document")
        if require_multi and not recall.get("structuralChain"):
            reasons.append("no_structural_chain")
        if recall.get("queryCoverage", 0) < minimum_coverage:
            reasons.append("low_query_coverage")
        if recall.get("intentCoverage", 0) < minimum_intent:
            reasons.append("low_intent_coverage")
        if not recall.get("trusted"):
            reasons.append("untrusted_evidence")
        if recall.get("maximumSensitivity", 0) > _unit(options.get("maxSensitivity"), 0.5):
            reasons.append("sensitive_evidence")
        if recall.get("estimatedEvidenceTokens", 0) > max_tokens:
            reasons.append("evidence_exceeds_micro_budget")
    blocked = any(reason in {"untrusted_evidence", "sensitive_evidence"} for reason in reasons)
    return {
        "accepted": not reasons,
        "authorized": not blocked,
        "route": "micro" if not reasons else "blocked" if blocked else "fallback",
        "reasons": reasons,
        "checks": {
            "requireMultiDocument": require_multi,
            "minimumCoverage": minimum_coverage,
            "minimumIntentCoverage": minimum_intent,
            "maxEvidenceTokens": max_tokens,
        },
    }


def tokenize_project_text(text: object) -> list[str]:
    return re.findall(
        r"[^\W_]+", unicodedata.normalize("NFKC", str(text)).lower(), flags=re.UNICODE
    )


def estimate_tokens(text: object) -> int:
    return max(1, round(len(str(text)) / 4)) if str(text) else 0


def _normalize_document(document: dict[str, Any], index: int, default_trust: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("document must be a mapping.")
    title = _non_empty(document.get("title") or f"Document {index + 1}", "document.title")
    text = _non_empty(
        document.get("text") or " ".join(document.get("sentences", [])), "document.text"
    )
    sentences = (
        document.get("sentences")
        if isinstance(document.get("sentences"), list)
        else re.split(r"(?<=[.!?])\s+", text)
    )
    sentences = [str(row).strip() for row in sentences if str(row).strip()]
    trust = (
        document.get("trust")
        if document.get("trust") in {"trusted", "untrusted"}
        else ("trusted" if default_trust == "trusted" else "untrusted")
    )
    return {
        "id": str(document.get("id") or f"doc-{_digest(f'{index}:{title}:{text}', 12)}"),
        "title": title,
        "text": text,
        "sourceUri": document.get("sourceUri"),
        "trust": trust,
        "sensitivity": _unit(document.get("sensitivity"), 0),
        "sourceQuality": _unit(document.get("sourceQuality"), 1 if trust == "trusted" else 0.5),
        "contentHash": _digest(text, 24),
        "sentences": sentences or [text],
    }


def _entity_labels(text: str, title: str, known_titles: Iterable[str]) -> list[str]:
    labels: list[str] = [title]
    labels.extend(candidate for candidate in known_titles if _mentions(text, candidate))
    labels.extend(
        match.group(0) for match in re.finditer(r"\b[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)+\b", text)
    )
    output: dict[str, str] = {}
    for label in labels:
        cleaned = str(label).strip(" .,;:()[]{}")
        if len(cleaned) > 1:
            output.setdefault(_normalize(cleaned), cleaned)
    return list(output.values())


def _relations(
    facts: list[dict[str, Any]], entities: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    output = []
    for fact in facts:
        ids = list(dict.fromkeys(fact["entityIds"]))
        for left_index, left in enumerate(ids):
            for right in ids[left_index + 1 :]:
                relation_key = f"{fact['id']}:{left}:{right}"
                output.append(
                    {
                        "id": f"rel-{_digest(relation_key)}",
                        "leftEntityId": left,
                        "rightEntityId": right,
                        "factId": fact["id"],
                        "documentId": fact["documentId"],
                    }
                )
    return output


def _fact_score(
    question: str, terms: set[str], fact: dict[str, Any], entities: dict[str, dict[str, Any]]
) -> float:
    fact_terms = set(fact["tokens"])
    overlap = len(terms & fact_terms) / max(1, len(terms))
    title = 0.35 if _mentions(question, fact["title"]) else 0
    entity = (
        0.15
        if any(
            _mentions(question, entities[item]["label"])
            for item in fact["entityIds"]
            if item in entities
        )
        else 0
    )
    return overlap + title + entity + fact["sourceQuality"] * 0.05


def _select_pair(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    best: tuple[float, list[dict[str, Any]], list[str]] | None = None
    for left_index, left in enumerate(candidates[:12]):
        for right in candidates[left_index + 1 : 12]:
            if left["fact"]["documentId"] == right["fact"]["documentId"]:
                continue
            bridges = sorted(set(left["fact"]["entityIds"]) & set(right["fact"]["entityIds"]))
            score = left["score"] + right["score"] + (0.75 if bridges else 0)
            if best is None or score > best[0]:
                best = (score, [left, right], bridges)
    return (best[1], best[2]) if best else (candidates[:2], [])


def _content_terms(text: str) -> set[str]:
    return {
        token for token in tokenize_project_text(text) if token not in STOPWORDS and len(token) > 1
    }


def _intent_terms(question: str) -> set[str]:
    terms = _content_terms(question)
    lower = question.lower()
    if re.search(r"\bwhere\b|\blocated\b|\borigin\b", lower):
        terms |= {"location", "located", "born", "formed", "based", "city", "state", "country"}
    if re.search(r"\bwhen\b|\byear\b|\bdate\b", lower):
        terms |= {"year", "date", "born", "founded", "released"}
    if re.search(r"\bwho\b|\bname\b|\bcomposer\b|\bproducer\b", lower):
        terms |= {"name", "born", "composer", "producer", "created", "written"}
    if "nationality" in lower:
        terms |= {
            "nationality",
            "american",
            "british",
            "canadian",
            "french",
            "german",
            "italian",
            "spanish",
        }
    return terms


def _coverage(terms: set[str], text: str) -> float:
    if not terms:
        return 1.0
    present = set(tokenize_project_text(text))
    return round(len(terms & present) / len(terms), 6)


def _mentions(text: str, label: str) -> bool:
    return _normalize(label) in _normalize(text)


def _normalize(text: object) -> str:
    return " ".join(tokenize_project_text(text))


def _digest(value: object, length: int = 16) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:length]


def _unit(value: object, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


def _non_empty(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string.")
    return text


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schemaVersion") != 1
        or not snapshot.get("projectId")
    ):
        raise ValueError("Invalid Project Memory snapshot.")
    for key in ("documents", "facts", "entities", "relations"):
        if not isinstance(snapshot.get(key), list):
            raise ValueError(f"Project Memory snapshot {key} must be a list.")
