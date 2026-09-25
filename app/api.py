from fastapi import APIRouter
from sqlalchemy import select
from .auth import current_user, login, login_with_password, register_account, to_view
from .database import AppUser, SessionLocal
from .schemas import AskRequest, AuditView, DemoLogin, LoginRequest, RegisterRequest, SpendCheckRequest, UserView
from .services import evaluate_spend, recent_audits, search_policies

router=APIRouter(prefix="/api")
@router.get("/health")
def health(): return {"status":"ok"}
@router.get("/demo-users",response_model=list[UserView])
def demo_users():
    with SessionLocal() as session: return [to_view(user) for user in session.scalars(select(AppUser).order_by(AppUser.email)).all()]
@router.post("/auth/demo-login")
def demo_login(payload: DemoLogin):
    token,user=login(payload.email); return {"token":token,"user":user}
@router.post("/auth/login")
def password_login(payload: LoginRequest):
    token, user = login_with_password(payload.email, payload.password)
    return {"token": token, "user": user}
@router.post("/auth/register")
def register(payload: RegisterRequest):
    token, user = register_account(payload)
    return {"token": token, "user": user}
@router.post("/policies/search")
def policy_search(payload: AskRequest):
    user=current_user(payload.token); answer,policies=search_policies(user,payload.question); return {"answer":answer,"policies":policies}
@router.post("/spend-check")
def spend_check(payload: SpendCheckRequest): return {"approvals":evaluate_spend(current_user(payload.token),payload)}
@router.get("/audits",response_model=list[AuditView])
def audits(): return recent_audits()
