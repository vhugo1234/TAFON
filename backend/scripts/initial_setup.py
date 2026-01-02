#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

# Ajusta o path para importar corretamente (assume que este script fica em backend/scripts/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# IMPORT DINÂMICO: garante que todos os módulos em app.db.models sejam carregados
# antes de qualquer criação de tabela / inicialização de mapeadores.
try:
    import pkgutil
    import importlib
    import app.db.models as models_pkg
    for finder, name, ispkg in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(models_pkg.__name__ + "." + name)
    # Agora todos os módulos do pacote app.db.models devem estar importados.
    print("Módulos de app.db.models importados dinamicamente.")
except Exception as e:
    print("Aviso: falha ao importar dinamicamente módulos de app.db.models:", e)

from app.db.connection import Base, engine, SessionLocal
from app.db.models.tenant import Tenant
from app.db.models.user import UserCentral
from app.db.models.user_tenant import UserTenant, UserRole
from app.db.models.item_tenant import ItemTenant
from app.core.security import get_password_hash

# Valores lidos de env vars com fallback
DEFAULT_TENANT_NAME = os.getenv("INITIAL_TENANT_NAME", "Central SaaS")
DEFAULT_SCHEMA = os.getenv("INITIAL_SCHEMA", "t1")
DEFAULT_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@almoxarifado.com")
DEFAULT_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "suasenhaforte123")

def create_initial_schema():
    """Cria apenas as tabelas do esquema central (public / sem schema)."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Criando tabelas do schema central (public)...")
    try:
        central_tables = [
            tbl for tbl in Base.metadata.tables.values()
            if (tbl.schema is None or tbl.schema == '' or tbl.schema == 'public')
        ]
        print("Tabelas centrais para criar:", [tbl.name for tbl in central_tables])
        Base.metadata.create_all(bind=engine, tables=central_tables)
        print("Tabelas do esquema central criadas com sucesso.")
    except Exception as e:
        print(f"ERRO ao criar tabelas do esquema central: {e}")
        sys.exit(1)

def create_initial_tenant():
    """Cria o primeiro tenant central no DB (registro na tabela 'tenants')."""
    db: Session = SessionLocal()
    try:
        db.execute(text("SET search_path TO public"))
        if db.query(Tenant).filter(Tenant.schema_name == DEFAULT_SCHEMA).first():
            print(f"Tenant '{DEFAULT_TENANT_NAME}' (schema {DEFAULT_SCHEMA}) já existe. Ignorando a criação.")
            return

        initial_tenant = Tenant(
            nome_empresa=DEFAULT_TENANT_NAME,
            schema_name=DEFAULT_SCHEMA
        )

        db.add(initial_tenant)
        db.commit()
        db.refresh(initial_tenant)
        print(f"Tenant '{DEFAULT_TENANT_NAME}' criado com sucesso. ID: {initial_tenant.id}")
    except Exception as e:
        db.rollback()
        print(f"ERRO ao criar Tenant inicial: {e}")
        sys.exit(1)
    finally:
        db.close()

def create_initial_tenant_schema_and_user():
    """
    Cria o schema isolado (DEFAULT_SCHEMA) e o usuário Admin dentro dele.
    """
    db: Session = SessionLocal()
    try:
        db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DEFAULT_SCHEMA}"))
        db.commit()
        print(f"Schema '{DEFAULT_SCHEMA}' criado ou já existente.")

        db.execute(text(f"SET search_path TO {DEFAULT_SCHEMA}"))

        # ATENÇÃO: os models devem ter __table_args__ com schema configurado ou base metadata deve criar tabelas
        try:
            UserTenant.__table__.create(bind=engine, checkfirst=True)
            ItemTenant.__table__.create(bind=engine, checkfirst=True)
            db.commit()
            print(f"Tabelas do schema '{DEFAULT_SCHEMA}' criadas com sucesso.")
        except Exception as e:
            db.rollback()
            print(f"Erro ao criar tabelas do schema '{DEFAULT_SCHEMA}': {e}")
            raise

        if not db.query(UserTenant).filter(UserTenant.email == DEFAULT_EMAIL).first():
            hashed_password = get_password_hash(DEFAULT_PASSWORD)
            tenant_admin = UserTenant(
                nome="Admin Central",
                email=DEFAULT_EMAIL,
                hashed_password=hashed_password,
                role=UserRole.ADMIN,
                is_active=True,
                is_admin=True,
            )
            db.add(tenant_admin)
            db.flush()
            try:
                db.refresh(tenant_admin)
            except Exception:
                # tentar obter id via atributos ou através do SELECT
                pass
            db.commit()
            print(f"Usuário Admin de Tenant ('{DEFAULT_SCHEMA}') criado com sucesso (ID: {tenant_admin.id}).")
        else:
            print(f"Usuário Admin de Tenant ('{DEFAULT_SCHEMA}') já existe. Ignorando.")
    except Exception as e:
        db.rollback()
        print(f"ERRO ao criar schema/usuário do Tenant: {e}")
        sys.exit(1)
    finally:
        db.close()

def get_tenant_and_admin_ids():
    """
    Recupera os IDs atuais do tenant central e do respectivo admin.
    """
    db: Session = SessionLocal()
    try:
        db.execute(text("SET search_path TO public"))
        tenant = db.query(Tenant).filter(Tenant.schema_name == DEFAULT_SCHEMA).first()
        admin = None
        if tenant:
            db.execute(text(f"SET search_path TO {DEFAULT_SCHEMA}"))
            admin = db.query(UserTenant).filter(UserTenant.email == DEFAULT_EMAIL).first()
        return (tenant.id if tenant else None), (admin.id if admin else None)
    finally:
        db.close()

def create_initial_superuser():
    """Cria o registro do usuário central (Admin) na tabela 'UserCentral'."""
    db = SessionLocal()
    try:
        db.execute(text("SET search_path TO public"))

        if db.query(UserCentral).filter(UserCentral.email == DEFAULT_EMAIL).first():
            print(f"Usuário inicial '{DEFAULT_EMAIL}' já existe. Ignorando a criação.")
            return

        hashed_password = get_password_hash(DEFAULT_PASSWORD)

        tenant_id, tenant_user_id = get_tenant_and_admin_ids()

        initial_user = UserCentral(
            email=DEFAULT_EMAIL,
            hashed_password=hashed_password,
            tenant_id=tenant_id,
            tenant_user_id=tenant_user_id,
            is_active=True,
            is_superuser=True
        )

        db.add(initial_user)
        db.commit()
        print("\n-------------------------------------")
        print("Superusuário inicial criado com sucesso para o login:")
        print(f"Email: {DEFAULT_EMAIL}")
        print(f"Senha: {DEFAULT_PASSWORD}")
        print("-------------------------------------\n")
    except Exception as e:
        db.rollback()
        print(f"ERRO ao criar Superusuário inicial: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_schema()
    create_initial_tenant()
    create_initial_tenant_schema_and_user()
    create_initial_superuser()