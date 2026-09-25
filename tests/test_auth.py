from fastapi.testclient import TestClient

from app.main import app


def test_seed_user_can_login_with_password():
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": "lan.procurement@acme.example", "password": "demo-password"},
        )

    assert response.status_code == 200
    assert response.json()["user"]["organization_id"] == "acme-retail"
