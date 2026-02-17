#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text, Table, Column, Integer
import pkgutil
import importlib

# Ajusta o path para importar corretamente (assume que este script fica em backend/scripts/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# IMPORT DINÂMICO: importa recursivamente todos os módulos do pacote app.db.models
# (usa walk_packages para incluir subpackages)
try:
    import app.db.models as models_pkg

    def import_all_models(package):
        for finder, name, ispkg in pkgutil.walk_packages(package.__path__, prefix=package.__name__ + "."):
            try:
                importlib.import_module(name)
            except Exception as ie:
                # não falhar aqui — continuamos tentando importar outros módulos
                print(f"Aviso: falha ao importar {name}: {ie}")

    import_all_models(models_pkg)
    print("Módulos de app.db.models importados recursivamente.")
except Exception as e:
    print("Aviso: falha ao importar dinamicamente módulos de app.db.models:", e)

# Tentar forçar configuração de mapeadores depois de importar tudo
try:
    from sqlalchemy.orm import configure_mappers

    try:
        configure_mappers()
        print("configure_mappers() executado com sucesso.")
    except Exception as cm_err:
        # Se falhar, mostramos a mensagem e tentamos um conjunto adicional de imports heurísticos
        print("Aviso: configure_mappers() falhou inicialmente:", cm_err)
        # heurística: tentar importar módulos que costumam conter dependências por nome
        heuristics = (
            "app.db.models.role_tenant",
            "app.db.models.user_tenant",
            "app.db.models.pass_criteria",
            "app.db.models.exercises",
        )
        for m in heuristics:
            try:
                importlib.import_module(m)
            except Exception:
                pass
        # tentar novamente
        try:
            configure_mappers()
            print("configure_mappers() executado com sucesso após heurística de import.")
        except Exception as second_err:
            print("Aviso: configure_mappers() ainda falhou após heurística:", second_err)
            # continuamos; o script tentará criar tabelas e só instanciar modelos se possível
except Exception as e:
    print("Aviso: não foi possível importar configure_mappers():", e)

# conexões / Base / Session
try:
    from app.db.connection import Base, engine, SessionLocal
except Exception as e:
    print("ERRO: não foi possível importar Base/engine/SessionLocal de app.db.connection:", e)
    raise

# Tenta localizar os modelos nas possíveis localizações, com fallback e mensagens claras
Tenant = None
UserCentral = None
try:
    # modelo central de tenants (normalmente em app.db.models.public)
    from app.db.models.public import Tenant, UserCentral

    Tenant = Tenant
    UserCentral = UserCentral
except Exception:
    try:
        from app.db.models.tenant import Tenant as TenantFallback

        Tenant = TenantFallback
    except Exception:
        Tenant = None

# UserTenant, ItemTenant e enum/const para role (tentativa padrão)
UserTenant = None
ItemTenant = None
UserRoleConst = None
try:
    from app.db.models.tenant import (
        UserTenant as UserTenantModel,
        ItemTenant as ItemTenantModel,
        UserRoleEnum as UserRoleEnumModel,
    )

    UserTenant = UserTenantModel
    ItemTenant = ItemTenantModel
    UserRoleConst = UserRoleEnumModel
except Exception:
    # tentar outros caminhos / nomes
    try:
        from app.db.models.tenant import UserTenant as UserTenantModel2, UserRole as UserRoleModel2

        UserTenant = UserTenantModel2
        UserRoleConst = UserRoleModel2
    except Exception:
        # manter None e tratar mais abaixo
        pass

# Segurança (hash de senha)
try:
    from app.core.security import get_password_hash
except Exception as e:
    print("ERRO: não foi possível importar get_password_hash de app.core.security:", e)
    get_password_hash = None

# Valores lidos de env vars com fallback
DEFAULT_TENANT_NAME = os.getenv("INITIAL_TENANT_NAME", "Central SaaS")
DEFAULT_SCHEMA = os.getenv("INITIAL_SCHEMA", "t1")
DEFAULT_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@almoxarifado.com")
DEFAULT_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "suasenhaforte123")


def truncate_password_to_72_bytes(s: str) -> str:
    """
    Retorna uma string que, quando codificada em UTF-8, ocupa no máximo 72 bytes.
    Preserva caracteres UTF-8 válidos (remove bytes finais incompletos).
    """
    if not isinstance(s, str):
        s = str(s or "")
    b = s.encode("utf-8")
    if len(b) <= 72:
        return s
    truncated = b[:72]
    # tentar decodificar; se houver corte no meio de um caractere UTF-8,
    # remover bytes finais até decodificar corretamente
    for end in range(len(truncated), 0, -1):
        try:
            return truncated[:end].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return ""  # fallback extremo (não deve ocorrer)


