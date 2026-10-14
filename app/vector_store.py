"""Vector retrieval boundary. Pinecone holds vectors; RDS remains the ACL authority."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from .config import (
    ENVIRONMENT, PINECONE_API_KEY, PINECONE_INDEX_HOST, PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE_PREFIX, VECTOR_STORE,
)
from .schemas import UserView


@dataclass(frozen=True)
class VectorMatch:
    id: str
    score: float
    metadata: dict


def namespace_for(organization_id: str) -> str:
    return f"{PINECONE_NAMESPACE_PREFIX}{organization_id}"


def acl_filter(user: UserView) -> dict | None:
    """The filter is sent with the query, before any candidate is returned."""
    if "workspace_admin" in user.roles:
        return None
    return {"$and": [
        {"allowed_departments": {"$in": ["all", user.department]}},
        {"allowed_roles": {"$in": user.roles}},
    ]}


def metadata_for(*, document_id: str, organization_id: str, content: str,
                 allowed_departments: list[str], allowed_roles: list[str],
                 classification: str, position: int, page_number: int | None) -> dict:
    return {
        "document_id": document_id,
        "organization_id": organization_id,
        "content": content,
        "allowed_departments": allowed_departments,
        "allowed_roles": allowed_roles,
        "classification": classification,
        "position": position,
        "page_number": page_number or 0,
    }


class MemoryVectorStore:
    """Development-only adapter: API contract mirrors Pinecone, never used in production."""
    def __init__(self):
        self.records: dict[str, dict[str, tuple[list[float], dict]]] = {}

    def upsert(self, namespace: str, vectors: list[dict]) -> None:
        target = self.records.setdefault(namespace, {})
        for vector in vectors:
            target[vector["id"]] = (vector["values"], vector["metadata"])

    def delete_document(self, namespace: str, document_id: str) -> None:
        target = self.records.get(namespace, {})
        for key, (_, metadata) in list(target.items()):
            if metadata.get("document_id") == document_id:
                del target[key]

    def query(self, namespace: str, vector: list[float], user: UserView, top_k: int) -> list[VectorMatch]:
        matches: list[VectorMatch] = []
        for identifier, (values, metadata) in self.records.get(namespace, {}).items():
            department_ok = "all" in metadata["allowed_departments"] or user.department in metadata["allowed_departments"]
            role_ok = bool(set(user.roles).intersection(metadata["allowed_roles"]))
            if "workspace_admin" not in user.roles and not (department_ok and role_ok):
                continue
            score = sum(left * right for left, right in zip(vector, values))
            matches.append(VectorMatch(identifier, score, metadata))
        return sorted(matches, key=lambda item: item.score, reverse=True)[:top_k]


class PineconeVectorStore:
    def __init__(self):
        if not PINECONE_API_KEY or not (PINECONE_INDEX_HOST or PINECONE_INDEX_NAME):
            raise RuntimeError("PINECONE_API_KEY và PINECONE_INDEX_HOST (hoặc INDEX_NAME) là bắt buộc khi VECTOR_STORE=pinecone.")
        from pinecone import Pinecone
        client = Pinecone(api_key=PINECONE_API_KEY)
        self.index = client.Index(host=PINECONE_INDEX_HOST) if PINECONE_INDEX_HOST else client.Index(PINECONE_INDEX_NAME)

    def upsert(self, namespace: str, vectors: list[dict]) -> None:
        for start in range(0, len(vectors), 96):
            self.index.upsert(vectors=vectors[start:start + 96], namespace=namespace)

    def delete_document(self, namespace: str, document_id: str) -> None:
        self.index.delete(namespace=namespace, filter={"document_id": {"$eq": document_id}})

    def query(self, namespace: str, vector: list[float], user: UserView, top_k: int) -> list[VectorMatch]:
        query = {"namespace": namespace, "vector": vector, "top_k": top_k, "include_metadata": True}
        if access_filter := acl_filter(user):
            query["filter"] = access_filter
        response = self.index.query(**query)
        return [VectorMatch(match.id, float(match.score), dict(match.metadata or {})) for match in response.matches]


@lru_cache(maxsize=1)
def get_vector_store() -> MemoryVectorStore | PineconeVectorStore:
    if VECTOR_STORE == "pinecone":
        return PineconeVectorStore()
    if VECTOR_STORE == "memory" and ENVIRONMENT != "production":
        return MemoryVectorStore()
    raise RuntimeError("Production requires VECTOR_STORE=pinecone; memory is limited to local development.")
