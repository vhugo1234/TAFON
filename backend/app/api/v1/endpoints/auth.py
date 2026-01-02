from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.connection import get_db
# prefira imports explícitos para evitar problemas de namespace
from app.db.models.public import UserCentral
from app.db.models.tenant import UserTenant
from app.core.security import create_access_token, verify_password
from app.core.config import settings
from datetime import timedelta
import traceback
import re

router = APIRouter(tags=["auth"])

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


def _safe_set_search_path(db: Session, schema_name: str):
    # Assumimos schema_name validado previamente
    db.execute(text(f'SET search_path TO "{schema_name}", public'))


@router.post("/auth/token", response_model=Token)
@router.post("/login", response_model=Token)  # mantém compatibilidade com /login
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Requisição deve ser form-urlencoded ou application/json")

    if not username or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Campos de autenticação ausentes (username/email e password).")

    # 1) Tenta autenticar no CENTRAL
    try:
        user = db.query(UserCentral).filter(UserCentral.email == username).first()
    except Exception:
        traceback.print_exc()
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
                    "is_superuser": getattr(user, "is_superuser", False),
                    "nome": getattr(user, "nome", user.email),
                    "role": "SUPERUSER",
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
                "is_admin": True,
                "email": user.email,
            }

    # 2) Autentica em tenants existentes (consulta apenas schemas relevantes)
    try:
        rows = db.execute(text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'public')"
        )).fetchall()
        schemas = [r[0] for r in rows]
    except Exception:
        traceback.print_exc()
        schemas = []

    for schema in schemas:
        # validar schema_name antes de usar
        if not _SCHEMA_RE.match(schema):
            continue
        try:
            # set search_path para o schema seguro (usa aspas)
            _safe_set_search_path(db, schema)
            user_tenant = db.query(UserTenant).filter(UserTenant.email == username).first()
            if not user_tenant:
                continue

            stored_pw_tenant = getattr(user_tenant, "hashed_password", None)
            if not stored_pw_tenant:
                continue

            if verify_password(password, stored_pw_tenant):
                # ler info do tenant no public
                try:
                    db.execute(text('SET search_path TO public'))
                    result = db.execute(
                        text("SELECT nome_empresa, logo_url FROM tenants WHERE schema_name = :schema"),
                        {"schema": schema}
                    ).first()
                    empresa = result[0] if result and result[0] else "Empresa"
                    logoUrl = result[1] if result and result[1] else "/static/logos/logo_almo.png"
                except Exception:
                    traceback.print_exc()
                    empresa = "Empresa"
                    logoUrl = "/static/logos/logo_almo.png"

                access_token_expires = timedelta(minutes=int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)))
                access_token = create_access_token(
                    data={
                        "sub": user_tenant.email,
                        "schema_name": schema,
                        "user_id": user_tenant.id,
                        "nome": getattr(user_tenant, "nome", None),
                        "role": getattr(user_tenant, "role", getattr(user_tenant, "role_id", None)),
                        "is_admin": getattr(user_tenant, "is_admin", False),
                        "empresa": empresa,
                        "logoUrl": logoUrl,
                        "is_superuser": False,
                        "email": user_tenant.email
                    },
                    expires_delta=access_token_expires
                )
                # restaura search_path para public antes de retornar
                try:
                    db.execute(text('SET search_path TO public'))
                except Exception:
                    traceback.print_exc()
                return {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "tenant_id": None,
                    "schema_name": schema,
                    "is_superuser": False,
                    "empresa": empresa,
                    "logoUrl": logoUrl,
                    "nome": getattr(user_tenant, "nome", None),
                    "role": getattr(user_tenant, "role", getattr(user_tenant, "role_id", None)),
                    "is_admin": getattr(user_tenant, "is_admin", False),
                    "email": user_tenant.email
                }
        except Exception:
            traceback.print_exc()
            # restaura search_path para public após erro no schema atual
            try:
                db.execute(text('SET search_path TO public'))
            except Exception:
                traceback.print_exc()
            continue

    # garantir que o search_path volte pra public
    try:
        db.execute(text('SET search_path TO public'))
    except Exception:
        traceback.print_exc()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )