from typing import Optional, List
import os
import time
import shutil
import re
import logging
from uuid import uuid4
from pathlib import Path
import traceback

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends, Request
from fastapi import Path as FastAPIPath  # avoid name clash with pathlib.Path
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.connection import get_db
from app.db.models.tenant import UserTenant
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants/{schema_name}/public", tags=["Tenant Public"])


REQUIRED_TABLES: List[str] = [
    "user_tenant",
    "role_tenant",
]

def is_valid_schema_name(name: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9_]+$', name))


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def public_register(
    request: Request,
    schema_name: str = FastAPIPath(..., min_length=1),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    cpf: str = Form(""),
    phone: str = Form(""),
    department: str = Form(""),
    institution: str = Form(""),
    birth_date: str = Form(""),
    notes: Optional[str] = Form(None),
    address: str = Form(""),
    specialty: str = Form(""),
    role: str = Form("professor"),
    role_id: Optional[int] = Form(None),
    cref: Optional[str] = Form(None),
    avatar_file: Optional[UploadFile] = File(None),
    # banking fields (new)
    bank_name: Optional[str] = Form(None),
    pix: Optional[str] = Form(None),
    bank_account: Optional[str] = Form(None),
    agency: Optional[str] = Form(None),
    # NEW: optional event assignment fields
    event_id: Optional[int] = Form(None),
    assign_role_name: Optional[str] = Form(None),
    assign_days_assigned: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Public registration endpoint. Creates tenant schema if missing, sets search_path,
    saves optional avatar, creates UserTenant row inside tenant schema and returns it.

    New optional behavior:
    - If `event_id` is provided, attempts to create a row in {schema}.event_workers
      linking the created user to that event. This insertion is attempted AFTER the
      user creation; failures to link do NOT roll back the user creation. The response
      will include `event_worker` (the inserted row) on success or `event_warning`
      message when linking wasn't possible.

    Backwards compatible: if event_id is not sent, behavior is identical to the original endpoint.
    """
    from sqlalchemy.exc import IntegrityError

    if not is_valid_schema_name(schema_name):
        raise HTTPException(status_code=400, detail="Schema inválido (caracteres não permitidos).")

    try:
        logger.info(
            "[tenant_public_register] register schema=%s username=%s email=%s role=%s avatar_present=%s cref=%s event_id=%s",
            schema_name, username, email, role, bool(avatar_file and getattr(avatar_file, "filename", None)), cref, event_id
        )
    except Exception:
        pass

    # Ensure schema exists and minimal tables
    try:
        exists_row = db.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :s"),
            {"s": schema_name}
        ).first()
    except Exception:
        logger.exception("Erro ao consultar information_schema")
        raise HTTPException(status_code=500, detail="Erro ao verificar schemas no banco.")

    schema_exists = bool(exists_row)

    if not schema_exists:
        try:
            logger.info("Schema %s não existe — criando automaticamente", schema_name)
            db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            for tbl in REQUIRED_TABLES:
                db.execute(text(f'CREATE TABLE IF NOT EXISTS "{schema_name}".{tbl} (LIKE public.{tbl} INCLUDING ALL)'))
                seq_name = f"{tbl}_id_seq"
                db.execute(text(f'CREATE SEQUENCE IF NOT EXISTS "{schema_name}".{seq_name}'))
                try:
                    db.execute(text(f'ALTER TABLE "{schema_name}".{tbl} ALTER COLUMN id SET DEFAULT nextval(\'"{schema_name}".{seq_name}\')'))
                except Exception:
                    logger.debug("Não foi possível ajustar default da coluna id para %s.%s (talvez não exista)", schema_name, tbl)
            db.commit()
            logger.info("Schema %s criado com sucesso (tabelas mínimas criadas).", schema_name)
        except Exception:
            logger.exception("Falha ao criar schema/tabelas para %s", schema_name)
            try:
                db.rollback()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Falha ao criar schema/tabelas do tenant automaticamente.")

    # Set search_path to tenant schema for subsequent operations
    try:
        db.execute(text(f'SET search_path TO "{schema_name}"'))
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível ativar o schema do tenant.")

    avatar_url = None

    # Save avatar file if provided
    if avatar_file and getattr(avatar_file, "filename", None):
        upload_dir = Path("uploads") / "avatars"
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.exception("[tenant_public_register] Falha ao criar diretório uploads/avatars")
            try:
                db.execute(text('SET search_path TO public'))
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Erro interno ao preparar upload (mkdir).")

        ts = int(time.time())
        try:
            ext = os.path.splitext(avatar_file.filename)[1] or ".png"
        except Exception:
            ext = ".png"
        safe_name = f"{schema_name}_{ts}_{uuid4().hex}{ext}"
        dest_path = upload_dir / safe_name

        try:
            try:
                avatar_file.file.seek(0)
            except Exception:
                pass

            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(avatar_file.file, buffer)
                buffer.flush()
                try:
                    os.fsync(buffer.fileno())
                except Exception:
                    logger.debug("[tenant_public_register] fsync não disponível ou falhou (continuando)")
            avatar_url = f"/uploads/avatars/{safe_name}"
            logger.info("[tenant_public_register] Saved avatar to %s -> %s", dest_path.resolve(), avatar_url)
        except Exception as e:
            logger.exception("[tenant_public_register] Erro ao salvar avatar")
            try:
                if dest_path and dest_path.exists():
                    dest_path.unlink()
            except Exception:
                logger.debug("[tenant_public_register] Falha ao remover arquivo parcial")
            try:
                db.execute(text('SET search_path TO public'))
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Erro ao salvar avatar: {e}")

    # Create user inside tenant schema
    try:
        hashed = get_password_hash(password)
        user = UserTenant(
            nome=full_name,
            username=username,
            email=email,
            hashed_password=hashed,
            cpf=cpf or None,
            phone=phone or None,
            department=department or None,
            institution=institution or None,
            birth_date=birth_date or None,
            notes=(notes or None),
            address=address or None,
            avatar_url=avatar_url,
            specialty=specialty or None,
            accepted_terms=True,
            is_active=False,
            is_admin=False,
            role_id=role_id,
            cref=cref or None,
            # banking fields
            bank_name=bank_name or None,
            pix=pix or None,
            bank_account=bank_account or None,
            agency=agency or None,
        )

        # prepare base/avatar_public for later use (useful even if commit fails)
        base = str(request.base_url).rstrip("/")
        avatar_public = f"{base}{avatar_url}" if avatar_url else None

        db.add(user)
        try:
            db.commit()
        except IntegrityError as ie:
            # duplicate username/email or other integrity constraint:
            db.rollback()
            logger.warning("[tenant_public_register] IntegrityError ao criar usuário: %s", getattr(ie, "orig", ie))
            # try to find existing user by username or email and proceed (best-effort)
            try:
                sel_exist = db.execute(
                    text(f'SELECT * FROM "{schema_name}".user_tenant WHERE username = :u OR email = :e'),
                    {"u": username, "e": email},
                ).fetchone()
                if sel_exist:
                    try:
                        result = dict(sel_exist._mapping)
                    except Exception:
                        result = {c: getattr(sel_exist, c) for c in sel_exist.keys()}
                    if result.get("avatar_url"):
                        result["avatar_url"] = f"{base}{result['avatar_url']}"
                    result["message"] = "Cadastro recebido (usuário já existente)"
                    user_id = result.get("id")
                else:
                    logger.exception("[tenant_public_register] IntegrityError sem registro existente para username/email")
                    try:
                        db.execute(text('SET search_path TO public'))
                    except Exception:
                        pass
                    raise HTTPException(status_code=500, detail="Erro ao criar usuário no tenant.")
            except HTTPException:
                raise
            except Exception:
                logger.exception("[tenant_public_register] Falha ao recuperar usuário existente após IntegrityError")
                try:
                    db.execute(text('SET search_path TO public'))
                except Exception:
                    pass
                raise HTTPException(status_code=500, detail="Erro ao criar usuário no tenant.")
        except Exception:
            logger.exception("[tenant_public_register] Erro ao commitar usuário no tenant %s", schema_name)
            try:
                db.execute(text('SET search_path TO public'))
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Erro ao criar usuário no tenant.")
        else:
            # commit succeeded: capture id and prepare response values
            user_id = getattr(user, "id", None)
            result = None
            try:
                sel = db.execute(
                    text(f'SELECT * FROM "{schema_name}".user_tenant WHERE id = :id'),
                    {"id": user_id},
                )
                row = sel.fetchone()
                if row:
                    try:
                        result = dict(row._mapping)
                    except Exception:
                        result = {c: getattr(row, c) for c in row.keys()}
                    if result.get("avatar_url"):
                        result["avatar_url"] = f"{base}{result['avatar_url']}"
                    result["message"] = "Cadastro recebido, aguardando aprovação"
                else:
                    result = {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
            except Exception:
                # If SELECT fails due to prior transaction issue, rollback and retry once
                logger.exception("[tenant_public_register] SELECT após commit falhou; tentando rollback e retry")
                try:
                    db.rollback()
                except Exception:
                    logger.debug("[tenant_public_register] rollback falhou ou não aplicável")

                try:
                    db.execute(text(f'SET search_path TO "{schema_name}"'))
                    sel = db.execute(
                        text(f'SELECT * FROM "{schema_name}".user_tenant WHERE id = :id'),
                        {"id": user_id},
                    )
                    row = sel.fetchone()
                    if row:
                        try:
                            result = dict(row._mapping)
                        except Exception:
                            result = {c: getattr(row, c) for c in row.keys()}
                        if result.get("avatar_url"):
                            result["avatar_url"] = f"{base}{result['avatar_url']}"
                        result["message"] = "Cadastro recebido, aguardando aprovação"
                    else:
                        result = {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                except Exception:
                    logger.exception("[tenant_public_register] nova tentativa de SELECT também falhou")
                    result = {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}

        # --- NEW: if event_id provided, attempt to create event_workers link in the same tenant schema
        if event_id:
            try:
                # Check event exists in tenant schema
                ev = db.execute(
                    text(f'SELECT id FROM "{schema_name}".events WHERE id = :eid'),
                    {"eid": event_id},
                ).fetchone()
                if not ev:
                    # event doesn't exist in this tenant schema: return user created but warn
                    result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                    result["event_worker"] = None
                    result["event_warning"] = f"Evento {event_id} não encontrado no tenant {schema_name}."
                else:
                    # Prevent duplicate
                    dup = db.execute(
                        text(f'SELECT id FROM "{schema_name}".event_workers WHERE event_id = :eid AND user_id = :uid'),
                        {"eid": event_id, "uid": user_id},
                    ).fetchone()
                    if dup:
                        # return existing id with note
                        existing_id = dup[0] if hasattr(dup, "__len__") else (getattr(dup, "id", None) or None)
                        result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                        result["event_worker"] = {"id": existing_id, "note": "Vínculo já existia"}
                    else:
                        # decide role_id: prefer form value, else use created user's role_id
                        created_user_role_id = None
                        try:
                            created_user_role_id = int(result.get("role_id")) if result and result.get("role_id") is not None else None
                        except Exception:
                            created_user_role_id = None

                        role_id_to_insert = role_id if role_id is not None else created_user_role_id

                        # best-effort: resolve role_name from roles_tenant if available
                        resolved_role_name = None
                        if role_id_to_insert is not None:
                            try:
                                sel_r = db.execute(
                                    text(f'SELECT nome FROM "{schema_name}".roles_tenant WHERE id = :rid'),
                                    {"rid": int(role_id_to_insert)}
                                ).fetchone()
                                if sel_r:
                                    try:
                                        resolved_role_name = dict(sel_r._mapping).get("nome")
                                    except Exception:
                                        try:
                                            resolved_role_name = sel_r[0]
                                        except Exception:
                                            resolved_role_name = None
                            except Exception:
                                resolved_role_name = None

                        try:
                            ins = db.execute(
                                text(f'''
                                    INSERT INTO "{schema_name}".event_workers
                                      (event_id, user_id, role_id, role_name, days_assigned, created_at)
                                    VALUES (:event_id, :user_id, :role_id, :role_name, :days_assigned, now())
                                    RETURNING *
                                '''),
                                {
                                    "event_id": event_id,
                                    "user_id": user_id,
                                    "role_id": role_id_to_insert,
                                    "role_name": assign_role_name if assign_role_name is not None else resolved_role_name,
                                    "days_assigned": assign_days_assigned or 0,
                                },
                            )
                            ew_row = ins.fetchone()
                            try:
                                db.commit()
                            except Exception:
                                logger.exception("[tenant_public_register] Erro ao commitar event_workers")
                                try:
                                    db.rollback()
                                except Exception:
                                    pass
                                result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                                result["event_worker"] = None
                                result["event_warning"] = "Falha ao criar vínculo de worker; verifique logs."
                            else:
                                if ew_row:
                                    try:
                                        ew = dict(ew_row._mapping)
                                    except Exception:
                                        ew = {c: getattr(ew_row, c) for c in ew_row.keys()}
                                    result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                                    result["event_worker"] = ew
                                else:
                                    result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                                    result["event_worker"] = None
                        except IntegrityError as ie:
                            # if unique violation on event_workers (race), try to fetch existing and continue
                            db.rollback()
                            logger.warning("[tenant_public_register] IntegrityError ao criar event_worker: %s", getattr(ie, "orig", ie))
                            try:
                                existing = db.execute(
                                    text(f'SELECT * FROM "{schema_name}".event_workers WHERE event_id = :eid AND user_id = :uid'),
                                    {"eid": event_id, "uid": user_id},
                                ).fetchone()
                                if existing:
                                    try:
                                        ew = dict(existing._mapping)
                                    except Exception:
                                        ew = {c: getattr(existing, c) for c in existing.keys()}
                                    result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                                    result["event_worker"] = ew
                                else:
                                    result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                                    result["event_worker"] = None
                            except Exception:
                                logger.exception("[tenant_public_register] Falha ao recuperar event_worker após IntegrityError")
                                result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                                result["event_worker"] = None
                        except Exception:
                            logger.exception("[tenant_public_register] Erro ao criar event_worker")
                            try:
                                db.rollback()
                            except Exception:
                                pass
                            result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                            result["event_worker"] = None
            except Exception as e:
                logger.exception("[tenant_public_register] Erro ao tentar vincular usuário ao evento")
                result = result or {"id": user_id, "email": email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}
                result.setdefault("event_worker", None)
                result["event_warning"] = f"Erro ao tentar vincular usuário ao evento: {str(e)}"

        # Restore search_path to public before returning
        try:
            db.execute(text('SET search_path TO public'))
        except Exception:
            pass

        return result

    except Exception:
        logger.exception("[tenant_public_register] Erro ao criar usuário no tenant %s", schema_name)
        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.execute(text('SET search_path TO public'))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Erro ao criar usuário no tenant.")
