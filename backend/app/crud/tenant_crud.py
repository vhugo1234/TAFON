from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status
from app.db.connection import engine
# Tenant (registro central) deve vir do módulo 'public'
from app.db.models.public import Tenant
# Modelos tenant-specific e TenantBase do módulo tenant
from app.db.models.tenant import (
    TenantBase,
    Event,
    Exercise,
    PassCriteria,
    Candidate,
    ExecutionResult,
    UserTenant,
)
from app.db.models.role_tenant import RoleTenant
from app.schemas.tenant_schema import TenantCreate
from app.db.startup import insert_default_roles_tenant  # implemente para usar engine e schema

# Lista dos modelos tenant-specific (se quiser manter explícito)
TENANT_SPECIFIC_MODELS = [
    UserTenant,
    RoleTenant,
    Event,
    Exercise,
    PassCriteria,
    Candidate,
    ExecutionResult,
]

class CRUDTenant:
    def create_tenant_with_schema(self, db: Session, tenant_in: TenantCreate) -> Tenant:
        new_tenant_data = tenant_in.model_dump()
        schema_name = new_tenant_data.pop("schema_name")

        new_tenant = Tenant(
            schema_name=schema_name,
            nome_empresa=new_tenant_data.get("name"),
            # preencha outros campos se necessário
        )

        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)

        # Validação simples do nome do schema
        if not schema_name or not schema_name.replace("_", "").isalnum():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de schema inválido.")

        try:
            # Cria schema e as tabelas do TenantBase dentro de uma transação DDL
            with engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
                # seta search_path para criar tabelas no schema correto
                conn.execute(text(f'SET search_path TO "{schema_name}", public'))
                TenantBase.metadata.create_all(bind=conn)
        except Exception as e:
            # cleanup: remover registro central se falhar o provisionamento
            db.rollback()
            try:
                db.query(Tenant).filter(Tenant.id == new_tenant.id).delete()
                db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Falha ao provisionar schema '{schema_name}': {e}"
            )

        try:
            # Inserir papéis/seed no schema do tenant — implementado para aceitar engine + schema
            insert_default_roles_tenant(engine, schema_name)
        except Exception as e:
            # Log e prosseguir (ou considerar rollback completo dependendo do caso)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao inserir roles padrão: {e}")

        return new_tenant

tenant_crud = CRUDTenant()
