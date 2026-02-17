#!/usr/bin/env python3
"""
Cria um admin para o tenant DEFAULT_SCHEMA (t1) e um superuser central.
Uso: defina env INITIAL_ADMIN_PASSWORD para a senha desejada (ou será usado um default).
Execute dentro do container: python /app/scripts/create_admins.py
"""
import os
import sys
from importlib import import_module

# Ajusta o path para permitir importação do package `app` quando o script for executado diretamente
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text, Table, Column, Integer
from sqlalchemy.orm import configure_mappers
from app.db.connection import SessionLocal

# tenta usar o helper de hash da aplicação; fallback para pbkdf2_sha256 se necessário
try:
    from app.core.security import get_password_hash
except Exception:
    get_password_hash = None

# fallback de hash (se get_password_hash não funcionar com bcrypt)
try:
    from passlib.hash import pbkdf2_sha256 as _pbkdf2
except Exception:
    _pbkdf2 = None

DEFAULT_SCHEMA = os.getenv("INITIAL_SCHEMA", "t1")
DEFAULT_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@almoxarifado.com")
ENV_PWD = os.getenv("INITIAL_ADMIN_PASSWORD", None)
DEFAULT_PASSWORD = ENV_PWD if ENV_PWD is not None else "ChangeMe123!"


def truncate_password_to_72_bytes(s: str) -> str:
    """Trunca string para no máximo 72 bytes em UTF-8, preservando caracteres válidos."""
    if not isinstance(s, str):
        s = str(s or "")
    b = s.encode("utf-8")
    if len(b) <= 72:
        return s
    truncated = b[:72]
    for end in range(len(truncated), 0, -1):
        try:
            return truncated[:end].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return ""  # fallback extremo


def hash_password(pwd: str) -> str:
    """Gera hash usando get_password_hash quando disponível; fallback para pbkdf2."""
    if get_password_hash:
        try:
            return get_password_hash(pwd)
        except Exception as e:
            print("Aviso: get_password_hash falhou:", e)
    if _pbkdf2:
        print("Usando pbkdf2_sha256 como fallback para hash.")
        return _pbkdf2.hash(pwd)
    raise RuntimeError("Nenhum mecanismo de hash disponível (get_password_hash e passlib fallback falharam).")


def ensure_public_tenants_placeholder(tenant_mod):
    """
    Adiciona um objeto Table('tenants', schema='public') no metadata do TenantBase
    para permitir que SQLAlchemy resolva ForeignKey("public.tenants.id") quando
    os modelos do tenant usam uma FK qualificada.
    """
    TenantBase = getattr(tenant_mod, "TenantBase", None) if tenant_mod else None
    if TenantBase is None:
        return
    key = "public.tenants"
    try:
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
    except Exception as e:
        print("Aviso: falha ao criar placeholder para public.tenants:", e)


