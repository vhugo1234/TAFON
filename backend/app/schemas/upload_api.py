from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from pathlib import Path
import os
from typing import Any

# Dependência opcional para restringir upload a usuários autenticados/admins
try:
    from app.core.security import get_current_active_superuser
except Exception:
    def get_current_active_superuser() -> Any:  # type: ignore
        return None

router = APIRouter()


@router.post("/upload-image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    _admin=Depends(get_current_active_superuser),
):
    UPLOAD_DIR = Path("uploads")
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao criar pasta de upload: {e}")

    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Tipo de arquivo não permitido: {file.content_type}")

    filename = os.path.basename(file.filename)
    dest = UPLOAD_DIR / filename

    counter = 1
    base, ext = os.path.splitext(filename)
    while dest.exists():
        filename = f"{base}_{counter}{ext}"
        dest = UPLOAD_DIR / filename
        counter += 1

    try:
        with dest.open("wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar arquivo: {e}")

    return {"filename": filename, "path": f"/uploads/{filename}"}