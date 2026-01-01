from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status
from app.db.connection import engine
# Importa o modelo central (Tenant) e todos os modelos TAF
from app.db.models.tenant import (
    Tenant, 
    Event, 
    Exercise, 
    PassCriteria, 
    Candidate, 
    ExecutionResult
)
from app.schemas.tenant_schema import TenantCreate
from app.db.models.base import Base

# Modelos de usuário/papel que são fundamentais
from app.db.models.user_tenant import UserTenant
from app.db.models.role_tenant import RoleTenant 

# AVISO: ItemTenant e AcessorioTenant removidos desta lista por solicitação do usuário.

from app.db.startup import insert_default_roles_tenant  # critical PATCH!

# LISTA CORRIGIDA E COMPLETA: SOMENTE os modelos necessários para o TAF
TENANT_SPECIFIC_MODELS = [
    # Modelos de Acesso e Infra que são necessários para o sistema (User/Role)
    UserTenant, 
    RoleTenant,    
    
    # Modelos do TAF (Agora incluídos para criação)
    Event,
    Exercise,
    PassCriteria,
    Candidate,
    ExecutionResult,
]

class CRUDTenant:
    def create_tenant_with_schema(self, db: Session, tenant_in: TenantCreate) -> Tenant:
        """
        Cria o registro do Tenant no DB central e, em seguida, 
        cria o schema e as tabelas isoladas do Tenant, e garante papéis padrão.
        """
        new_tenant_data = tenant_in.model_dump()
        schema_name = new_tenant_data.pop("schema_name")
        
        new_tenant = Tenant(
            schema_name=schema_name,
            nome_empresa=new_tenant_data["name"],
            # Adicione outros campos do tenant conforme sua necessidade
        )
        
        db.add(new_tenant)
        db.commit() 
        db.refresh(new_tenant)

        try:
            print(f"Tentando criar o schema isolado: {schema_name}")
            db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            db.commit()
            print(f"Schema {schema_name} criado com sucesso.")

        except Exception as e:
            db.rollback()
            print(f"ERRO: Falha ao criar o schema '{schema_name}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Falha ao criar o schema do cliente: {schema_name}. Detalhe: {e}"
            )
        
        try:
            with engine.connect() as connection:
                tables_to_create = []
                for model in TENANT_SPECIFIC_MODELS:
                    # O loop agora usa a lista COMPLETA de modelos TAF + User/Role
                    table_obj = model.__table__.to_metadata(Base.metadata)
                    table_obj.schema = schema_name
                    tables_to_create.append(table_obj)

                Base.metadata.create_all(connection, tables=tables_to_create, checkfirst=True)
                # connection.commit() # Não é estritamente necessário em create_all

            print(f"Tabelas específicas do Tenant criadas no schema {schema_name}.")

            # PATCH: Garante papéis padrão no schema do tenant!
            insert_default_roles_tenant(db, schema_name)
            print(f"Papéis padrão inseridos para o tenant {schema_name}.")

            return new_tenant

        except Exception as e:
            db.rollback()
            print(f"ERRO: Falha ao criar tabelas no schema '{schema_name}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Falha ao criar tabelas do cliente: {schema_name}. Detalhe: {e}"
            )

tenant_crud = CRUDTenant()
