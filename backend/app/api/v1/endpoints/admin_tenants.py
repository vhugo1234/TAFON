from typing import List, Optional
from datetime import date, datetime
import logging
import re
from contextlib import contextmanager
from typing import Generator
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.connection import get_db, engine
from app.db.models.public import Tenant
from app.api.deps_admin import get_current_admin_superuser  # <--- CORRIGIDO!
from app.core.security import get_password_hash
from app.schemas.tenant_schema import TenantCreate, TenantUpdate, TenantOut, TenantStatus, TenantType
from app.db.models.tenant import UserTenant, UserRoleEnum
from app.db.startup import initialize_tenant_schema

logger = logging.getLogger("app.routers.admin")
router = APIRouter(
    dependencies=[Depends(get_current_admin_superuser)],  # <--- CORRIGIDO!
)

    #tags=["Admin - Clientes"]


# ------------------------------------------------------------------
# 🚨 DEFINIÇÃO DA SENHA PADRÃO TEMPORÁRIA
# ------------------------------------------------------------------
DEFAULT_ADMIN_PASSWORD = "Mudar123!" # ⚠️ SENHA PADRÃO PARA O CLIENTE

# ----------------------
# Helpers e Engine Wrapper
# ----------------------

def get_db_engine():
    """Retorna o objeto engine do SQLAlchemy para uso em comandos DDL (CREATE/DROP SCHEMA)."""
    return engine

_schema_name_re = re.compile(r"^[a-z0-9_]+$")

def _validate_schema_name(name: str) -> bool:
    """Valida se o nome do schema é seguro."""
    return bool(_schema_name_re.match(name))

