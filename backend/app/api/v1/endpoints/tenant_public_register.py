from typing import Optional, List
import os
import time
import shutil
import re
import logging
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from fastapi import Path as FastAPIPath  # avoid name clash with pathlib.Path
from fastapi import Request
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
    notes: str = Form(""),
    address: str = Form(""),
    specialty: str = Form(""),
    role: str = Form("professor"),
    role_id: Optional[int] = Form(None),
    avatar_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Public registration endpoint with extra debug logging (temporary).
    """
    # basic validation
    if not is_valid_schema_name(schema_name):
        raise HTTPException(status_code=400, detail="Schema inválido (caracteres não permitidos).")

    # Log incoming minimal info for debug
    try:
        logger.info("[tenant_public_register] Incoming public_register for schema=%s username=%s email=%s role=%s avatar_present=%s",
                    schema_name, username, email, role, bool(avatar_file and getattr(avatar_file, "filename", None)))
    except Exception:
        pass

    # 1) Ensure tenant schema exists (create minimal tables if necessary)
    try:
        exists_row = db.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :s"),
            {"s": schema_name}
        ).first()
    except Exception as e:
        logger.exception("Erro ao consultar information_schema")
        raise HTTPException(status_code=500, detail="Erro ao verificar schemas no banco.")

    schema_exists = bool(exists_row)

    if not schema_exists:
        try:
            logger.info("Schema %s não existe — criando automaticamente", schema_name)
            db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            for tbl in REQUIRED_TABLES:
                db.execute(text(f"CREATE TABLE IF NOT EXISTS {schema_name}.{tbl} (LIKE public.{tbl} INCLUDING ALL)"))
                seq_name = f"{tbl}_id_seq"
                db.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {schema_name}.{seq_name}"))
                try:
                    db.execute(text(f"ALTER TABLE {schema_name}.{tbl} ALTER COLUMN id SET DEFAULT nextval('{schema_name}.{seq_name}')"))
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

    # 2) Set search_path to tenant schema
    try:
        db.execute(text(f"SET search_path TO {schema_name}"))
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível ativar o schema do tenant.")

    avatar_url = None
    dest_path = None

    # 3) Save avatar file (if provided) with robust error handling and debug logging
    if avatar_file and getattr(avatar_file, "filename", None):
        upload_dir = Path("uploads") / "avatars"
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.exception("[tenant_public_register] Falha ao criar diretório uploads/avatars")
            try:
                db.execute(text("SET search_path TO public"))
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
            # ensure file pointer at start
            try:
                avatar_file.file.seek(0)
            except Exception:
                pass

            # log approximate size if available (debug)
            try:
                avatar_file.file.seek(0, os.SEEK_END)
                size = avatar_file.file.tell()
                avatar_file.file.seek(0)
                logger.info("[tenant_public_register] avatar file size (bytes): %s", size)
            except Exception:
                logger.debug("[tenant_public_register] não foi possível determinar size do arquivo (ok).")

            # write to disk
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
            logger.exception("[tenant_public_register] Erro ao salvar avatar (detalhe abaixo)")
            # try remove partial file
            try:
                if dest_path and dest_path.exists():
                    dest_path.unlink()
            except Exception:
                logger.debug("[tenant_public_register] Falha ao remover arquivo parcial")
            # restore search_path and return informative error (temporary debug)
            try:
                db.execute(text("SET search_path TO public"))
            except Exception:
                pass
            # Return a 500 with a helpful message for debugging (temporary)
            raise HTTPException(status_code=500, detail=f"Erro ao salvar avatar: {e}")

    # 4) Create user inside tenant schema
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
            notes=notes or None,
            address=address or None,
            avatar_url=avatar_url,
            specialty=specialty or None,
            accepted_terms=True,
            is_active=False,
            is_admin=False,
            role_id=role_id
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        logger.exception("[tenant_public_register] Erro ao criar usuário no tenant %s", schema_name)
        try:
            db.execute(text("SET search_path TO public"))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Erro ao criar usuário no tenant.")

    # 5) restore search_path
    try:
        db.execute(text("SET search_path TO public"))
    except Exception:
        pass

    base = str(request.base_url).rstrip("/")
    avatar_public = f"{base}{avatar_url}" if avatar_url else None

    return {"id": user.id, "email": user.email, "message": "Cadastro recebido, aguardando aprovação", "avatar_url": avatar_public}