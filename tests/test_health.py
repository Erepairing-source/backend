"""
Basic health check and API tests
"""
import pytest
from fastapi.testclient import TestClient

@pytest.mark.unit
def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

@pytest.mark.api
def test_api_root(client):
    """Test API root endpoint"""
    response = client.get("/api/v1/")
    assert response.status_code in [200, 404]  # May or may not exist

@pytest.mark.api
def test_docs_available(client):
    """Test that API docs are available"""
    response = client.get("/docs")
    assert response.status_code == 200
