import re
import uuid
from datetime import UTC, datetime
from sqlalchemy import select
from .database import AuditEvent, PolicyDocument, PurchaseCheck, SessionLocal
from .policy import access_decision, approval_path
from .schemas import AuditView, PolicyView, SpendCheckRequest, UserView

def _score(query: str, content: str) -> float:
    terms = {x for x in re.findall(r"[\wÀ-ỹ]+", query.lower()) if len(x) > 2}; return round(sum(t in content.lower() for t in terms) / max(1,len(terms)), 2)

def search_policies(user: UserView, question: str) -> tuple[str, list[PolicyView]]:
    with SessionLocal() as session: documents = session.scalars(select(PolicyDocument)).all()
    ranked = sorted(documents, key=lambda d: _score(question, f"{d.title} {d.content}"), reverse=True)[:6]
    items=[]; allowed=[]
    for doc in ranked:
        permitted, reason = access_decision(user, doc); score=_score(question, f"{doc.title} {doc.content}")
        item=PolicyView(id=doc.id,title=doc.title,category=doc.category,classification=doc.classification,score=score,decision="allowed" if permitted else "denied",reason=reason,excerpt=doc.content[:360] if permitted else None)
        items.append(item)
        if permitted and score > 0: allowed.append(doc)
    answer = " ".join(doc.content[:420] for doc in allowed[:2]) or "Không có chính sách phù hợp mà tài khoản hiện tại được phép xem."
    _audit(user, "policy_search", question, "allowed" if allowed else "no_permitted_result")
    return answer, items

def evaluate_spend(user: UserView, request: SpendCheckRequest) -> list[dict]:
    path=approval_path(float(request.amount_vnd), request.contract_months)
    with SessionLocal() as session:
        session.add(PurchaseCheck(id=str(uuid.uuid4()), organization_id=user.organization_id, requester_id=user.id, supplier=request.supplier, category=request.category, amount_vnd=request.amount_vnd, contract_months=request.contract_months, approval_path=path, created_at=datetime.now(UTC))); session.commit()
    _audit(user, "spend_check", request.supplier, "approval_path_generated")
    return path

def _audit(user: UserView, action: str, resource: str, outcome: str):
    with SessionLocal() as session:
        session.add(AuditEvent(id=str(uuid.uuid4()), organization_id=user.organization_id, actor_email=user.email, action=action, resource=resource[:255], outcome=outcome, created_at=datetime.now(UTC))); session.commit()

def recent_audits() -> list[AuditView]:
    with SessionLocal() as session: rows=session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(25)).all()
    return [AuditView(created_at=row.created_at.isoformat(),actor_email=row.actor_email,action=row.action,resource=row.resource,outcome=row.outcome) for row in rows]
