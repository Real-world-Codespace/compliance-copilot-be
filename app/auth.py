from datetime import UTC, datetime, timedelta
import jwt
import bcrypt
from fastapi import HTTPException
from sqlalchemy import select
from .config import JWT_SECRET
from .database import AppUser, Organization, PolicyDocument, SessionLocal
from .schemas import RegisterRequest, UserView
from .seed import POLICIES
from .rag import ingest_text
import uuid

def to_view(user: AppUser) -> UserView:
    return UserView(id=user.id, name=user.name, email=user.email, organization_id=user.organization_id, department=user.department, roles=user.roles)

def login_with_password(email: str, password: str) -> tuple[str, UserView]:
    with SessionLocal() as session:
        user = session.scalar(select(AppUser).where(AppUser.email == email.lower()))
    if not user or not user.password_hash or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    return jwt.encode({"sub": user.id, "exp": datetime.now(UTC) + timedelta(hours=4)}, JWT_SECRET, algorithm="HS256"), to_view(user)


def register_account(payload: RegisterRequest) -> tuple[str, UserView]:
    with SessionLocal() as session:
        if session.scalar(select(AppUser).where(AppUser.email == payload.email.lower())):
            raise HTTPException(409, "Email đã được sử dụng")
        organization_id = f"org-{uuid.uuid4().hex[:12]}"
        user = AppUser(id=f"usr-{uuid.uuid4().hex[:12]}", organization_id=organization_id, name=payload.name,
                       email=payload.email.lower(), department="operations", roles=["requester", "workspace_admin"],
                       password_hash=bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode())
        session.add(Organization(id=organization_id, name=payload.organization_name))
        session.add(user)
        session.add_all([
            PolicyDocument(id=f"{organization_id}-{item['id']}", organization_id=organization_id,
                           title=item["title"], category=item["category"], classification=item["classification"],
                           allowed_departments=item["allowed_departments"], allowed_roles=item["allowed_roles"],
                           content=item["content"])
            for item in POLICIES
        ])
        session.commit()
    user_view = to_view(user)
    for policy in POLICIES:
        ingest_text(
            user_view, policy["title"], policy["content"], policy["classification"],
            policy["allowed_departments"], policy["allowed_roles"],
        )
    return jwt.encode({"sub": user.id, "exp": datetime.now(UTC) + timedelta(hours=4)}, JWT_SECRET, algorithm="HS256"), user_view

def current_user(token: str) -> UserView:
    try: user_id = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError as error: raise HTTPException(401, "Token không hợp lệ") from error
    with SessionLocal() as session: user = session.get(AppUser, user_id)
    if not user: raise HTTPException(401, "User không tồn tại")
    return to_view(user)
