from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.api.deps_tenant import get_tenant_db_session
import os
import re
import tempfile
import base64
import logging
from io import BytesIO
from PIL import Image, UnidentifiedImageError
import hashlib
from datetime import datetime
from typing import Optional

router = APIRouter(tags=["Coordinator Signature"])
logger = logging.getLogger(__name__)

# regex para data URI base64
_DATA_URI_RE = re.compile(r"^data:(?P<mime>[\w/\-\.]+)(;charset=[\w-]+)?(?P<base64>;base64)?,(?P<data>.+)$", re.I)

# Config (override via ENV)
SIGNATURE_UPLOAD_DIR = os.environ.get("SIGNATURE_UPLOAD_DIR", "uploads/signatures")
MAX_WIDTH = int(os.environ.get("SIG_MAX_WIDTH_PX", "1200"))
MAX_HEIGHT = int(os.environ.get("SIG_MAX_HEIGHT_PX", "400"))
MAX_BYTES = int(os.environ.get("SIG_MAX_BYTES", str(2 * 1024 * 1024)))  # 2 MB default

class SignatureUpload(BaseModel):
    signature_data: str  # data URI (data:image/png;base64,...) - este endpoint exige dataURI no MVP

# Dependência de autenticação: substitua pela sua dependency real se tiver.
try:
    # adapta para o nome da sua dependency real (ex.: app.api.deps.get_current_user)
    from app.api.deps import get_current_user  # ajustar se o path for diferente
except Exception:
    def get_current_user():
        # fallback permissivo para ambientes de desenvolvimento: retorna None.
        # Em produção substitua por sua dependency que retorna o usuário autenticado.
        return None

@router.post("/coordinator/{coord_id}/signature")
def upload_coordinator_signature(
    coord_id: int,
    payload: SignatureUpload,
    db: Session = Depends(get_tenant_db_session),
    current_user = Depends(get_current_user)
):
    """
    Recebe signature_data (data URI base64) e salva arquivo PNG no disco (por tenant schema).
    Atualiza user_tenant.signature_path, signature_hash, signature_uploaded_at.
    - Exige signature_data em formato data URI (data:image/png;base64,...)
    - Ajuste get_current_user para sua implementação real de auth/perm.
    """
    # Permissão: recomendamos que só o próprio usuário (coord) ou admin possa alterar.
    if current_user is not None:
        try:
            cur_id = getattr(current_user, "id", None)
            is_admin = getattr(current_user, "is_admin", False)
            if cur_id != coord_id and not is_admin:
                raise HTTPException(status_code=403, detail="Sem permissão para atualizar assinatura deste coordenador")
        except HTTPException:
            raise
        except Exception:
            # se current_user não tem os campos esperados, deixamos passar para dev; em prod ajuste a dependency
            logger.debug("get_current_user retornou objeto inesperado; verifique permissão")

    s = payload.signature_data
    if not s:
        raise HTTPException(status_code=400, detail="signature_data ausente")

    # Valida data URI
    m = _DATA_URI_RE.match(s)
    if not m:
        raise HTTPException(status_code=400, detail="signature_data deve ser data URI base64 (data:image/png;base64,...)")

    mime = (m.group("mime") or "image/png").lower()
    data_b64 = m.group("data")

    try:
        img_bytes = base64.b64decode(data_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Base64 inválido")

    if len(img_bytes) > MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"Imagem muito grande (max {MAX_BYTES} bytes)")

    # tenta abrir com Pillow
    try:
        img = Image.open(BytesIO(img_bytes))
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Imagem inválida")
    except Exception as e:
        logger.exception("Erro ao abrir imagem: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao processar imagem")

    # normaliza modo e remove EXIF (salvaremos sempre PNG)
    if img.mode not in ("RGBA", "RGB"):
        img = img.convert("RGBA" if img.mode == "P" else "RGB")

    # limita dimensões (mantém proporção, sem upscaling)
    iw, ih = img.size
    scale = min(1.0, float(MAX_WIDTH) / iw if iw else 1.0, float(MAX_HEIGHT) / ih if ih else 1.0)
    if scale < 1.0:
        new_size = (int(iw * scale), int(ih * scale))
        img = img.resize(new_size, Image.ANTIALIAS)

    # determina tenant schema (para separar diretórios)
    schema_name = None
    try:
        sp = db.execute(text("SHOW search_path")).fetchone()
        if sp and sp[0]:
            schema_name = sp[0].split(',')[0].strip().strip('"')
    except Exception:
        logger.exception("Não consegui obter search_path; usando 'default'")

    tenant_dir = schema_name or "default"
    save_dir = os.path.join(SIGNATURE_UPLOAD_DIR, tenant_dir)
    os.makedirs(save_dir, exist_ok=True)

    filename = f"coordinator_{coord_id}.png"
    save_path = os.path.join(save_dir, filename)

    # salvar imagem como PNG (sem EXIF)
    try:
        out_buf = BytesIO()
        if img.mode == "RGBA":
            img.save(out_buf, format="PNG")
        else:
            img_rgb = img.convert("RGB")
            img_rgb.save(out_buf, format="PNG")
        content = out_buf.getvalue()
        with open(save_path, "wb") as f:
            f.write(content)
    except Exception:
        logger.exception("Falha ao salvar arquivo de assinatura")
        raise HTTPException(status_code=500, detail="Erro ao salvar assinatura no servidor")

    # calcular hash e persistir metadados no user_tenant do schema atual
    sig_hash = hashlib.sha256(content).hexdigest()
    now = datetime.utcnow()

    try:
        upd = text(
            "UPDATE user_tenant SET signature_path = :path, signature_hash = :h, signature_uploaded_at = :ts WHERE id = :id"
        )
        db.execute(upd, {"path": save_path, "h": sig_hash, "ts": now, "id": coord_id})
        db.commit()
    except Exception:
        logger.exception("Falha ao atualizar user_tenant com signature_path")
        raise HTTPException(status_code=500, detail="Erro ao persistir metadados da assinatura no banco")

    return {"signature_path": save_path, "signature_hash": sig_hash, "uploaded_at": now.isoformat()}
