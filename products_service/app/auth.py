# auth.py
import requests

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import SECRET_KEY
from app import logger


AUTH_SERVICE_URL = "http://auth_service:8000"
ALGORITHM = "HS256"
ROLE_ORDER = {"customer": 0, "operator": 1, "admin": 2}


def _decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("token_type")
        if token_type not in (None, "access"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token or unauthorized access",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token or unauthorized access",
            )

        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or unauthorized access",
        )


def verify_token_in_other_service(token: str, require_admin: bool = False, minimum_role: str = "customer"):
    payload = _decode_access_token(token)
    user_id = payload.get("sub")
    if require_admin:
        minimum_role = "operator"

    headers = {"Content-Type": "application/json"}
    response = requests.post(
        f"{AUTH_SERVICE_URL}/verify-token",
        json={"token": token},
        headers=headers,
        timeout=5,
    )
    try:
        response_data = response.json()
    except ValueError:
        response_data = {}

    if response.status_code != 200 or not response_data.get("valid"):
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or unauthorized access",
        )

    role = response_data.get("role", "customer")
    if ROLE_ORDER.get(role, -1) < ROLE_ORDER.get(minimum_role, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {minimum_role} access",
        )

    return {"user_id": response_data.get("user_id", user_id), "role": role}
