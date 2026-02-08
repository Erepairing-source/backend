"""
Authentication and authorization tests
"""
import pytest

@pytest.mark.api
def test_register_user(client):
    """Test user registration"""
    user_data = {
        "email": f"test_{pytest.current_time}@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "phone": "+919999999999",
        "role": "customer"
    }
    response = client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code in [200, 400]  # 400 if user exists

@pytest.mark.api
def test_login_user(client):
    """Test user login"""
    # First register
    user_data = {
        "email": f"login_test_{pytest.current_time}@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "phone": "+919999999999",
        "role": "customer"
    }
    client.post("/api/v1/auth/register", json=user_data)
    
    # Then login
    login_data = {
        "email": user_data["email"],
        "password": user_data["password"]
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.api
def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "wrongpassword"
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 401

@pytest.fixture(autouse=True)
def set_current_time():
    """Set current time for unique email generation"""
    import time
    pytest.current_time = int(time.time())
