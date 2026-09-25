from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class DemoLogin(BaseModel):
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=160)
    name: str = Field(min_length=2, max_length=160)
    email: str
    password: str = Field(min_length=8, max_length=128)


class UserView(BaseModel):
    id: str
    name: str
    email: str
    organization_id: str
    department: str
    roles: list[str]


class PolicyView(BaseModel):
    id: str
    title: str
    category: str
    classification: str
    score: float
    decision: Literal["allowed", "denied"]
    reason: str
    excerpt: str | None = None


class AskRequest(BaseModel):
    token: str
    question: str = Field(min_length=3, max_length=1000)


class SpendCheckRequest(BaseModel):
    token: str
    supplier: str = Field(min_length=2, max_length=160)
    category: Literal["software", "marketing", "professional_services", "office", "travel"]
    amount_vnd: Decimal = Field(gt=0)
    contract_months: int = Field(ge=0, le=60)


class ApprovalStep(BaseModel):
    role: str
    reason: str


class AuditView(BaseModel):
    created_at: str
    actor_email: str
    action: str
    resource: str
    outcome: str
