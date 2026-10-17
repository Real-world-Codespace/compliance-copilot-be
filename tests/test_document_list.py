from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import KnowledgeDocument, SessionLocal
from app.main import app


def test_document_list_enforces_tenant_acl_and_processing_status():
    suffix = uuid4().hex
    ids = {name: f"test-{name}-{suffix}" for name in ("allowed", "restricted", "processing", "other")}
    common = dict(source_type="file", classification="confidential", created_by="test", created_at=datetime.now(UTC))
    with TestClient(app) as client:
        with SessionLocal() as session:
            session.add_all([
                KnowledgeDocument(id=ids["allowed"], organization_id="acme-retail", title="Engineering", allowed_departments=["engineering"], allowed_roles=["requester"], status="ready", **common),
                KnowledgeDocument(id=ids["restricted"], organization_id="acme-retail", title="Finance secret", allowed_departments=["finance"], allowed_roles=["finance_manager"], status="ready", **common),
                KnowledgeDocument(id=ids["processing"], organization_id="acme-retail", title="Processing", allowed_departments=["engineering"], allowed_roles=["requester"], status="processing", **common),
                KnowledgeDocument(id=ids["other"], organization_id="orion-health", title="Other tenant", allowed_departments=["all"], allowed_roles=["requester"], status="ready", **common),
            ])
            session.commit()
        try:
            def login(email):
                response = client.post("/api/auth/login", json={"email": email, "password": "demo-password"})
                assert response.status_code == 200
                return {"Authorization": f"Bearer {response.json()['token']}"}

            assert client.get("/api/documents").status_code == 401
            assert client.get("/api/documents", headers={"Authorization": "Bearer invalid"}).status_code == 401
            result = client.get("/api/documents", headers=login("quang.engineering@acme.example"))
            assert result.status_code == 200
            documents = result.json()
            visible = {item["id"] for item in documents}
            assert ids["allowed"] in visible
            assert not visible.intersection({ids["restricted"], ids["processing"], ids["other"]})
            assert all("storage_key" not in item and "allowed_roles" not in item for item in documents)

            result = client.get("/api/documents", headers=login("lan.procurement@acme.example"))
            assert result.status_code == 200
            visible = {item["id"] for item in result.json()}
            assert {ids["allowed"], ids["restricted"], ids["processing"]} <= visible
            assert ids["other"] not in visible
            result = client.get("/api/documents", headers=login("hoa.finance@orion.example"))
            assert ids["other"] in {item["id"] for item in result.json()}
            assert ids["allowed"] not in {item["id"] for item in result.json()}
        finally:
            with SessionLocal() as session:
                for document_id in ids.values():
                    document = session.get(KnowledgeDocument, document_id)
                    if document:
                        session.delete(document)
                session.commit()
