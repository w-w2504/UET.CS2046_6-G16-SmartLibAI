from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "catalog_ready" in data
    assert "search_ready" in data
    assert "recommend_ready" in data
    assert "rag_ready" in data
    assert "request_id" in data
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] == data["request_id"]


def test_404_error_envelope():
    response = client.get("/api/v1/non_existent_route")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "resource_not_found"
    assert "request_id" in data
    assert "X-Request-ID" in response.headers

