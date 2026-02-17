#!/usr/bin/env python3
"""
Script de diagnóstico do TAFON
Verifica conexão com banco, migrações, e configurações essenciais.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import traceback

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://tafon_user:tafon123456@db:5432/tafon_central_db"
    )
)

def check_database_connection():
    """Verifica conexão com o banco de dados."""
    print("?? Verificando conexão com banco de dados...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()")).fetchone()
            print(f"? Conexão OK - PostgreSQL: {result[0].split(',')[0]}")
            return True, engine
    except Exception as e:
        print(f"? Falha na conexão: {e}")
        return False, None

def check_tables(engine):
    """Verifica se as tabelas essenciais existem."""
    print("\n?? Verificando tabelas do schema public...")
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema='public')
        
        required_tables = ['tenants', 'users_central']
        missing = [t for t in required_tables if t not in tables]
        
        if missing:
            print(f"? Tabelas faltando: {', '.join(missing)}")
            print("?? Execute: docker-compose exec backend alembic upgrade head")
            return False
        else:
            print(f"? Tabelas encontradas: {', '.join(tables)}")
            return True
    except Exception as e:
        print(f"? Erro ao verificar tabelas: {e}")
        return False

def check_superuser(engine):
    """Verifica se existe pelo menos um superusuário."""
    print("\n?? Verificando superusuários...")
    try:
        Session = sessionmaker(bind=engine)
        db = Session()
        db.execute(text("SET search_path TO public"))
        
        result = db.execute(
            text("SELECT COUNT(*) FROM users_central WHERE is_superuser = TRUE")
        ).scalar()
        
        if result > 0:
            print(f"? {result} superusuário(s) encontrado(s)")
            
            # Listar emails
            users = db.execute(
                text("SELECT id, email, nome FROM users_central WHERE is_superuser = TRUE")
            ).fetchall()
            for user in users:
                print(f"   • ID {user[0]}: {user[1]} ({user[2]})")
            return True
        else:
            print("? Nenhum superusuário encontrado")
            print("?? Execute: docker-compose exec backend python scripts/create_superuser.py")
            return False
    except Exception as e:
        print(f"? Erro ao verificar superusuários: {e}")
        return False
    finally:
        db.close()

def check_tenants(engine):
    """Lista tenants existentes."""
    print("\n?? Verificando tenants (clientes)...")
    try:
        Session = sessionmaker(bind=engine)
        db = Session()
        db.execute(text("SET search_path TO public"))
        
        result = db.execute(
            text("SELECT COUNT(*) FROM tenants")
        ).scalar()
        
        if result > 0:
            print(f"? {result} tenant(s) encontrado(s)")
            
            # Listar tenants
            tenants = db.execute(
                text("SELECT id, schema_name, nome_empresa FROM tenants")
            ).fetchall()
            for tenant in tenants:
                print(f"   • ID {tenant[0]}: {tenant[1]} ({tenant[2] or 'Sem nome'})")
                
                # Verificar se schema existe
                schema_exists = db.execute(
                    text("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = :schema"),
                    {"schema": tenant[1]}
                ).scalar()
                
                if schema_exists:
                    print(f"     ? Schema '{tenant[1]}' existe")
                else:
                    print(f"     ? Schema '{tenant[1]}' NÃO existe!")
            return True
        else:
            print("??  Nenhum tenant encontrado")
            print("?? Crie um tenant via Admin Dashboard ou API")
            return True  # Não é erro crítico
    except Exception as e:
        print(f"? Erro ao verificar tenants: {e}")
        return False
    finally:
        db.close()

def check_environment():
    """Verifica variáveis de ambiente essenciais."""
    print("\n?? Verificando variáveis de ambiente...")
    
    required_vars = {
        'SECRET_KEY': 'Chave secreta para JWT',
        'DB_USER': 'Usuário do banco de dados',
        'DB_PASSWORD': 'Senha do banco de dados',
        'DB_NAME': 'Nome do banco de dados',
    }
    
    all_ok = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mascarar valores sensíveis
            if 'PASSWORD' in var or 'SECRET' in var:
                display_value = '*' * len(value)
            else:
                display_value = value
            print(f"? {var} = {display_value}")
        else:
            print(f"? {var} não definida ({description})")
            all_ok = False
    
    return all_ok

def main():
    """Função principal."""
    print("\n" + "="*60)
    print("?? TAFON - Diagnóstico de Saúde do Sistema")
    print("="*60 + "\n")
    
    checks = []
    
    # Check 1: Variáveis de ambiente
    checks.append(("Variáveis de Ambiente", check_environment()))
    
    # Check 2: Conexão com banco
    db_ok, engine = check_database_connection()
    checks.append(("Conexão com Banco", db_ok))
    
    if engine:
        # Check 3: Tabelas
        checks.append(("Tabelas do Schema Public", check_tables(engine)))
        
        # Check 4: Superusuários
        checks.append(("Superusuários", check_superuser(engine)))
        
        # Check 5: Tenants
        checks.append(("Tenants", check_tenants(engine)))
    
    # Resumo
    print("\n" + "="*60)
    print("?? RESUMO")
    print("="*60)
    
    all_ok = True
    for check_name, status in checks:
        icon = "?" if status else "?"
        print(f"{icon} {check_name}")
        if not status:
            all_ok = False
    
    print("="*60)
    
    if all_ok:
        print("\n?? Todos os checks passaram! Sistema pronto para uso.\n")
        sys.exit(0)
    else:
        print("\n??  Alguns checks falharam. Revise os erros acima.\n")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n??  Diagnóstico interrompido pelo usuário.\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n? Erro fatal: {e}\n")
        traceback.print_exc()
        sys.exit(1)
