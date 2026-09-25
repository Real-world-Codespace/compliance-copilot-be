from datetime import datetime
from decimal import Decimal
from sqlalchemy import JSON, DateTime, Numeric, String, Text, TypeDecorator, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pgvector.sqlalchemy import Vector
from .config import DATABASE_URL, EMBEDDING_DIMENSIONS


class Base(DeclarativeBase): pass


class EmbeddingType(TypeDecorator):
    """Uses pgvector in PostgreSQL and JSON locally, keeping local tests portable."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(EMBEDDING_DIMENSIONS))
        return dialect.type_descriptor(JSON())


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))


class AppUser(Base):
    __tablename__ = "app_users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    department: Mapped[str] = mapped_column(String(80))
    roles: Mapped[list] = mapped_column(JSON)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PolicyDocument(Base):
    __tablename__ = "policy_documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(80), index=True)
    classification: Mapped[str] = mapped_column(String(40), index=True)
    allowed_departments: Mapped[list] = mapped_column(JSON)
    allowed_roles: Mapped[list] = mapped_column(JSON)
    content: Mapped[str] = mapped_column(Text)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(40), default="policy")
    classification: Mapped[str] = mapped_column(String(40), index=True)
    allowed_departments: Mapped[list] = mapped_column(JSON)
    allowed_roles: Mapped[list] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1000), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ready", index=True)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), index=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True)
    position: Mapped[int] = mapped_column()
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(EmbeddingType())
    allowed_departments: Mapped[list] = mapped_column(JSON)
    allowed_roles: Mapped[list] = mapped_column(JSON)
    classification: Mapped[str] = mapped_column(String(40), index=True)


class PurchaseCheck(Base):
    __tablename__ = "purchase_checks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True)
    requester_id: Mapped[str] = mapped_column(String(64), index=True)
    supplier: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    amount_vnd: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    contract_months: Mapped[int] = mapped_column()
    approval_path: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_email: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
