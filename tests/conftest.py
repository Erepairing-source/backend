import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
import os

# Test database URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/erepairing_test")

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine"""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create a fresh database session for each test"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(test_db):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def auth_headers(client):
    """Create authenticated user and return headers"""
    # Create test user
    user_data = {
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "phone": "+919999999999",
        "role": "customer"
    }
    response = client.post("/api/v1/auth/register", json=user_data)
    if response.status_code != 200:
        # User might already exist
        pass
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return {}
