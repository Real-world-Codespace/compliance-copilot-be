import bcrypt
from datetime import UTC, datetime
from sqlalchemy import inspect, select, text
from .database import AppUser, Base, DocumentChunk, KnowledgeDocument, Organization, PolicyDocument, SessionLocal, engine
from .rag import chunk_text, embed

POLICIES = [
 {"id":"proc-approval","title":"Procurement Approval Matrix 2026","category":"approval","classification":"internal","allowed_departments":["procurement","finance","operations"],"allowed_roles":["requester","procurement_manager","finance_manager"],"content":"Mua sắm dưới 20 000 000 VND cần Budget Owner. Từ 20 000 000 đến dưới 100 000 000 VND cần Procurement Manager và Budget Owner. Từ 100 000 000 VND trở lên cần Finance Manager; trên 500 000 000 VND cần CFO. Hợp đồng từ 12 tháng cần Legal review trước khi ký."},
 {"id":"supplier-onboarding","title":"Supplier Due Diligence Standard","category":"supplier","classification":"confidential","allowed_departments":["procurement","finance"],"allowed_roles":["procurement_manager","finance_manager"],"content":"Nhà cung cấp mới phải hoàn tất tax ID verification, bank account validation và sanctions screening trước purchase order đầu tiên. Nhà cung cấp xử lý dữ liệu cá nhân cần DPA và đánh giá bảo mật."},
 {"id":"software-spend","title":"Software Subscription Policy","category":"software","classification":"internal","allowed_departments":["engineering","operations","finance","procurement"],"allowed_roles":["requester","procurement_manager","finance_manager"],"content":"Mọi phần mềm SaaS có dữ liệu doanh nghiệp phải được IT Security review. Hợp đồng tự gia hạn cần thông báo Procurement trước 60 ngày. Không dùng thẻ cá nhân cho subscription vượt 10 000 000 VND mỗi tháng."},
 {"id":"travel-policy","title":"Travel and Expense Policy","category":"travel","classification":"internal","allowed_departments":["all"],"allowed_roles":["requester","finance_manager"],"content":"Công tác cần quản lý trực tiếp phê duyệt trước khi đặt dịch vụ. Chi phí trên 2 000 000 VND cần hóa đơn hợp lệ. Ngoại lệ hạn mức khách sạn cần Finance approval."},
]

USERS = [
 {"id":"u-lan","organization_id":"acme-retail","name":"Lan Nguyen","email":"lan.procurement@acme.example","department":"procurement","roles":["requester","procurement_manager","workspace_admin"]},
 {"id":"u-minh","organization_id":"acme-retail","name":"Minh Tran","email":"minh.finance@acme.example","department":"finance","roles":["requester","finance_manager"]},
 {"id":"u-quang","organization_id":"acme-retail","name":"Quang Le","email":"quang.engineering@acme.example","department":"engineering","roles":["requester"]},
 {"id":"u-orion","organization_id":"orion-health","name":"Hoa Vo","email":"hoa.finance@orion.example","department":"finance","roles":["requester","finance_manager"]},
]

def initialize_database():
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    # Compatibility columns for local databases created by earlier project iterations.
    document_columns = {
        "original_filename": "VARCHAR(255)", "content_type": "VARCHAR(120)", "file_size": "INTEGER",
        "checksum": "VARCHAR(64)", "storage_key": "VARCHAR(1000)", "status": "VARCHAR(30)",
        "status_message": "TEXT",
    }
    existing_document_columns = {column["name"] for column in inspect(engine).get_columns("knowledge_documents")}
    with engine.begin() as connection:
        for name, definition in document_columns.items():
            if name not in existing_document_columns:
                connection.execute(text(f"ALTER TABLE knowledge_documents ADD COLUMN {name} {definition}"))
        existing_chunk_columns = {column["name"] for column in inspect(engine).get_columns("document_chunks")}
        if "page_number" not in existing_chunk_columns:
            connection.execute(text("ALTER TABLE document_chunks ADD COLUMN page_number INTEGER"))
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx "
                "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
            ))
    # Lightweight compatibility migration for local databases created before password auth.
    if "password_hash" not in {column["name"] for column in inspect(engine).get_columns("app_users")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE app_users ADD COLUMN password_hash VARCHAR(255)"))
    with SessionLocal() as session:
        if session.scalar(select(Organization.id).limit(1)) is None:
            session.add_all([Organization(id="acme-retail", name="Acme Retail"), Organization(id="orion-health", name="Orion Health")])
            session.add_all([AppUser(**item, password_hash=bcrypt.hashpw(b"demo-password", bcrypt.gensalt()).decode()) for item in USERS])
            session.add_all([PolicyDocument(organization_id="acme-retail", **item) for item in POLICIES])
            session.commit()
        else:
            for user in session.scalars(select(AppUser).where(AppUser.password_hash.is_(None))).all():
                user.password_hash = bcrypt.hashpw(b"demo-password", bcrypt.gensalt()).decode()
            lan = session.get(AppUser, "u-lan")
            if lan and "workspace_admin" not in lan.roles:
                lan.roles = [*lan.roles, "workspace_admin"]
            session.commit()
        # Existing policy seed is copied into secure chunks once. Every chunk retains its ACL metadata.
        if session.scalar(select(DocumentChunk.id).limit(1)) is None:
            policies = session.scalars(select(PolicyDocument)).all()
            for policy in policies:
                document_id = f"knowledge-{policy.id}"
                session.add(KnowledgeDocument(
                    id=document_id, organization_id=policy.organization_id, title=policy.title,
                    source_type="policy", classification=policy.classification,
                    allowed_departments=policy.allowed_departments, allowed_roles=policy.allowed_roles,
                    created_by="system", created_at=datetime.now(UTC),
                ))
                for position, content in enumerate(chunk_text(policy.content)):
                    session.add(DocumentChunk(
                        id=f"chunk-{policy.id}-{position}", document_id=document_id,
                        organization_id=policy.organization_id, position=position, content=content,
                        embedding=embed(content), allowed_departments=policy.allowed_departments,
                        allowed_roles=policy.allowed_roles, classification=policy.classification,
                    ))
            session.commit()
