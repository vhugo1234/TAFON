# backend/app/api/deps.py
from typing import Dict, Any
from fastapi import Depends
from app.core.security import oauth2_scheme, decode_token


def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Dependency to get the current user from JWT token.
    Returns the decoded token payload as a dict.
    TEMPORARY FIX: Can be expanded to fetch full user object from DB if needed.
    """
    payload = decode_token(token)
    return payload
