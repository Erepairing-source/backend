"""
Security utilities for authentication and authorization
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings

# Initialize password context with explicit bcrypt configuration
try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    # Test bcrypt initialization
    test_hash = pwd_context.hash("test")
    print("[OK] Password context initialized successfully")
except Exception as e:
    print(f"[ERROR] Password context initialization failed: {str(e)}")
    import traceback
    traceback.print_exc()
    raise
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        if not plain_password or not hashed_password:
            return False
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        import traceback
        print(f"Error in verify_password: {str(e)}")
        print(traceback.format_exc())
        raise


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


# Placeholder hash for users who have not set password yet (signup → email link flow).
# Login rejects users whose password_hash equals this.
PENDING_PASSWORD_PLACEHOLDER = "PENDING_SET_PASSWORD"


def get_pending_password_hash() -> str:
    """Return hash used for users who must set password via email link."""
    return get_password_hash(PENDING_PASSWORD_PLACEHOLDER)


def is_pending_password(user_password_hash: str) -> bool:
    """Return True if user has not set password yet (placeholder hash)."""
    if not user_password_hash:
        return True
    try:
        return pwd_context.verify(PENDING_PASSWORD_PLACEHOLDER, user_password_hash)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user_token(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current user from token (sync so callers using def routes run in thread pool)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    return payload




