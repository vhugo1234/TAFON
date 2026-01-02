# backend/app/api/v1/endpoints/emprestimos.py
"""
TEMPORARY SHIM: Placeholder for emprestimos endpoint to avoid import errors.
TODO: Implement actual emprestimos logic or remove if not needed.
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/emprestimos/_placeholder")
async def placeholder_emprestimos():
    """
    TEMPORARY PLACEHOLDER endpoint.
    """
    return {
        "message": "emprestimos endpoint placeholder",
        "note": "Implement actual emprestimos logic here"
    }
