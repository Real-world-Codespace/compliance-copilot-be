import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from .auth import current_user, login_with_password, register_account
from .config import MAX_UPLOAD_SIZE_MB, S3_BUCKET
from .database import KnowledgeDocument, SessionLocal
from .extractor import SUPPORTED_EXTENSIONS
from .ingestion import process_document
from .rag import ingest_text
from .schemas import AskRequest, AuditView, IngestRequest, LoginRequest, RegisterRequest, SecureAnswer, SpendCheckRequest
from .services import answer_question, evaluate_spend, recent_audits
from .storage import get_storage

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok", "service": "enterprise-secure-knowledge-hub"}


@router.post("/auth/login")
def password_login(payload: LoginRequest):
    token, user = login_with_password(payload.email, payload.password)
    return {"token": token, "user": user}


@router.post("/auth/register")
def register(payload: RegisterRequest):
    token, user = register_account(payload)
    return {"token": token, "user": user}


@router.post("/knowledge/ask", response_model=SecureAnswer)
def ask_knowledge(payload: AskRequest):
    return answer_question(current_user(payload.token), payload.question)


@router.post("/admin/knowledge/ingest")
def ingest_knowledge(payload: IngestRequest):
    user = current_user(payload.token)
    if "workspace_admin" not in user.roles:
        raise HTTPException(403, "Chỉ workspace admin được nạp tri thức")
    document_id = ingest_text(user, payload.title, payload.content, payload.classification, payload.allowed_departments, payload.allowed_roles)
    return {"document_id": document_id, "status": "indexed"}


@router.post("/admin/documents", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    token: str = Form(...),
    title: str = Form(...),
    classification: str = Form("internal"),
    allowed_departments: str = Form("operations"),
    allowed_roles: str = Form("requester"),
    file: UploadFile = File(...),
):
    user = current_user(token)
    if "workspace_admin" not in user.roles:
        raise HTTPException(403, "Chỉ workspace admin được tải tài liệu")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Chỉ hỗ trợ PDF có text, DOCX và TXT.")
    content = await file.read()
    if not content or len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"Tệp phải có nội dung và không vượt {MAX_UPLOAD_SIZE_MB} MB.")
    if not S3_BUCKET:
        raise HTTPException(503, "S3_BUCKET chưa được cấu hình cho môi trường này.")
    document_id = f"doc-{uuid.uuid4().hex[:16]}"
    filename = Path(file.filename or f"document{extension}").name
    storage_key = f"tenants/{user.organization_id}/documents/{document_id}/original/{filename}"
    get_storage().upload(storage_key, content, file.content_type or "application/octet-stream")
    document = KnowledgeDocument(
        id=document_id, organization_id=user.organization_id, title=title.strip(), source_type="file",
        classification=classification, allowed_departments=[item.strip() for item in allowed_departments.split(",") if item.strip()],
        allowed_roles=[item.strip() for item in allowed_roles.split(",") if item.strip()], created_by=user.id,
        original_filename=filename, content_type=file.content_type or "application/octet-stream", file_size=len(content),
        checksum=hashlib.sha256(content).hexdigest(), storage_key=storage_key, status="uploaded",
        status_message="Tệp đã lưu S3, đang chờ worker tạo embeddings.", created_at=datetime.now(UTC),
    )
    with SessionLocal() as session:
        session.add(document)
        session.commit()
    background_tasks.add_task(process_document, document_id)
    return {"document_id": document_id, "status": "uploaded"}


@router.post("/spend-check")
def spend_check(payload: SpendCheckRequest):
    return {"approvals": evaluate_spend(current_user(payload.token), payload)}


@router.post("/admin/audits", response_model=list[AuditView])
def audits(payload: AskRequest):
    return recent_audits(current_user(payload.token))
