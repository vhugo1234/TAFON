from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Tuple
from datetime import datetime, date
import os
import re
import base64
import hashlib
import uuid
import logging
from io import BytesIO
from PIL import Image, UnidentifiedImageError

from app.api.deps_tenant import get_tenant_db_session
from app.schemas.attendance_schema import AttendanceCreate, AttendanceOut

router = APIRouter(tags=["Attendance"])

logger = logging.getLogger("attendance")

# Configuráveis via ENV
SIGNATURE_UPLOAD_DIR = os.environ.get("SIGNATURE_UPLOAD_DIR", "uploads/signatures")
# normalize to absolute path to avoid surprises
SIGNATURE_UPLOAD_DIR = os.path.abspath(SIGNATURE_UPLOAD_DIR)
MAX_SIG_BYTES = int(os.environ.get("SIG_MAX_BYTES", str(2 * 1024 * 1024)))  # 2MB
MAX_SIG_W = int(os.environ.get("SIG_MAX_WIDTH_PX", "1200"))
MAX_SIG_H = int(os.environ.get("SIG_MAX_HEIGHT_PX", "400"))

# data URI regex (captures mime, base64 indicator and data)
_DATA_URI_RE = re.compile(
    r"^data:(?P<mime>[\w/\-\.]+)(;charset=[\w-]+)?(?P<base64>;base64)?,(?P<data>.+)$",
    re.I | re.S,
)

# Dependência de autenticação — ajuste para a sua implementação real
try:
    from app.api.deps import get_current_user
