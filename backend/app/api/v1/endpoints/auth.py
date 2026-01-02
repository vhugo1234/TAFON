from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.connection import get_db
# TEMPORARY FIX: Explicit imports from specific model modules to avoid ambiguity
from app.db.models.public import UserCentral, Tenant
from app.db.models.tenant import UserTenant
from app.core.security import create_access_token, verify_password
from app.core.config import settings
from datetime import timedelta
import json
import re

router = APIRouter()

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


def validate_schema_name(schema_name: str) -> bool:
    """
    SECURITY: Validate schema name to prevent SQL injection.
    Only allow alphanumeric characters, underscores, and hyphens.
    """
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', schema_name))


@router.post("/token", response_model=Token)
@router.post("/login", response_model=Token)
async def login_for_access_token(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    username = None
    password = None

    # Form data (OAuth2PasswordRequestForm)
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
    # JSON body
    elif "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            # Se o JSON for inválido, retornar 400 em vez de 500
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON body",
            )
        username = body.get("email") or body.get("username")
        password = body.get("password")
    else:
        try:
            body = await request.json()
            username = body.get("email") or body.get("username")
            password = body.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requisição deve ser form-urlencoded ou application/json",
            )

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campos de autenticação ausentes (username/email e password).",
        )

    # 1. Busca no schema CENTRAL (superadmin)
    user = db.query(UserCentral).filter(UserCentral.email == username).first()
    nome_usuario = getattr(user, "nome", None) or getattr(user, "username", None) or (user.email if user else None)
    if user and verify_password(password, user.hashed_password):
        print(f"[LOGIN CENTRAL SUCESSO] Usuário: {nome_usuario}")
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        empresa = getattr(user.tenant, "nome_empresa", "Central") if getattr(user, "tenant", None) else "Central"
        logoUrl = getattr(user.tenant, "logo_url", "/static/logos/logo_almo.png") if getattr(user, "tenant", None) else "/static/logos/logo_almo.png"
        schema_name = getattr(user.tenant, "schema_name", None) if getattr(user, "tenant", None) else None
        access_token = create_access_token(
            data={
                "sub": user.email,
                "tenant_id": user.tenant_id,
                "tenant_user_id": user.tenant_user_id,
                "is_superuser": user.is_superuser,
                "nome": nome_usuario,
                "role": "SUPERUSER",
                "is_admin": True,
                "empresa": empresa,
                "logoUrl": logoUrl,
                "email": user.email,
            },
            expires_delta=access_token_expires
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "tenant_id": user.tenant_id,
            "schema_name": schema_name,
            "is_superuser": user.is_superuser,
            "empresa": empresa,
            "logoUrl": logoUrl,
            "nome": nome_usuario,
            "role": "SUPERUSER",
            "is_admin": True,
            "email": user.email,
        }

    # 2. Procura em todos os schemas de tenants (clientes)
    schemas = [
        row[0] for row in db.execute(
            text("SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'public')")
        )
    ]
    for schema_name in schemas:
        try:
            # SECURITY: Validate schema name before using in SQL
            if not validate_schema_name(schema_name):
                print(f"[SECURITY] Invalid schema name skipped: {schema_name}")
                continue
            
            print(f"Tentando login no schema: {schema_name}")
            # SECURITY: Use validated schema name with text() to prevent SQL injection
            db.execute(text(f'SET search_path TO "{schema_name}"'))
            user_tenant = db.query(UserTenant).filter(UserTenant.email == username).first()
            if user_tenant:
                print(f">>> Encontrado usuário em {schema_name}: {user_tenant.email} (admin? {user_tenant.is_admin})")
                senha_ok = verify_password(password, user_tenant.hashed_password)
                print("Senha válida?", senha_ok)
                if senha_ok:
                    # --- PATCH COMEÇA AQUI ---
                    # Após autenticar o usuário, troque search_path para public ANTES de buscar nome/logo!
                    db.execute(text("SET search_path TO public"))  # Troca para schema central

                    result = db.execute(
                        text("SELECT nome_empresa, logo_url FROM tenants WHERE schema_name = :schema"),
                        {"schema": schema_name}
                    ).first()
                    empresa = result[0] if result and result[0] else "Empresa"
                    logoUrl = result[1] if result and result[1] else "/static/logos/logo_almo.png"
                    print(f"[TOKEN PAYLOAD] empresa={empresa}, logoUrl={logoUrl}")

                    # --- PATCH TERMINA AQUI ---

                    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                    access_token = create_access_token(
                        data={
                            "sub": user_tenant.email,
                            "schema_name": schema_name,
                            "user_id": user_tenant.id,
                            "nome": user_tenant.nome,
                            "role": user_tenant.role.value,
                            "is_admin": user_tenant.is_admin,
                            "empresa": empresa,
                            "logoUrl": logoUrl,
                            "is_superuser": False,
                            "email": user_tenant.email
                        },
                        expires_delta=access_token_expires
                    )
                    print(f"[LOGIN TENANT SUCESSO] Usuário: {user_tenant.email} (schema {schema_name}), empresa={empresa}, logoUrl={logoUrl}")
                    return {
                        "access_token": access_token,
                        "token_type": "bearer",
                        "tenant_id": None,
                        "schema_name": schema_name,
                        "is_superuser": False,
                        "empresa": empresa,
                        "logoUrl": logoUrl,
                        "nome": user_tenant.nome,
                        "role": user_tenant.role.value,
                        "is_admin": user_tenant.is_admin,
                        "email": user_tenant.email
                    }
        except Exception as e:
            db.rollback()
            print(f"[ERRO ao logar no schema {schema_name}] {e}")
            # Restore search_path on error
            db.execute(text("SET search_path TO public"))
            pass
    db.execute(text("SET search_path TO public"))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )