# backend/app/api/v1/endpoints/password_reset.py
"""
TEMPORARY SHIM: Password reset endpoints to avoid import errors.
TODO: Implement proper password reset logic with email/tokens.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter()


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


@router.post("/request")
async def request_password_reset(request: PasswordResetRequest):
    """
    Request a password reset (sends email with token).
    TEMPORARY SHIM: Returns stub response.
    """
    return {
        "message": "Password reset request received",
        "email": request.email,
        "status": "pending",
        "note": "STUB: Email sending not implemented yet"
    }


@router.post("/confirm")
async def confirm_password_reset(reset: PasswordResetConfirm):
    """
    Confirm password reset with token and new password.
    TEMPORARY SHIM: Returns stub response.
    """
    return {
        "message": "Password reset confirmed",
        "status": "success",
        "note": "STUB: Password update not implemented yet"
    }
