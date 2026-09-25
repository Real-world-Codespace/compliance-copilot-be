import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from .database import AuditEvent, PurchaseCheck, SessionLocal
from .policy import approval_path
from .rag import secure_retrieve
from .schemas import AuditView, CitationView, SecureAnswer, SpendCheckRequest, UserView


def answer_question(user: UserView, question: str) -> SecureAnswer:
    results = secure_retrieve(user, question)
    citations = [
        CitationView(
            document_id=chunk.document_id,
            title=_document_title(chunk.document_id),
            classification=chunk.classification,
            excerpt=chunk.content[:360],
            score=round(score, 3),
        )
        for chunk, score in results
    ]
    answer = "\n\n".join(citation.excerpt for citation in citations[:2])
    if not answer:
        answer = "Không có tri thức phù hợp mà tài khoản hiện tại được phép xem."
    _audit(user, "rag_query", question, "permitted_context_returned" if citations else "no_permitted_context")
    return SecureAnswer(answer=answer, citations=citations)


def _document_title(document_id: str) -> str:
    from .database import KnowledgeDocument
    with SessionLocal() as session:
        document = session.get(KnowledgeDocument, document_id)
        return document.title if document else "Internal knowledge"


def evaluate_spend(user: UserView, request: SpendCheckRequest) -> list[dict]:
    path = approval_path(float(request.amount_vnd), request.contract_months)
    with SessionLocal() as session:
        session.add(PurchaseCheck(
            id=str(uuid.uuid4()), organization_id=user.organization_id, requester_id=user.id,
            supplier=request.supplier, category=request.category, amount_vnd=request.amount_vnd,
            contract_months=request.contract_months, approval_path=path, created_at=datetime.now(UTC),
        ))
        session.commit()
    _audit(user, "spend_check", request.supplier, "approval_path_generated")
    return path


def _audit(user: UserView, action: str, resource: str, outcome: str) -> None:
    with SessionLocal() as session:
        session.add(AuditEvent(
            id=str(uuid.uuid4()), organization_id=user.organization_id, actor_email=user.email,
            action=action, resource=resource[:255], outcome=outcome, created_at=datetime.now(UTC),
        ))
        session.commit()


def recent_audits(user: UserView) -> list[AuditView]:
    if "workspace_admin" not in user.roles:
        raise HTTPException(403, "Chỉ workspace admin được xem audit")
    with SessionLocal() as session:
        rows = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.organization_id == user.organization_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(50)
        ).all()
    return [AuditView(created_at=row.created_at.isoformat(), actor_email=row.actor_email, action=row.action, resource=row.resource, outcome=row.outcome) for row in rows]