def create_initial_schema():
    """Cria apenas as tabelas do esquema central (public / sem schema)."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Criando tabelas do schema central (public)...")
    public_base = None
    try:
        mod_public = importlib.import_module("app.db.models.public")
        public_base = getattr(mod_public, "Base", None)
    except Exception:
        public_base = None

    # Se encontramos public_base, usamos sua metadata; caso contrário usamos o Base exportado por app.db.connection
    metadata_source = None
    if public_base is not None:
        print("Usando Base de app.db.models.public para criar tabelas centrais.")
        metadata_source = public_base.metadata
    elif Base is not None:
        print("Usando Base de app.db.connection para criar tabelas centrais (fallback).")
        metadata_source = Base.metadata
    else:
        print("ERRO: nenhum Base disponível para criar tabelas centrais.")
        sys.exit(1)

    try:
        central_tables = [
            tbl
            for tbl in metadata_source.tables.values()
            if (tbl.schema is None or tbl.schema == "" or tbl.schema == "public")
        ]
        print("Tabelas centrais para criar:", [tbl.name for tbl in central_tables])
        # cria apenas as tabelas centrais
        metadata_source.create_all(bind=engine, tables=central_tables)
        print("Tabelas do esquema central criadas com sucesso.")
    except Exception as e:
        print(f"ERRO ao criar tabelas do esquema central: {e}")
        sys.exit(1)


def create_initial_tenant():
    """Cria o primeiro tenant central no DB (registro na tabela 'tenants')."""
    if Tenant is None:
        print("ERRO: modelo 'Tenant' não encontrado. Não foi possível criar registro de tenant central.")
        return

    db: Session = SessionLocal()
    try:
        db.execute(text("SET search_path TO public"))
        if db.query(Tenant).filter(Tenant.schema_name == DEFAULT_SCHEMA).first():
            print(f"Tenant '{DEFAULT_TENANT_NAME}' (schema {DEFAULT_SCHEMA}) já existe. Ignorando a criação.")
            return

        initial_tenant = Tenant(nome_empresa=DEFAULT_TENANT_NAME, schema_name=DEFAULT_SCHEMA)

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
    Cria o schema isolado (DEFAULT_SCHEMA) e as tabelas do tenant (usando TenantBase.metadata quando disponível),
    e cria o usuário Admin dentro dele.
    """
    # Import dinâmico do módulo tenant para pegar UserTenant, ItemTenant, TenantBase e UserRoleEnum
    try:
        tenant_mod = importlib.import_module("app.db.models.tenant")
    except Exception:
        tenant_mod = None

    UserTenantLocal = getattr(tenant_mod, "UserTenant", None) if tenant_mod else None
    ItemTenantLocal = getattr(tenant_mod, "ItemTenant", None) if tenant_mod else None
    TenantBase = getattr(tenant_mod, "TenantBase", None) if tenant_mod else None
    UserRoleConstLocal = getattr(tenant_mod, "UserRoleEnum", None) if tenant_mod else None

    if UserTenantLocal is None and ItemTenantLocal is None and TenantBase is None:
        print("ERRO: modelo 'UserTenant' não encontrado. Não é possível criar usuário do tenant.")
        return

    db: Session = SessionLocal()
    try:
        # Criar schema se não existir
        db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DEFAULT_SCHEMA}"'))
        db.commit()
        print(f"Schema '{DEFAULT_SCHEMA}' criado ou já existente.")

        # Agora, criar as tabelas do tenant no schema apropriado.
        # Use TenantBase.metadata quando disponível; caso contrário tente criar tabelas individuais.
        with engine.begin() as conn:
            # garantir que a search_path é definida na mesma conexão
            conn.exec_driver_sql(f'SET search_path TO "{DEFAULT_SCHEMA}"')

            if TenantBase is not None:
                # garantir que a tabela public.tenants esteja visível no metadata do TenantBase para resolução de FK
                try:
                    key = "public.tenants"
                    if key not in TenantBase.metadata.tables:
                        Table(
                            "tenants",
                            TenantBase.metadata,
                            Column("id", Integer, primary_key=True),
                            schema="public",
                            extend_existing=True,
                        )
                        print("Placeholder Table('public.tenants') criado no TenantBase.metadata para resolver FKs.")
                    else:
                        print("Tabela public.tenants já presente no TenantBase.metadata.")
                except Exception as _e:
                    print("Aviso: falha ao criar placeholder para public.tenants no TenantBase.metadata:", _e)

                # Cria todas as tabelas do TenantBase (no schema selecionado)
                TenantBase.metadata.create_all(bind=conn)
                print(f"Tabelas do schema '{DEFAULT_SCHEMA}' criadas via TenantBase.metadata.")
            else:
                # fallback: criar tabelas individuais se disponíveis
                if hasattr(UserTenantLocal, "__table__"):
                    UserTenantLocal.__table__.create(bind=conn, checkfirst=True)
                if ItemTenantLocal and hasattr(ItemTenantLocal, "__table__"):
                    ItemTenantLocal.__table__.create(bind=conn, checkfirst=True)
                print(f"Tabelas do schema '{DEFAULT_SCHEMA}' criadas via __table__.create (fallback).")

        # Criar admin do tenant se não existir
        # Reabrir sessão para operar no schema
        db = SessionLocal()
        db.execute(text(f'SET search_path TO "{DEFAULT_SCHEMA}"'))
        if UserTenantLocal and not db.query(UserTenantLocal).filter(UserTenantLocal.email == DEFAULT_EMAIL).first():
            if get_password_hash is None:
                print("ERRO: get_password_hash não disponível; não é possível criar usuário com senha.")
                return
            # Truncar a senha para 72 bytes (em UTF-8) para evitar erro do bcrypt
            pwd_to_use = truncate_password_to_72_bytes(DEFAULT_PASSWORD)
            hashed_password = get_password_hash(pwd_to_use)

            # decide valor para o campo 'role' — tenta usar enum/const quando disponível
            role_value = None
            if UserRoleConstLocal is not None:
                if hasattr(UserRoleConstLocal, "ADMIN"):
                    role_value = getattr(UserRoleConstLocal, "ADMIN")
            if role_value is None:
                role_value = "admin"

            params = {"nome": "Admin Tenant", "email": DEFAULT_EMAIL, "hashed_password": hashed_password}
            # se o modelo tem coluna 'role' use-a
            try:
                cols = list(UserTenantLocal.__table__.c.keys())
            except Exception:
                cols = []

            if "role" in cols:
                params["role"] = role_value

            tenant_admin = UserTenantLocal(**params)
            db.add(tenant_admin)
            db.commit()
            print(f"Usuário Admin de Tenant ('{DEFAULT_SCHEMA}') criado com sucesso (ID: {getattr(tenant_admin, 'id', None)}).")
        else:
            print(f"Usuário Admin de Tenant ('{DEFAULT_SCHEMA}') já existe. Ignorando.")
    except Exception as e:
        db.rollback()
        print(f"ERRO ao criar schema/usuário do Tenant: {e}")
        sys.exit(1)
    finally:
        try:
            db.close()
        except Exception:
            pass