def main():
    pwd_raw = DEFAULT_PASSWORD
    pwd = truncate_password_to_72_bytes(pwd_raw)
    print("Senha raw bytes:", len(pwd_raw.encode("utf-8")), "-> truncada bytes:", len(pwd.encode("utf-8")))
    hashed = hash_password(pwd)

    # Importa modelos
    Tenant = None
    UserCentral = None
    try:
        mod_public = import_module("app.db.models.public")
        Tenant = getattr(mod_public, "Tenant", None)
        UserCentral = getattr(mod_public, "UserCentral", None)
    except Exception as e:
        print("Aviso: não foi possível importar app.db.models.public:", e)

    tenant_mod = None
    try:
        tenant_mod = import_module("app.db.models.tenant")
    except Exception as e:
        # pode ser que modelos estejam organizados de forma diferente
        print("Aviso: não foi possível importar app.db.models.tenant diretamente:", e)

    # Se existe TenantBase, garanta placeholder público antes de configurar mapeadores
    ensure_public_tenants_placeholder(tenant_mod)

    # Forçar mapeadores depois das importações/placeholder para resolver relationships por nome
    try:
        configure_mappers()
        print("configure_mappers() executado com sucesso.")
    except Exception as e:
        print("Aviso: configure_mappers() falhou (continuando):", e)

    UserTenant = getattr(tenant_mod, "UserTenant", None) if tenant_mod else None

    db = SessionLocal()
    try:
        # garantir que tenant existe em public
        if Tenant is None:
            print("ERRO: modelo Tenant não encontrado; abortando.")
            return

        db.execute(text("SET search_path TO public"))
        tenant = db.query(Tenant).filter(Tenant.schema_name == DEFAULT_SCHEMA).first()
        if not tenant:
            print(f"Tenant com schema '{DEFAULT_SCHEMA}' não existe. Criando registro...")
            tenant = Tenant(nome_empresa="Central SaaS", schema_name=DEFAULT_SCHEMA)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print("Tenant criado. ID:", tenant.id)
        else:
            print("Tenant já existe. ID:", tenant.id)

        # Criar schema no DB (se necessário)
        db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DEFAULT_SCHEMA}"'))
        db.commit()

        # Reforçar search_path para inserir no schema do tenant
        db.execute(text(f'SET search_path TO "{DEFAULT_SCHEMA}"'))

        if UserTenant is None:
            print("Aviso: modelo UserTenant não encontrado; pulando criação do usuário tenant.")
        else:
            # checar se já existe
            existing = db.query(UserTenant).filter(UserTenant.email == DEFAULT_EMAIL).first()
            if existing:
                print("Usuário tenant já existe (email=%s). ID: %s" % (DEFAULT_EMAIL, getattr(existing, "id", None)))
            else:
                # montar params mínimos; alguns modelos podem ter colunas diferentes; usamos introspecção
                params = {"nome": "Admin Tenant", "email": DEFAULT_EMAIL, "hashed_password": hashed}
                cols = []
                try:
                    cols = list(UserTenant.__table__.c.keys())
                except Exception:
                    pass
                if "is_admin" in cols:
                    params["is_admin"] = True
                if "is_active" in cols:
                    params["is_active"] = True
                if "role" in cols:
                    # tentar colocar role admin se enum existir
                    role_val = None
                    enum_cls = getattr(tenant_mod, "UserRoleEnum", None) if tenant_mod else None
                    if enum_cls and hasattr(enum_cls, "ADMIN"):
                        role_val = getattr(enum_cls, "ADMIN")
                    params["role"] = role_val if role_val is not None else "admin"
                obj = UserTenant(**{k: v for k, v in params.items() if v is not None})
                db.add(obj)
                db.commit()
                db.refresh(obj)
                print("Usuário tenant criado. ID:", getattr(obj, "id", None))

        # Criar superuser central
        if UserCentral is None:
            print("Aviso: modelo UserCentral não encontrado; pulando criação de superuser central.")
        else:
            db.execute(text("SET search_path TO public"))
            if db.query(UserCentral).filter(UserCentral.email == DEFAULT_EMAIL).first():
                print("Superusuário central já existe. Ignorando.")
            else:
                tenant_id = tenant.id if tenant else None
                tenant_user_id = None
                try:
                    if UserTenant is not None:
                        db.execute(text(f'SET search_path TO "{DEFAULT_SCHEMA}"'))
                        admin = db.query(UserTenant).filter(UserTenant.email == DEFAULT_EMAIL).first()
                        tenant_user_id = getattr(admin, "id", None) if admin else None
                        db.execute(text("SET search_path TO public"))
                except Exception:
                    tenant_user_id = None

                params = {"email": DEFAULT_EMAIL, "hashed_password": hashed, "is_active": True, "is_superuser": True}
                try:
                    cols = list(UserCentral.__table__.c.keys())
                except Exception:
                    cols = []
                if "tenant_id" in cols:
                    params["tenant_id"] = tenant_id
                if "tenant_user_id" in cols:
                    params["tenant_user_id"] = tenant_user_id

                central_user = UserCentral(**{k: v for k, v in params.items() if v is not None})
                db.add(central_user)
                db.commit()
                db.refresh(central_user)
                print("Superusuário central criado. ID:", getattr(central_user, "id", None))

    except Exception as e:
        db.rollback()
        print("ERRO durante criação:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()