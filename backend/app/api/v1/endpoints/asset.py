# backend/app/api/v1/endpoints/asset.py
"""
TEMPORARY SHIM: Placeholder for asset endpoint to avoid import errors.
TODO: Implement actual asset logic or remove if not needed.
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/asset/_placeholder")
async def placeholder_asset():
    """
    TEMPORARY PLACEHOLDER endpoint.
    """
    return {
        "message": "asset endpoint placeholder",
        "note": "Implement actual asset logic here"
    }
