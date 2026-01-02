from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pathlib import Path
import os

router = APIRouter()

@router.post("/upload-image", status_code=status.HTTP_201_CREATED)
async def upload_image(file: UploadFile = File(...)):
    UPLOAD_DIR = Path("uploads")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    allowed = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Tipo de arquivo não permitido")

    filename = os.path.basename(file.filename)
    dest = UPLOAD_DIR / filename

    # evita sobrescrever
    counter = 1
    base, ext = os.path.splitext(filename)
    while dest.exists():
        filename = f"{base}_{counter}{ext}"
        dest = UPLOAD_DIR / filename
        counter += 1

    with dest.open("wb") as f:
        content = await file.read()
        f.write(content)

    return {"filename": filename, "path": f"/uploads/{filename}"}