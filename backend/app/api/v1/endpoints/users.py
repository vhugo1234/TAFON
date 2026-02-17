from fastapi import APIRouter, Depends, HTTPException, status, Body, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func
from sqlalchemy.exc import IntegrityError
from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse
import os
import time
import shutil
from uuid import uuid4
from pathlib import Path

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

# --- CREATE USER (Corrigido: Removemos avatar_file dos argumentos) ---
@router.post("/", response_model=UserTenantOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    avatar_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    import logging, traceback
    logger = logging.getLogger("uvicorn.error")

    def to_bool(val):
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return bool(val)
        s = str(val).strip().lower()
        return s in ("1", "true", "yes", "on")

    schema_name = get_schema_name(current_user)
    if not schema_name:
        raise HTTPException(400, "Tenant não identificado")

    # ensure search_path is set for any direct SQL we run here
    try:
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao setar search_path: {e}")

    try:
        content_type = request.headers.get("content-type", "") or ""
        if content_type.startswith("multipart/"):
            form = await request.form()
            data = {}
            for k, v in form.multi_items():
                if hasattr(v, "filename"):
                    continue
                data[k] = v
        else:
            try:
                data = await request.json()
                if data is None:
                    data = {}
            except Exception:
                data = {}

        nome = data.get("nome") or data.get("full_name") or None
        username = (data.get("username") or None)
        email = (data.get("email") or None)
        password = data.get("password") or None

        missing = []
        if not nome:
            missing.append("nome or full_name")
        if not email:
            missing.append("email")
        if not password:
            missing.append("password")
        if not username and email and "@" in email:
            username = email.split("@")[0]

        if missing:
            raise HTTPException(status_code=422, detail=f"Campos obrigatórios ausentes: {', '.join(missing)}")

        if username and isinstance(username, str):
            username = username.strip()
        if email and isinstance(email, str):
            email = email.strip().lower()

        # --- check duplicates using qualified table name to avoid search_path issues ---
        existing = None
        try:
            dup_sql = text(
                f'SELECT id, username, email FROM "{schema_name}".user_tenant '
                "WHERE (lower(username) = lower(:username) AND :username IS NOT NULL) "
                "OR (lower(email) = lower(:email) AND :email IS NOT NULL) LIMIT 1"
            )
            dup_res = db.execute(dup_sql, {"username": username, "email": email}).fetchone()
            if dup_res:
                existing = dict(dup_res._mapping)
                content = {
                    "detail": "Já existe usuário com username/email informado",
                    "existing_user_id": existing.get("id")
                }
                return JSONResponse(status_code=409, content=content)
        except Exception:
            # if the raw check fails, continue and rely on DB uniqueness constraints
            logger.debug("create_user: falha ao checar duplicidade (continuando)", exc_info=True)

        # Avatar handling (if provided via param avatar_file)
        avatar_path = None
        if avatar_file and getattr(avatar_file, "filename", None):
            upload_dir = Path("uploads") / "avatars"
            upload_dir.mkdir(parents=True, exist_ok=True)
            ext = os.path.splitext(avatar_file.filename)[1] or ".png"
            safe_name = f"{schema_name}_{uuid4().hex}{ext}"
            dest = upload_dir / safe_name
            try:
                try:
                    avatar_file.file.seek(0)
                except Exception:
                    pass
                with open(dest, "wb") as buffer:
                    shutil.copyfileobj(avatar_file.file, buffer)
                avatar_path = f"/uploads/avatars/{safe_name}"
            except Exception as e:
                logger.error("[create_user] failed to save avatar: %s", e, exc_info=True)
                raise HTTPException(status_code=500, detail=f"Falha ao salvar avatar: {e}")

        # parse role/custom_role
        role_id = None
        if data.get("role_id") is not None and str(data.get("role_id")).strip() != "":
            try:
                role_id = int(data.get("role_id"))
            except Exception:
                role_id = None

        custom_role = data.get("custom_role") or data.get("role") or None
        if isinstance(custom_role, str):
            custom_role = custom_role.strip() or None

        # create hashed password
        hashed = get_password_hash(password)

        user = UserTenant(
            nome=nome,
            username=username,
            email=email,
            hashed_password=hashed,
            cpf=data.get("cpf") or None,
            phone=data.get("phone") or None,
            department=data.get("department") or None,
            institution=data.get("institution") or None,
            birth_date=data.get("birth_date") or None,
            notes=data.get("notes") or None,
            address=data.get("address") or None,
            avatar_url=avatar_path or data.get("avatar_url"),
            specialty=data.get("specialty") or None,
            accepted_terms=to_bool(data.get("accepted_terms")),
            is_active=to_bool(data.get("is_active")),
            is_admin=to_bool(data.get("is_admin")),
            role_id=role_id,
            custom_role=custom_role,
            cref=data.get("cref") or None,
            # banking fields
            bank_name=data.get("bank_name") or None,
            pix=data.get("pix") or None,
            bank_account=data.get("bank_account") or None,
            agency=data.get("agency") or None,
        )

        db.add(user)
        try:
            db.commit()
            # do NOT rely on db.refresh(user) (refresh may use a connection without search_path)
            # instead SELECT the created row using fully qualified name
            sel = db.execute(
                text(
                    f'SELECT id, nome, username, email, cpf, phone, department, institution, '
                    f'birth_date, notes, address, specialty, avatar_url, role, role_id, custom_role, '
                    f'accepted_terms, is_active, is_admin, created_at, cref, bank_name, pix, bank_account, agency '
                    f'FROM "{schema_name}".user_tenant WHERE id = :id'
                ),
                {"id": user.id},
            )
            row = sel.fetchone()
            if row:
                return dict(row._mapping)
            # fallback
            return user
        except IntegrityError as ie:
            db.rollback()
            msg = str(getattr(ie, "orig", ie)).lower()
            # try to find existing id using qualified select
            existing = None
            try:
                lookup_sql = text(
                    f'SELECT id FROM "{schema_name}".user_tenant WHERE (lower(username)=lower(:username) AND :username IS NOT NULL) OR (lower(email)=lower(:email) AND :email IS NOT NULL) LIMIT 1'
                )
                found = db.execute(lookup_sql, {"username": username, "email": email}).fetchone()
                if found:
                    existing = dict(found._mapping)
            except Exception:
                existing = None

            detail = "Violação de unicidade"
            if "username" in msg or "user_tenant_username_key" in msg:
                detail = "Username já cadastrado"
            elif "email" in msg or "user_tenant_email_key" in msg:
                detail = "Email já cadastrado"

            content = {"detail": detail}
            if existing and existing.get("id"):
                content["existing_user_id"] = existing.get("id")

            return JSONResponse(status_code=409, content=content)
        except Exception as e:
            db.rollback()
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Erro ao criar usuário: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar usuário: {e}")
    finally:
        try:
            db.execute(text('SET search_path TO public'))
        except Exception:
            pass

# --- EDIT USER (PATCH aceita multipart e JSON; atualizada para garantir cref/is_active) ---
@router.patch("/{user_id}", response_model=UserTenantOut)
async def edit_user(
    user_id: int,
    request: Request,
    avatar_file: Optional[UploadFile] = File(None),
    user_in: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    import logging, traceback
    logger = logging.getLogger("uvicorn.error")

    def _to_bool(val):
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

    def _maybe_int(v):
        if v is None or v == "":
            return None
        try:
            return int(v)
        except Exception:
            return None

    schema_name = get_schema_name(current_user)
    if not schema_name:
        raise HTTPException(400, "Tenant não identificado!")

    try:
        # garantir search_path para operações diretas
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
    except Exception as e:
        logger.exception("[users.edit_user] falha ao setar search_path: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao ativar schema do tenant")

    try:
        # parse inputs (multipart or json)
        content_type = request.headers.get("content-type", "") or ""
        update_data: Dict[str, Any] = {}

        if content_type.startswith("multipart/"):
            form = await request.form()
            # use multi_items when available to preserve repeated fields handling
            try:
                items = form.multi_items()
            except Exception:
                items = form.items()
            for k, v in items:
                # skip uploaded files - avatar_file is a separate parameter
                if hasattr(v, "filename"):
                    continue
                update_data[k] = v

            # file may be provided either as avatar_file param or in the form
            file_obj = avatar_file or (await request.form()).get("avatar_file") if not avatar_file else avatar_file
            # prefer the explicit avatar_file param if present
            file_obj = avatar_file or (form.get("avatar_file") if 'form' in locals() else None)
            if file_obj and getattr(file_obj, "filename", None):
                logger.info("[users.edit_user] received file: %s", file_obj.filename)
                upload_dir = os.path.join("uploads", "avatars")
                os.makedirs(upload_dir, exist_ok=True)
                ts = int(time.time())
                safe_name = f"{schema_name}_{ts}_{os.path.basename(file_obj.filename)}"
                dest_path = os.path.join(upload_dir, safe_name)
                try:
                    try:
                        file_obj.file.seek(0)
                    except Exception:
                        pass
                    with open(dest_path, "wb") as buffer:
                        shutil.copyfileobj(file_obj.file, buffer)
                    update_data["avatar_url"] = f"/uploads/avatars/{safe_name}"
                    logger.info("[users.edit_user] saved file to %s", dest_path)
                except Exception as e:
                    logger.error("[users.edit_user] failed to save uploaded file: %s", e, exc_info=True)
                    raise HTTPException(status_code=500, detail=f"Falha ao salvar avatar: {e}")
        else:
            # JSON body case
            if user_in:
                update_data = dict(user_in)
            else:
                try:
                    body = await request.json()
                    update_data = dict(body or {})
                except Exception:
                    update_data = {}

        # Normalize & sanitize incoming values
        # Trim strings and convert empty strings to None for most fields
        for k, v in list(update_data.items()):
            if isinstance(v, str):
                trimmed = v.strip()
                # keep empty string for notes perhaps, but here we convert empties to None to allow clearing
                update_data[k] = trimmed if trimmed != "" else None

        # Normalize booleans (convert textual booleans to real bools or remove if None)
        for bool_key in ("accepted_terms", "is_active", "is_admin"):
            if bool_key in update_data:
                converted = _to_bool(update_data[bool_key])
                if converted is None:
                    # remove key so we don't accidentally set to empty string
                    update_data.pop(bool_key, None)
                else:
                    update_data[bool_key] = bool(converted)

        # Normalize role_id: empty string -> None, else int
        if "role_id" in update_data:
            if update_data["role_id"] == "":
                update_data["role_id"] = None
            elif update_data["role_id"] is not None:
                try:
                    update_data["role_id"] = int(update_data["role_id"])
                except Exception:
                    logger.debug("[users.edit_user] role_id conversion failed for value: %s", update_data.get("role_id"))

        # Handle password: hash if provided
        hashed_pwd = None
        if "password" in update_data:
            pwd = update_data.pop("password")
            if pwd and isinstance(pwd, str) and pwd.strip() != "":
                hashed_pwd = get_password_hash(pwd)

        # Normalize custom_role empty->None
        if "custom_role" in update_data and isinstance(update_data["custom_role"], str) and (update_data["custom_role"] is None or (isinstance(update_data["custom_role"], str) and update_data["custom_role"].strip() == "")):
            update_data["custom_role"] = None

        # Ensure cref passed through (string trimmed or None)
        if "cref" in update_data and isinstance(update_data["cref"], str):
            update_data["cref"] = update_data["cref"].strip() or None

        # Build update SQL (qualified) with allowed fields
        allowed_fields = {
            "nome", "username", "email", "cpf", "phone", "department", "institution",
            "birth_date", "notes", "address", "avatar_url", "specialty",
            "accepted_terms", "is_active", "is_admin", "role_id", "custom_role", "cref",
            # banking fields
            "bank_name", "pix", "bank_account", "agency"
        }

        set_parts = []
        params: Dict[str, Any] = {"_id": user_id}
        if hashed_pwd is not None:
            set_parts.append("hashed_password = :hashed_password")
            params["hashed_password"] = hashed_pwd

        # build set clauses and params using _<field> param names to avoid collisions
        for key, val in update_data.items():
            if key in allowed_fields:
                pname = f"_{key}"
                set_parts.append(f"{key} = :{pname}")
                # leave None as None to set NULL in DB
                params[pname] = val
            else:
                logger.debug("[users.edit_user] ignoring unknown field: %s", key)

        # debug logs to help trace issues
        logger.info("[users.edit_user] update_data keys=%s", list(update_data.keys()))
        logger.debug("[users.edit_user] update_data=%s", update_data)
        logger.info("[users.edit_user] set_parts=%s", set_parts)
        logger.debug("[users.edit_user] params=%s", params)

        if set_parts:
            sql = text(f'UPDATE "{schema_name}".user_tenant SET ' + ", ".join(set_parts) + ' WHERE id = :_id')
            try:
                db.execute(sql, params)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("[users.edit_user] raw UPDATE failed: %s", e, exc_info=True)
                raise HTTPException(status_code=500, detail=f"Falha ao atualizar usuário: {e}")

        # SELECT qualified row and return dict (include cref)
        try:
            sel = db.execute(
                text(
                    f'SELECT id, nome, username, email, cpf, phone, department, institution, '
                    f'birth_date, notes, address, specialty, avatar_url, role, role_id, custom_role, '
                    f'accepted_terms, is_active, is_admin, created_at, cref, bank_name, pix, bank_account, agency '
                    f'FROM "{schema_name}".user_tenant WHERE id = :_id'
                ),
                {"_id": user_id},
            )
            row = sel.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")
            result = dict(row._mapping)
            # make avatar_url absolute like create_user
            base = str(request.base_url).rstrip("/")
            if result.get("avatar_url"):
                result["avatar_url"] = f"{base}{result['avatar_url']}"
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[users.edit_user] failed to SELECT updated user: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Erro ao obter usuário atualizado: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[users.edit_user] Erro interno: %s", e, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Erro interno ao atualizar usuário")
    finally:
        try:
            db.execute(text('SET search_path TO public'))
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