def get_tenant_and_admin_ids():
    """
    Recupera os IDs atuais do tenant central e do respectivo admin.
    """
    db: Session = SessionLocal()
    try:
        db.execute(text("SET search_path TO public"))
        tenant = None
        try:
            if Tenant is not None:
                tenant = db.query(Tenant).filter(Tenant.schema_name == DEFAULT_SCHEMA).first()
        except Exception:
            tenant = None

        admin = None
        if tenant:
            db.execute(text(f'SET search_path TO "{DEFAULT_SCHEMA}"'))
            try:
                # usar UserTenant importado globalmente se disponível
                lookup_user_tenant = UserTenant if UserTenant is not None else None
                if lookup_user_tenant is None:
                    # tentar importar dinamicamente
                    try:
                        m = importlib.import_module("app.db.models.tenant")
                        lookup_user_tenant = getattr(m, "UserTenant", None)
                    except Exception:
                        lookup_user_tenant = None
                if lookup_user_tenant:
                    admin = db.query(lookup_user_tenant).filter(lookup_user_tenant.email == DEFAULT_EMAIL).first()
            except Exception:
                admin = None
        return (tenant.id if tenant else None), (admin.id if admin else None)
    finally:
        db.close()


def create_initial_superuser():
    """Cria o registro do usuário central (Admin) na tabela 'UserCentral'."""
    if UserCentral is None:
        print("ERRO: modelo 'UserCentral' não encontrado. Não foi possível criar superusuário central.")
        return

    if get_password_hash is None:
        print("ERRO: get_password_hash não disponível; não é possível criar superusuário com senha.")
        return

    db = SessionLocal()
    try:
        db.execute(text("SET search_path TO public"))

        if db.query(UserCentral).filter(UserCentral.email == DEFAULT_EMAIL).first():
            print(f"Usuário inicial '{DEFAULT_EMAIL}' já existe. Ignorando a criação.")
            return

        # Truncar senha para 72 bytes (em UTF-8) para bcrypt
        pwd_to_use = truncate_password_to_72_bytes(DEFAULT_PASSWORD)
        hashed_password = get_password_hash(pwd_to_use)

        tenant_id, tenant_user_id = get_tenant_and_admin_ids()

        params = {"email": DEFAULT_EMAIL, "hashed_password": hashed_password, "is_active": True, "is_superuser": True}

        # incluir tenant references se existirem nas colunas
        try:
            cols = list(UserCentral.__table__.c.keys())
        except Exception:
            cols = []

        if "tenant_id" in cols:
            params["tenant_id"] = tenant_id
        if "tenant_user_id" in cols:
            params["tenant_user_id"] = tenant_user_id

        initial_user = UserCentral(**params)

        db.add(initial_user)
        db.commit()
        print("\n-------------------------------------")
        print("Superusuário inicial criado com sucesso para o login:")
        print(f"Email: {DEFAULT_EMAIL}")
        print("Senha: (truncada para 72 bytes se original maior)")
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