except Exception:
    def get_current_user():
        return None

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _save_data_uri_image(data_uri: str, tenant_dir: str, prefix: str) -> Tuple[str, str]:
    """
    Decode data URI, validate, normalize (Pillow), save PNG, return (relative_path, sha256).
    The returned path is relative to the SIGNATURE_UPLOAD_DIR root (tenant_dir/filename.png).
    """
    if not data_uri:
        raise ValueError("data URI vazia")

    m = _DATA_URI_RE.match(data_uri)
    if not m:
        raise ValueError("data URI inválida")

    data_b64 = m.group("data")
    try:
        img_bytes = base64.b64decode(data_b64)
    except Exception as e:
        raise ValueError("base64 inválido") from e

    if len(img_bytes) > MAX_SIG_BYTES:
        raise ValueError(f"Imagem excede limite de {MAX_SIG_BYTES} bytes")

    # open image with Pillow
    try:
        img = Image.open(BytesIO(img_bytes))
    except UnidentifiedImageError:
        raise ValueError("Imagem inválida / formato não suportado")
    except Exception as e:
        logger.exception("Erro ao abrir imagem")
        raise ValueError("Erro ao abrir imagem") from e

    # normalize mode
    try:
        if img.mode not in ("RGBA", "RGB"):
            # prefer RGBA if palette or transparency
            img = img.convert("RGBA" if img.mode == "P" else "RGB")
    except Exception:
        img = img.convert("RGBA")

    # resize preserving aspect ratio if needed
    iw, ih = img.size
    if iw == 0 or ih == 0:
        raise ValueError("Imagem com dimensão inválida")

    scale = min(1.0, float(MAX_SIG_W) / iw if iw else 1.0, float(MAX_SIG_H) / ih if ih else 1.0)
    if scale < 1.0:
        # Pillow >= 10 uses Resampling, fallback to ANTIALIAS for older versions
        try:
            resample = Image.Resampling.LANCZOS  # type: ignore
        except Exception:
            resample = Image.ANTIALIAS  # type: ignore
        new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
        img = img.resize(new_size, resample)

    # ensure tenant directory exists
    tenant_path = os.path.join(SIGNATURE_UPLOAD_DIR, tenant_dir)
    _ensure_dir(tenant_path)

    # use uuid to avoid collisions; keep png extension
    filename = f"{prefix}_{uuid.uuid4().hex}.png"
    save_path = os.path.join(tenant_path, filename)

    # write PNG to buffer then to disk (to ensure consistent storage and compute hash)
    out_buf = BytesIO()
    try:
        if img.mode == "RGBA":
            img.save(out_buf, format="PNG")
        else:
            img.convert("RGB").save(out_buf, format="PNG")
    except Exception as e:
        logger.exception("Erro ao salvar imagem em buffer")
        raise ValueError("Erro ao processar imagem") from e

    content = out_buf.getvalue()
    try:
        with open(save_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.exception("Erro ao escrever arquivo de assinatura em disco: %s", save_path)
        raise ValueError("Falha ao salvar arquivo no servidor (permissões?)") from e

    sig_hash = hashlib.sha256(content).hexdigest()

    # store relative path that can be later converted for serving / URLs
    rel_path = os.path.join(tenant_dir, filename).replace("\\", "/")
    # log saved file for easier debugging
    logger.debug("Saved signature file: %s (rel: %s)", save_path, rel_path)
    return rel_path, sig_hash

# Helper: normalize stored DB path into a public path served by StaticFiles (/uploads/...)
def _public_path_for_saved_signature(rel_path: Optional[str]) -> Optional[str]:
    """
    Normaliza o caminho salvo no DB para a rota pública que o StaticFiles monta.
    - Se rel_path é absoluto/começa com /uploads ou uploads/ ou http(s) -> retorna tal qual (com leading slash)
    - Se rel_path é algo como 'mb1/filename.png' -> transforma em '/uploads/signatures/mb1/filename.png'
    - Retorna string com forward slashes e leading slash where applicable
    """
    if not rel_path:
        return None
    p = str(rel_path).strip()
    # already absolute URL?
    if p.startswith("http://") or p.startswith("https://"):
        return p
    # already prefixed with /uploads
    if p.startswith("/uploads"):
        return p
    # already prefixed with uploads/ (relative)
    if p.startswith("uploads/"):
        return "/" + p  # ensure leading slash
    # if the path contains 'signatures/' at start, map to /uploads/signatures/...
    if p.startswith("signatures/"):
        return "/uploads/" + p
    # common case: 'mb1/filename.png' (tenant/filename) -> stored under uploads/signatures/<tenant>/filename
    return "/uploads/signatures/" + p.lstrip("/")

@router.post("/event/{event_id}/worker/{worker_id}/attendance/checkin", response_model=AttendanceOut)
def attendance_checkin(
    event_id: int,
    worker_id: int,
    payload: AttendanceCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user = Depends(get_current_user)
):
    """
    Check-in do worker: recebe signature_data (data URI) e opcional photo_data, lat/lng.
    Cria um registro em event_worker_attendance (attendance_date = payload.date or today).
    """
    logger.debug("Checkin request: event_id=%s worker_id=%s payload_signature_len=%s photo_len=%s", event_id, worker_id,
                 len(payload.signature_data or ""), len(payload.photo_data or ""))

    # buscar event_worker para recuperar user_id (se houver)
    try:
        ev_worker_row = db.execute(text("SELECT id, user_id FROM event_workers WHERE id = :id"), {"id": worker_id})
        ev_worker = ev_worker_row.mappings().first()
    except Exception as e:
        logger.exception("Erro ao consultar event_workers")
        raise HTTPException(status_code=500, detail="Erro ao consultar event_worker")

    if not ev_worker:
        raise HTTPException(status_code=404, detail="Event worker não encontrado")

    user_id = ev_worker.get("user_id")

    # determine tenant/schema name for storing file (search_path adjusted by session)
    schema_name = None
    try:
        sp = db.execute(text("SHOW search_path")).fetchone()
        if sp and sp[0]:
            schema_name = str(sp[0]).split(',')[0].strip().strip('"')
    except Exception:
        schema_name = None
    tenant_dir = schema_name or "default"

    # save signature (data URI) — may raise ValueError
    try:
        sig_rel_path, sig_hash = _save_data_uri_image(payload.signature_data, tenant_dir, f"attendance_sig_w{worker_id}")
    except ValueError as e:
        logger.warning("Signature validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Erro inesperado ao salvar assinatura")
        raise HTTPException(status_code=500, detail="Erro ao salvar assinatura")

    photo_rel_path = None
    if payload.photo_data:
        try:
            photo_rel_path, _ = _save_data_uri_image(payload.photo_data, tenant_dir, f"attendance_photo_w{worker_id}")
        except ValueError as e:
            logger.warning("Photo validation failed: %s", e)
            raise HTTPException(status_code=400, detail=f"photo_data inválida: {e}")
        except Exception:
            logger.exception("Erro inesperado ao salvar foto")
            raise HTTPException(status_code=500, detail="Erro ao salvar foto")

    attendance_date = payload.date or date.today()
    now = datetime.utcnow()

    # Insert row and return it
    try:
        ins = text("""
            INSERT INTO event_worker_attendance
              (event_id, event_worker_id, user_id, attendance_date, check_in_at, check_in_signature_path, check_in_signature_hash, check_in_photo_path, check_in_lat, check_in_lng, status, created_at, updated_at)
            VALUES
              (:event_id, :event_worker_id, :user_id, :attendance_date, :check_in_at, :sig_path, :sig_hash, :photo_path, :lat, :lng, :status, :now, :now)
            RETURNING *
        """)
        params = {
            "event_id": event_id,
            "event_worker_id": worker_id,
            "user_id": user_id,
            "attendance_date": attendance_date,
            "check_in_at": now,
            "sig_path": sig_rel_path,
            "sig_hash": sig_hash,
            "photo_path": photo_rel_path,
            "lat": payload.lat,
            "lng": payload.lng,
            "status": "checked_in",
            "now": now
        }
        result = db.execute(ins, params)
        # Use mappings() for SQLAlchemy result to get a dict-like mapping
        new_row = result.mappings().first()
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Erro ao persistir attendance: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao persistir attendance")

    if not new_row:
        raise HTTPException(status_code=500, detail="Não foi possível criar attendance")

    # Convert to dict and return Pydantic model
    try:
        as_dict = dict(new_row)
    except Exception:
        # mappings() already returns mapping -> but fallback
        as_dict = {k: new_row[k] for k in new_row.keys()}

    # Normalize paths for client responses (do not modify DB)
    try:
        as_dict["check_in_signature_path"] = _public_path_for_saved_signature(as_dict.get("check_in_signature_path"))
        as_dict["check_in_photo_path"] = _public_path_for_saved_signature(as_dict.get("check_in_photo_path"))
    except Exception:
        logger.exception("Erro ao normalizar paths para response")

    return AttendanceOut(**as_dict)

@router.post("/event/{event_id}/worker/{worker_id}/attendance/{attendance_id}/checkout", response_model=AttendanceOut)
def attendance_checkout(
    event_id: int,
    worker_id: int,
    attendance_id: int,
    db: Session = Depends(get_tenant_db_session),
    current_user = Depends(get_current_user)
):
    now = datetime.utcnow()
    try:
        rec = db.execute(
            text("SELECT id FROM event_worker_attendance WHERE id = :id AND event_id = :event_id AND event_worker_id = :worker_id"),
            {"id": attendance_id, "event_id": event_id, "worker_id": worker_id}
        ).fetchone()
    except Exception:
        logger.exception("Erro ao consultar attendance para checkout")
        raise HTTPException(status_code=500, detail="Erro ao consultar attendance")

    if not rec:
        raise HTTPException(status_code=404, detail="Attendance not found")

    try:
        upd = text("UPDATE event_worker_attendance SET check_out_at = :now, status = :status, updated_at = :now WHERE id = :id RETURNING *")
        r = db.execute(upd, {"now": now, "status": "checked_out", "id": attendance_id})
        db.commit()
        rec2 = r.mappings().first()
    except Exception as e:
        db.rollback()
        logger.exception("Erro ao atualizar checkout: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao atualizar checkout")

    # normalize paths for response
    try:
        row = dict(rec2)
        row["check_in_signature_path"] = _public_path_for_saved_signature(row.get("check_in_signature_path"))
        row["check_in_photo_path"] = _public_path_for_saved_signature(row.get("check_in_photo_path"))
    except Exception:
        logger.exception("Erro ao normalizar paths no checkout response")
        row = dict(rec2)

    return AttendanceOut(**row)

@router.get("/event/{event_id}/attendance", response_model=List[AttendanceOut])
def list_attendance(event_id: int, attendance_date: Optional[date] = None, db: Session = Depends(get_tenant_db_session)):
    if attendance_date:
        rows = db.execute(
            text("SELECT * FROM event_worker_attendance WHERE event_id = :event_id AND attendance_date = :d ORDER BY check_in_at"),
            {"event_id": event_id, "d": attendance_date}
        ).mappings().all()
    else:
        rows = db.execute(
            text("SELECT * FROM event_worker_attendance WHERE event_id = :event_id ORDER BY attendance_date DESC, check_in_at DESC"),
            {"event_id": event_id}
        ).mappings().all()
    results = []
    for r in rows:
        row = dict(r)
        # normalize stored paths for serving (do not alter DB)
        try:
            row["check_in_signature_path"] = _public_path_for_saved_signature(row.get("check_in_signature_path"))
            row["check_in_photo_path"] = _public_path_for_saved_signature(row.get("check_in_photo_path"))
        except Exception:
            logger.exception("Erro ao normalizar paths para list response")
        results.append(AttendanceOut(**row))
    return results
