from fastapi import APIRouter, Depends, HTTPException, status, Body, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Any, Dict, Optional
import os
import time
import shutil

from app.db.connection import get_db
from app.db.models.tenant import UserTenant
from app.schemas.user_tenant import UserTenantCreate, UserTenantUpdate, UserTenantOut
from app.core.security import get_password_hash
from app.api.deps import get_current_user

router = APIRouter()

def get_schema_name(current_user: Any):
    if isinstance(current_user, dict):
        return current_user.get("schema_name")
    return getattr(current_user, "schema_name", None)


@router.get("/", response_model=list[UserTenantOut])
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    schema_name = get_schema_name(current_user)
    if not schema_name:
        raise HTTPException(400, "Tenant não identificado!")
    db.execute(text(f"SET search_path TO {schema_name}"))
    users = db.query(UserTenant).all()
    db.execute(text("SET search_path TO public"))
    return users

@router.post("/", response_model=UserTenantOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserTenantCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    schema_name = get_schema_name(current_user)
    if not schema_name:
        raise HTTPException(400, "Tenant não identificado!")
    db.execute(text(f"SET search_path TO {schema_name}"))
    hashed_password = get_password_hash(user_in.password)
    user_obj = UserTenant(
        nome=user_in.nome,
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password,
        cpf=user_in.cpf,
        phone=user_in.phone,
        department=user_in.department,
        institution=user_in.institution,
        birth_date=user_in.birth_date,
        notes=user_in.notes,
        address=user_in.address,
        avatar_url=user_in.avatar_url,
        specialty=user_in.specialty,
        accepted_terms=user_in.accepted_terms,
        is_active=user_in.is_active,
        is_admin=user_in.is_admin,
        role_id=user_in.role_id,
    )
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)
    db.execute(text("SET search_path TO public"))
    return user_obj

