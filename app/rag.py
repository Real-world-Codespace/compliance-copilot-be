"""Secure RAG: tenant and ACL constraints are applied at vector retrieval time."""

import hashlib
import math
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from .config import EMBEDDING_DIMENSIONS, ENVIRONMENT, OPENAI_API_KEY
from .database import DocumentChunk, KnowledgeDocument, SessionLocal
from .embeddings import get_embeddings
from .schemas import UserView
from .vector_store import get_vector_store, metadata_for, namespace_for

EMBEDDING_DIMENSION = EMBEDDING_DIMENSIONS


def embed(text: str) -> list[float]:
    """Uses the approved embedding API outside the explicitly local fallback."""
    if OPENAI_API_KEY:
        return get_embeddings().query(text)
    if ENVIRONMENT == "production":
        raise RuntimeError("Production không được dùng deterministic embedding fallback.")
    vector = [0.0] * EMBEDDING_DIMENSION
    for token in re.findall(r"[\wÀ-ỹ]+", text.lower()):
        bucket = int(hashlib.sha256(token.encode()).hexdigest(), 16) % EMBEDDING_DIMENSION
        vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def is_permitted(user: UserView, item: DocumentChunk) -> bool:
    if user.organization_id == item.organization_id and "workspace_admin" in user.roles:
        return True
    department_match = "all" in item.allowed_departments or user.department in item.allowed_departments
    role_match = bool(set(user.roles).intersection(item.allowed_roles))
    return item.organization_id == user.organization_id and department_match and role_match


def chunk_text(content: str, size: int = 900) -> list[str]:
    words = content.split()
    return [" ".join(words[index:index + size]) for index in range(0, len(words), size)] or [content]


def index_chunks(chunks: list[DocumentChunk]) -> None:
    """Upsert chunks into the tenant namespace only after their RDS records exist."""
    by_namespace: dict[str, list[dict]] = {}
    for chunk in chunks:
        namespace = namespace_for(chunk.organization_id)
        by_namespace.setdefault(namespace, []).append({
            "id": chunk.id,
            "values": embed(chunk.content),
            "metadata": metadata_for(
                document_id=chunk.document_id, organization_id=chunk.organization_id,
                content=chunk.content, allowed_departments=chunk.allowed_departments,
                allowed_roles=chunk.allowed_roles, classification=chunk.classification,
                position=chunk.position, page_number=chunk.page_number,
            ),
        })
    store = get_vector_store()
    for namespace, vectors in by_namespace.items():
        store.upsert(namespace, vectors)


def ingest_text(user: UserView, title: str, content: str, classification: str, departments: list[str], roles: list[str]) -> str:
    document_id = f"doc-{uuid.uuid4().hex[:16]}"
    chunks: list[DocumentChunk] = []
    with SessionLocal() as session:
        session.add(KnowledgeDocument(
            id=document_id, organization_id=user.organization_id, title=title, source_type="text",
            classification=classification, allowed_departments=departments, allowed_roles=roles,
            created_by=user.id, created_at=datetime.now(UTC),
        ))
        for position, part in enumerate(chunk_text(content)):
            chunk = DocumentChunk(
                id=f"chk-{uuid.uuid4().hex[:16]}", document_id=document_id,
                organization_id=user.organization_id, position=position, page_number=None, content=part,
                allowed_departments=departments, allowed_roles=roles, classification=classification,
            )
            chunks.append(chunk)
            session.add(chunk)
        session.commit()
    index_chunks(chunks)
    return document_id


def secure_retrieve(user: UserView, question: str, limit: int = 4) -> list[tuple[DocumentChunk, float]]:
    """Pinecone namespace + metadata ACL filter precedes retrieval; RDS rechecks every match."""
    matches = get_vector_store().query(namespace_for(user.organization_id), embed(question), user, limit)
    if not matches:
        return []
    score_by_id = {match.id: match.score for match in matches}
    with SessionLocal() as session:
        chunks = session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(score_by_id))).all()
    # RDS is authoritative: this protects against stale/tampered vector metadata too.
    permitted = [chunk for chunk in chunks if is_permitted(user, chunk)]
    return sorted(((chunk, round(score_by_id[chunk.id], 3)) for chunk in permitted), key=lambda item: item[1], reverse=True)
