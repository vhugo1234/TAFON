from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.connection import get_db, engine
from app.db.models.public import UserCentral
from app.core.security import create_access_token, verify_password
from app.core.config import settings
from datetime import timedelta
from typing import Optional
import traceback
from jose import jwt, JWTError
import re
import logging

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

# simples validação de nome de schema: começa com letra/underscore, contém letras/dígitos/underscore
_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Token(BaseModel):
    access_token: str
    token_type: str
    tenant_id: int | None = None
    schema_name: str | None = None
    is_superuser: bool = False
    empresa: str | None = None
    logoUrl: str | None = None
    nome: str | None = None
    role: str | None = None
    is_admin: bool | None = None
    email: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/token", response_model=Token)
@router.post("/login", response_model=Token)
async def login_for_access_token(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    username = None
    password = None

    # Form data (OAuth2PasswordRequestForm) or multipart
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
    # JSON body
    elif "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")
        username = body.get("email") or body.get("username")
        password = body.get("password")
    else:
        # fallback: try parse json
        try:
            body = await request.json()
            username = body.get("email") or body.get("username")
            password = body.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requisição deve ser form-urlencoded ou application/json"
            )

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campos de autenticação ausentes (username/email e password)."
        )

    # Tenta garantir sessão limpa antes de usar
    try:
        db.rollback()
    except Exception:
        pass

    # 1) Autenticar no CENTRAL (users_central no schema public)
    try:
        # Garantir que estamos no schema public
        db.execute(text("SET search_path TO public"))
        user = db.query(UserCentral).filter(UserCentral.email == username).first()
    except Exception as e:
        logger.error(f"Erro ao buscar usuário central: {e}")
        traceback.print_exc()
        try:
            db.rollback()
        except Exception:
            pass
        user = None

    if user:
        stored_pw = getattr(user, "hashed_password", None)
        if stored_pw and verify_password(password, stored_pw):
            access_token_expires = timedelta(minutes=int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)))
            empresa = "Central"
            logoUrl = "/static/logos/logo_almo.png"
            schema_name = None
            try:
                tenant = getattr(user, "tenant", None)
                if tenant:
                    empresa = getattr(tenant, "nome_empresa", empresa)
                    logoUrl = getattr(tenant, "logo_url", logoUrl)
                    schema_name = getattr(tenant, "schema_name", None)
            except Exception:
                traceback.print_exc()

            access_token = create_access_token(
                data={
                    "sub": user.email,
                    "tenant_id": getattr(user, "tenant_id", None),
                    "schema_name": schema_name,
                    "is_superuser": getattr(user, "is_superuser", False),
                    "nome": getattr(user, "nome", user.email),
                    "role": "SUPERUSER",
                    "role_id": None,
                    "is_admin": True,
                    "empresa": empresa,
                    "logoUrl": logoUrl,
                    "email": user.email,
                },
                expires_delta=access_token_expires,
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "tenant_id": getattr(user, "tenant_id", None),
                "schema_name": schema_name,
                "is_superuser": getattr(user, "is_superuser", False),
                "empresa": empresa,
                "logoUrl": logoUrl,
                "nome": getattr(user, "nome", user.email),
                "role": "SUPERUSER",
                "role_id": None,
                "is_admin": True,
                "email": user.email,
            }

    # 2) Autentica em tenants existentes (consulta explicitamente por schema)
    try:
        # Garantir que estamos no schema public antes de listar schemas
        db.execute(text("SET search_path TO public"))
        rows = db.execute(text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'public', 'pg_toast') "
            "AND schema_name NOT LIKE 'pg_%'"
        )).fetchall()
        schemas = [r[0] for r in rows]
        logger.info(f"Schemas de tenants encontrados: {schemas}")
    except Exception as e:
        logger.error(f"Erro ao listar schemas: {e}")
        traceback.print_exc()
        try:
            db.rollback()
        except Exception:
            pass
        schemas = []

    for schema in schemas:
        if not _SCHEMA_RE.match(schema):
            logger.warning(f"Schema ignorado por nome inválido: {schema}")
            continue
        
        try:
            logger.info(f"Tentando autenticar no schema: {schema}")
            
            # Criar uma nova conexão para evitar problemas de transação
            with engine.connect() as conn:
                # Garantir search_path correto
                conn.execute(text("SET search_path TO public"))
                
                # Verificar se a tabela user_tenant existe neste schema
                check_table = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_name = 'user_tenant')"
                ), {"schema": schema}).scalar()
                
                if not check_table:
                    logger.warning(f"Tabela user_tenant não existe no schema {schema}")
                    continue
                
                # Buscar usuário no schema do tenant usando query parametrizada
                # CORREÇÃO CRÍTICA: usar aspas duplas no schema e evitar interpolação direta
                query = text(
                    'SELECT id, nome, email, hashed_password, is_active, is_admin, role, role_id '
                    'FROM "' + schema + '".user_tenant WHERE email = :email LIMIT 1'
                )
                
                row = conn.execute(query, {"email": username}).fetchone()
                
                if not row:
                    logger.info(f"Usuário não encontrado no schema {schema}")
                    continue

                # row indices based on select order
                user_tenant_id, nome, email_val, hashed_pw, is_active, is_admin, role_val, role_id = row

                if not hashed_pw:
                    logger.warning(f"Usuário {email_val} no schema {schema} não tem senha")
                    continue
                    
                # if user inactive skip
                if is_active is False:
                    logger.warning(f"Usuário {email_val} no schema {schema} está inativo")
                    continue
                    
                if verify_password(password, hashed_pw):
                    logger.info(f"Autenticação bem-sucedida para {email_val} no schema {schema}")
                    
                    # read tenant info from public.tenants
                    info = conn.execute(
                        text("SELECT nome_empresa, logo_url FROM public.tenants WHERE schema_name = :schema"),
                        {"schema": schema}
                    ).fetchone()
                    
                    empresa = info[0] if info and info[0] else "Empresa"
                    logoUrl = info[1] if info and info[1] else "/static/logos/logo_almo.png"

                    access_token_expires = timedelta(minutes=int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)))
                    access_token = create_access_token(
                        data={
                            "sub": email_val,
                            "schema_name": schema,
                            "user_id": user_tenant_id,
                            "nome": nome,
                            "role": role_val or str(role_id) if role_id else "user",
                            "role_id": role_id,
                            "is_admin": bool(is_admin),
                            "empresa": empresa,
                            "logoUrl": logoUrl,
                            "is_superuser": False,
                            "email": email_val
                        },
                        expires_delta=access_token_expires
                    )
                    return {
                        "access_token": access_token,
                        "token_type": "bearer",
                        "tenant_id": None,
                        "schema_name": schema,
                        "is_superuser": False,
                        "empresa": empresa,
                        "logoUrl": logoUrl,
                        "nome": nome,
                        "role": role_val or str(role_id) if role_id else "user",
                        "role_id": role_id,
                        "is_admin": bool(is_admin),
                        "email": email_val
                    }
                else:
                    logger.warning(f"Senha incorreta para {email_val} no schema {schema}")
                    
        except Exception as e:
            logger.error(f"Erro ao autenticar no schema {schema}: {e}")
            traceback.print_exc()
            # continue para o próximo schema
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/me")
async def me(authorization: Optional[str] = Header(None)):
    """
    Retorna informações públicas do usuário baseado no access token Bearer.
    Header esperado: Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authorization header missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid authorization header")

    token = parts[1]

    try:
        alg = getattr(settings, "ALGORITHM", "HS256")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[alg])
    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")

    user_info = {
        "nome": payload.get("nome") or payload.get("name"),
        "email": payload.get("email") or payload.get("sub"),
        "id": payload.get("user_id") or payload.get("id"),
        "role": payload.get("role"),
        "role_id": payload.get("role_id"),
        "roles": payload.get("roles"),
        "is_admin": payload.get("is_admin"),
        "is_superuser": payload.get("is_superuser"),
        "empresa": payload.get("empresa"),
        "logoUrl": payload.get("logoUrl"),
        "schema_name": payload.get("schema_name"),
    }
    return user_info