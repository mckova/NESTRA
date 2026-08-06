"""Minimal adapter shape for an existing vector database client."""

from __future__ import annotations


class VectorRetriever:
    def __init__(self, client, *, verified_source_ids: set[str] | None = None) -> None:
        self.client = client
        self.verified_source_ids = verified_source_ids or set()

    def retrieve(self, *, project_id: str, query: str, limit: int = 24) -> dict:
        matches = self.client.search(namespace=project_id, query=query, limit=limit)
        return {
            "documents": [
                {
                    "id": match.id,
                    "title": match.metadata["title"],
                    "text": match.metadata["text"],
                    "sourceUri": match.metadata.get("source_uri"),
                    "sourceQuality": match.score,
                    # Similarity is not trust. Only a separately verified source may opt in.
                    "trust": "trusted" if match.id in self.verified_source_ids else "untrusted",
                }
                for match in matches
            ]
        }
