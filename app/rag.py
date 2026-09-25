"""Secure retrieval: ACL filtering happens before similarity ranking or generation."""

import hashlib
import math
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from .config import EMBEDDING_DIMENSIONS, ENVIRONMENT, OPENAI_API_KEY
from .database import DocumentChunk, KnowledgeDocument, SessionLocal
from .embeddings import get_embeddings
from .schemas import UserView

EMBEDDING_DIMENSION = EMBEDDING_DIMENSIONS


def embed(text: str) -> list[float]:
    """Uses an approved embedding API outside the explicitly local fallback."""
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


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def is_permitted(user: UserView, item: DocumentChunk) -> bool:
    department_match = "all" in item.allowed_departments or user.department in item.allowed_departments
    role_match = bool(set(user.roles).intersection(item.allowed_roles))
    return item.organization_id == user.organization_id and department_match and role_match


def chunk_text(content: str, size: int = 900) -> list[str]:
    words = content.split()
    return [" ".join(words[index:index + size]) for index in range(0, len(words), size)] or [content]


def ingest_text(user: UserView, title: str, content: str, classification: str, departments: list[str], roles: list[str]) -> str:
    document_id = f"doc-{uuid.uuid4().hex[:16]}"
    with SessionLocal() as session:
        session.add(KnowledgeDocument(
            id=document_id, organization_id=user.organization_id, title=title, source_type="text",
            classification=classification, allowed_departments=departments, allowed_roles=roles,
            created_by=user.id, created_at=datetime.now(UTC),
        ))
        for position, part in enumerate(chunk_text(content)):
            session.add(DocumentChunk(
                id=f"chk-{uuid.uuid4().hex[:16]}", document_id=document_id,
                organization_id=user.organization_id, position=position, content=part,
                embedding=embed(part), allowed_departments=departments, allowed_roles=roles,
                classification=classification,
            ))
        session.commit()
    return document_id


def secure_retrieve(user: UserView, question: str, limit: int = 4) -> list[tuple[DocumentChunk, float]]:
    """In PostgreSQL, ACL metadata filters and pgvector ranking execute in one query."""
    question_embedding = embed(question)
    with SessionLocal() as session:
        if session.bind.dialect.name == "postgresql":
            departments = cast(DocumentChunk.allowed_departments, JSONB)
            roles = cast(DocumentChunk.allowed_roles, JSONB)
            department_acl = or_(departments.contains(["all"]), departments.contains([user.department]))
            role_acl = or_(*[roles.contains([role]) for role in user.roles])
            distance = cast(DocumentChunk.embedding, Vector(EMBEDDING_DIMENSION)).cosine_distance(question_embedding).label("distance")
            rows = session.execute(
                select(DocumentChunk, distance)
                .where(and_(DocumentChunk.organization_id == user.organization_id, department_acl, role_acl))
                .order_by(distance)
                .limit(limit)
            ).all()
            return [(chunk, round(1 - float(distance), 3)) for chunk, distance in rows]

        # SQLite fallback is only for local tests. It still filters ACL before scoring.
        tenant_chunks = session.scalars(
            select(DocumentChunk).where(DocumentChunk.organization_id == user.organization_id)
        ).all()

    permitted = [chunk for chunk in tenant_chunks if is_permitted(user, chunk)]
    ranked = sorted(((chunk, cosine(question_embedding, chunk.embedding)) for chunk in permitted), key=lambda item: item[1], reverse=True)
    return [item for item in ranked[:limit] if item[1] > 0]
