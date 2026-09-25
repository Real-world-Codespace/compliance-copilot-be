from fastapi.testclient import TestClient

from app.main import app


def test_engineering_user_never_receives_procurement_only_citation():
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "quang.engineering@acme.example", "password": "demo-password"},
        )
        response = client.post(
            "/api/knowledge/ask",
            json={"token": login.json()["token"], "question": "Quy trình thẩm định nhà cung cấp mới là gì?"},
        )

    assert response.status_code == 200
    titles = [citation["title"] for citation in response.json()["citations"]]
    assert "Supplier Due Diligence Standard" not in titles
    assert "Procurement Approval Matrix 2026" not in titles