def _to_iso_string(val) -> Optional[str]:
    """Converte datas e datetime para string ISO 8601 ou None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time()).isoformat()
    return str(val)

def _serialize_tenant(tenant: Tenant) -> dict:
    """
    Serializa um objeto ORM Tenant em um dicionário JSON-serializável,
    usando getattr com fallback para evitar AttributeError em registros antigos.
    """
    nome_empresa = getattr(tenant, "nome_empresa", None) or getattr(tenant, "name", "N/A")
    users_total = getattr(tenant, "users_total", 0)
    assets_total = getattr(tenant, "assets_total", 0)
    last_access = getattr(tenant, "last_access", None)
    return {
        "id": getattr(tenant, "id", None),
        "name": nome_empresa,
        "schema_name": getattr(tenant, "schema_name", "N/A"),
        "status": getattr(tenant, "status", "pending"),
        "tenant_type": getattr(tenant, "plan_type", "starter"),
        "created_at": _to_iso_string(getattr(tenant, "created_at", None)),
        "responsible_name": getattr(tenant, "responsible_name", None),
        "responsible_email": getattr(tenant, "responsible_email", None),
        "responsible_phone": getattr(tenant, "responsible_phone", None),
        "plan_type": getattr(tenant, "plan_type", "starter"),
        "plan_expires_at": _to_iso_string(getattr(tenant, "plan_expires_at", None)),
        "users_total": users_total,
        "assets_total": assets_total,
        "last_access": _to_iso_string(last_access),
        "logo_url": getattr(tenant, "logo_url", None),
        "dominio_url": getattr(tenant, "dominio_url", None),
    }

def _validate_for_put(tenant_in: TenantUpdate) -> None:
    update_data = tenant_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum campo fornecido para atualização."
        )

def _update_tenant_db_object(tenant: Tenant, update_data: dict) -> None:
    for key, value in update_data.items():
        if key in ("status", "plan_type") and isinstance(value, Enum):
            setattr(tenant, key, value.value)
        elif key == "plan_expires_at":
            setattr(tenant, key, _to_iso_string(value))
        elif key == "name":
             setattr(tenant, "nome_empresa", value)
        else:
            setattr(tenant, key, value)

# ------------------------------------------------------------------
# ROTA: LISTAGEM DE TENANTS
# ------------------------------------------------------------------
@router.get("/", response_model=List[TenantOut])
def get_all_tenants(db: Session = Depends(get_db)):
    tenants = db.query(Tenant).all()
    return [_serialize_tenant(t) for t in tenants]

# ------------------------------------------------------------------
# ROTA: OBTENÇÃO DE UM TENANT
# ------------------------------------------------------------------
@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant_by_id(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")
    return _serialize_tenant(tenant)

# ------------------------------------------------------------------
# ROTA: CRIAÇÃO DE UM NOVO TENANT
# ------------------------------------------------------------------
@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_tenant(tenant_in: TenantCreate, db: Session = Depends(get_db)):
    if not _validate_schema_name(tenant_in.schema_name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de schema inválido. Use apenas letras minúsculas, números e underscore.")

    if db.query(Tenant).filter(Tenant.schema_name == tenant_in.schema_name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Um cliente com este nome de schema já existe.")

    # proteger plan_type opcional
    plan_type_value = tenant_in.plan_type.value if tenant_in.plan_type is not None else None

    new_tenant = Tenant(
        nome_empresa=tenant_in.name,
        schema_name=tenant_in.schema_name,
        status=tenant_in.status.value,
        plan_type=plan_type_value,
        plan_expires_at=_to_iso_string(tenant_in.plan_expires_at),
        responsible_name=tenant_in.responsible_name,
        responsible_email=tenant_in.responsible_email,
        responsible_phone=tenant_in.responsible_phone,
        logo_url=tenant_in.logo_url,
        dominio_url=tenant_in.dominio_url,
    )

    admin_password = tenant_in.admin_password
    is_default_password = False

    if not admin_password:
        admin_password = DEFAULT_ADMIN_PASSWORD
        is_default_password = True
        logger.warning(f"Senha de admin padrão usada para o cliente {tenant_in.name}.")

    try:
        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)
    except IntegrityError as e:
        db.rollback()
        if ("duplicate key value violates unique constraint" in str(e)
           and "tenants_pkey" in str(e)):
            db.execute(text("SELECT setval('tenants_id_seq', (SELECT MAX(id) FROM tenants));"))
            db.commit()
            db.add(new_tenant)
            db.commit()
            db.refresh(new_tenant)
        else:
            logger.exception(f"Erro ao criar cliente e usuário admin: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar cliente: {e}")

    # --------------------------------------------------------
    # Provisionamento do schema e criação do admin (corrigido)
    # --------------------------------------------------------
    engine_obj = get_db_engine()
    try:
        # passar o Engine (não a Session) para a função de provisionamento
        initialize_tenant_schema(engine_obj, tenant_in.schema_name)

        # criar o usuário admin em sessão isolada usando SET LOCAL (não alterar a Session db)
        SessionForTenant = sessionmaker(bind=engine_obj, expire_on_commit=False)
        with SessionForTenant() as tenant_sess:
            tenant_sess.execute(text(f'SET LOCAL search_path = "{tenant_in.schema_name}", public'))
            hashed_password = get_password_hash(admin_password)
            admin_user = UserTenant(
                nome=tenant_in.responsible_name or "Admin",
                email=tenant_in.responsible_email,
                hashed_password=hashed_password,
                role=UserRoleEnum.ADMIN,
                is_admin=True,
                is_active=True,
            )
            tenant_sess.add(admin_user)
            tenant_sess.commit()

    except Exception as e:
        db.rollback()
        # tentar cleanup e informar
        try:
            # limpar schema se foi criado parcialmente
            with engine_obj.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{tenant_in.schema_name}" CASCADE'))
        except Exception:
            logger.exception("Falha ao dropar schema após erro de provisionamento.")
        try:
            db.query(Tenant).filter(Tenant.id == new_tenant.id).delete()
            db.commit()
            logger.warning(f"Rollback completo para cliente {tenant_in.name}.")
        except Exception:
            logger.error(f"Falha ao deletar registro central após erro de criação do Admin: {e}")
        logger.exception(f"Erro ao criar cliente e usuário admin: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar cliente: {e}")

    response_data = _serialize_tenant(new_tenant)
    if is_default_password:
        response_data['admin_temp_password'] = DEFAULT_ADMIN_PASSWORD
    return response_data

# ------------------------------------------------------------------
# ROTA: ATUALIZAÇÃO DE UM TENANT
# ------------------------------------------------------------------
@router.put("/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: int, tenant_in: TenantUpdate, db: Session = Depends(get_db)):
    _validate_for_put(tenant_in)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")
    update_data = tenant_in.model_dump(exclude_unset=True)
    try:
        _update_tenant_db_object(tenant, update_data)
        db.commit()
        db.refresh(tenant)
    except Exception as e:
        db.rollback()
        logger.exception(f"Erro ao atualizar cliente: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar cliente: {e}")
    return _serialize_tenant(tenant)

# ------------------------------------------------------------------
# ROTA: DELEÇÃO DE UM TENANT
# ------------------------------------------------------------------
@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")

    schema_name = getattr(tenant, "schema_name", None)
    try:
        db.query(Tenant).filter(Tenant.id == tenant.id).delete()
        db.commit()
        logger.info(f"Registro central do tenant ID {tenant_id} deletado.")
    except Exception as e:
        db.rollback()
        logger.exception("Erro ao deletar tenant (registro central)")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao deletar tenant: {e}")

    if schema_name:
        try:
            if not _validate_schema_name(schema_name):
                 raise ValueError("Nome de schema inválido para DROP.")
            engine_obj = get_db_engine()
            with engine_obj.connect() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
                connection.commit()
            logger.info(f"Schema '{schema_name}' e dados do cliente deletados com sucesso.")
        except Exception:
            logger.exception(f"Falha ao dropar o schema '{schema_name}' do cliente ID {tenant_id}. A deleção do registro central prosseguiu.")

    return {"message": "Cliente deletado com sucesso."}