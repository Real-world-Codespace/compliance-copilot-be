from fastapi.testclient import TestClient

from app.main import app
from app import storage
from app.database import KnowledgeDocument, SessionLocal


def test_upload_and_retrieve_document_locally(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "LOCAL_STORAGE_DIR", tmp_path)
    storage.get_storage.cache_clear()
    try:
        with TestClient(app) as client:
            login = client.post("/api/auth/login", json={"email": "lan.procurement@acme.example", "password": "demo-password"})
            assert login.status_code == 200
            token = login.json()["token"]
            result = client.post("/api/admin/documents", data={
                "token": token, "title": "Notebook policy", "classification": "internal",
                "allowed_departments": "procurement", "allowed_roles": "procurement_manager",
            }, files={"file": ("policy.txt", b"Notebook approval requires an equipment manager and the unique code MONSOON421.", "text/plain")})
            assert result.status_code == 202
            with SessionLocal() as session:
                document = session.get(KnowledgeDocument, result.json()["document_id"])
                assert document.status == "ready", document.status_message
            answer = client.post("/api/knowledge/ask", json={"token": token, "question": "MONSOON421"})
            assert answer.status_code == 200
            assert any(item["document_id"] == result.json()["document_id"] for item in answer.json()["citations"])
            with SessionLocal() as session:
                document = session.get(KnowledgeDocument, result.json()["document_id"])
                document.status = "failed"
                session.commit()
            answer = client.post("/api/knowledge/ask", json={"token": token, "question": "MONSOON421"})
            assert not any(item["document_id"] == result.json()["document_id"] for item in answer.json()["citations"])
    finally:
        storage.get_storage.cache_clear()