# --- UPDATED PATCH: support JSON or multipart/form-data (with optional avatar_file) ---
@router.patch("/{user_id}", response_model=UserTenantOut)
async def edit_user(
    user_id: int,
    request: Request,
    avatar_file: Optional[UploadFile] = File(None),
    user_in: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    PATCH parcial de usuário — aceita JSON body OR multipart/form-data with optional file field 'avatar_file'.

    Comportamento:
    - Se content-type for multipart/form-data, lê request.form() e trata arquivo (avatar_file).
    - Se for JSON, usa user_in.
    - Normaliza booleans vindos de form-data ("true"/"false") para valores Python.
    - Converte role_id para int quando possível.
    - Se 'password' estiver presente e não vazio, gera hashed_password.
    - Atualiza somente campos permitidos (whitelist) no objeto ORM.
    - Garante restauração do search_path e tratamento de erros com mensagens controladas.
    """
    import logging
    import traceback
    logger = logging.getLogger("uvicorn.error")

    def _to_bool(val):
        # Normaliza valores recebidos de formulários/JSON para bool/None
        if isinstance(val, bool):
            return val
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, (bytes, bytearray)):
            try:
                val = val.decode("utf-8", errors="ignore")
            except Exception:
                val = str(val)
        s = str(val).strip().lower()
        if s == "" or s in ("none", "null"):
            return None
        truthy = {"1", "true", "t", "yes", "y", "on"}
        falsy = {"0", "false", "f", "no", "n", "off"}
        if s in truthy:
            return True
        if s in falsy:
            return False
        return val

    schema_name = get_schema_name(current_user)
    if not schema_name:
        raise HTTPException(400, "Tenant não identificado!")

    # ensure we always attempt to restore search_path
    db.execute(text(f"SET search_path TO {schema_name}"))

    try:
        user_obj = db.query(UserTenant).filter(UserTenant.id == user_id).first()
        if not user_obj:
            db.execute(text("SET search_path TO public"))
            raise HTTPException(404, "Usuário não encontrado")

        update_data: Dict[str, Any] = {}

        content_type = request.headers.get("content-type", "") or ""
        logger.debug(f"[users.edit_user] content-type: {content_type}")

        # If multipart/form-data -> parse form (this includes files)
        if content_type.startswith("multipart/"):
            form = await request.form()
            logger.debug(f"[users.edit_user] form keys: {list(form.keys())}")

            # collect scalar fields from form
            for k, v in form.items():
                # skip UploadFile-like objects here
                if hasattr(v, "filename"):
                    continue
                update_data[k] = v

            # prefer explicit avatar_file param (FastAPI fills it) otherwise check form
            file_obj = avatar_file or form.get("avatar_file")
            if file_obj and getattr(file_obj, "filename", None):
                logger.debug(f"[users.edit_user] received file: {file_obj.filename}")
                upload_dir = os.path.join("uploads", "avatars")
                os.makedirs(upload_dir, exist_ok=True)
                ts = int(time.time())
                # safe filename: include schema and timestamp
                safe_name = f"{schema_name}_{ts}_{os.path.basename(file_obj.filename)}"
                dest_path = os.path.join(upload_dir, safe_name)
                try:
                    # Ensure file pointer at start
                    try:
                        file_obj.file.seek(0)
                    except Exception:
                        pass
                    with open(dest_path, "wb") as buffer:
                        shutil.copyfileobj(file_obj.file, buffer)
                    # stored path for serving by StaticFiles mounted at /uploads
                    update_data["avatar_url"] = f"/uploads/avatars/{safe_name}"
                except Exception as e:
                    logger.error(f"[users.edit_user] failed to save uploaded file: {e}\n{traceback.format_exc()}")
                    raise HTTPException(status_code=500, detail=f"Falha ao salvar avatar: {e}")
        else:
            # JSON body path (user_in provided via Body)
            if user_in:
                logger.debug(f"[users.edit_user] json body keys: {list(user_in.keys())}")
                update_data = dict(user_in)
            else:
                update_data = {}

        # Normalize boolean-like fields coming from form-data
        for bool_key in ("accepted_terms", "is_active", "is_admin"):
            if bool_key in update_data:
                converted = _to_bool(update_data[bool_key])
                if converted is None:
                    # treat empty/null as "not provided" -> remove key
                    update_data.pop(bool_key, None)
                else:
                    update_data[bool_key] = bool(converted)

        # Normalize role_id -> int if present
        if "role_id" in update_data and update_data["role_id"] is not None:
            try:
                update_data["role_id"] = int(update_data["role_id"])
            except Exception:
                # leave as-is; DB may raise a validation error later
                logger.debug(f"[users.edit_user] role_id conversion failed for value: {update_data['role_id']}")

        # Handle password separately (hash)
        if "password" in update_data:
            pwd = update_data.pop("password")
            if pwd and isinstance(pwd, str) and pwd.strip() != "":
                user_obj.hashed_password = get_password_hash(pwd)
            # if empty -> ignore

        # Whitelist of allowed fields to update on the ORM model
        allowed_fields = {
            "nome", "username", "email", "cpf", "phone", "department", "institution",
            "birth_date", "notes", "address", "avatar_url", "specialty",
            "accepted_terms", "is_active", "is_admin", "role_id"
        }

        # Apply other fields
        for key, value in update_data.items():
            if key in allowed_fields:
                setattr(user_obj, key, value)
            else:
                logger.debug(f"[users.edit_user] ignoring unknown field: {key}")

        db.add(user_obj)
        db.commit()
        db.refresh(user_obj)

        return user_obj

    except HTTPException:
        # re-raise known HTTP exceptions after restoring search_path
        db.execute(text("SET search_path TO public"))
        raise
    except Exception as e:
        # log full traceback for debugging and return controlled HTTPException
        tb = traceback.format_exc()
        logger.error(f"[users.edit_user] Erro interno: {e}\n{tb}")
        db.rollback()
        db.execute(text("SET search_path TO public"))
        raise HTTPException(status_code=500, detail=f"Erro interno ao atualizar usuário: {e}")
    finally:
        # ensure we always reset search_path if still set
        try:
            db.execute(text("SET search_path TO public"))
        except Exception:
            pass

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    schema_name = get_schema_name(current_user)
    if not schema_name:
        raise HTTPException(400, "Tenant não identificado!")
    db.execute(text(f"SET search_path TO {schema_name}"))
    user_obj = db.query(UserTenant).filter(UserTenant.id == user_id).first()
    if not user_obj:
        db.execute(text("SET search_path TO public"))
        raise HTTPException(404, "Usuário não encontrado")
    db.delete(user_obj)
    db.commit()
    db.execute(text("SET search_path TO public"))