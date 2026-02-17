#!/usr/bin/env python3
"""
Script para criar usuarios com senha correta no banco
Execute: docker exec -it tafon_backend python scripts/create_users.py
"""

import sys
import os

# Adiciona o path do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from app.core.security import get_password_hash

# Credenciais do banco
DB_USER = os.getenv("DB_USER", "tafon_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your_password")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "tafon_central_db")

# Conexao
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# Senha a ser usada
PASSWORD = "suasenhaforte123"

print("Gerando hash da senha...")
hashed_password = get_password_hash(PASSWORD)
print(f"Hash gerado: {hashed_password[:50]}...")

# Criar usuarios
with engine.connect() as conn:
    # Usuario CENTRAL (Superusuario)
    print("\n" + "="*60)
    print("CRIANDO SUPERUSUARIO CENTRAL (para /admin)")
    print("="*60)
    
    # Verificar se existe
    result = conn.execute(text("SELECT id FROM public.users_central WHERE email = 'admin@almoxarifado.com'"))
    user_exists = result.fetchone() is not None
    
    if user_exists:
        # Atualiza senha
        conn.execute(
            text("UPDATE public.users_central SET hashed_password = :hash WHERE email = 'admin@almoxarifado.com'"),
            {"hash": hashed_password}
        )
        print("? Superusuario admin@almoxarifado.com ATUALIZADO no schema PUBLIC")
    else:
        # Cria novo
        conn.execute(
            text("""
                INSERT INTO public.users_central (email, hashed_password, is_superuser, is_active)
                VALUES (:email, :hash, TRUE, TRUE)
            """),
            {"email": "admin@almoxarifado.com", "hash": hashed_password}
        )
        print("? Superusuario admin@almoxarifado.com CRIADO no schema PUBLIC")
    
    conn.commit()
    
    # Usuario MB1
    print("\n" + "="*60)
    print("CRIANDO USUARIO TENANT MB1")
    print("="*60)
    conn.execute(text("DELETE FROM mb1.user_tenant WHERE email = 'vhugo1234@gmail.com'"))
    conn.execute(
        text("""
            INSERT INTO mb1.user_tenant (nome, email, hashed_password, is_admin, is_active, role)
            VALUES (:nome, :email, :hash, TRUE, TRUE, 'admin')
        """),
        {"nome": "Admin MB1", "email": "vhugo1234@gmail.com", "hash": hashed_password}
    )
    conn.commit()
    print("? Usuario vhugo1234@gmail.com criado no schema mb1")
    
    # Usuario T1 (usa ENUM com ADMIN em maiusculo)
    print("\n" + "="*60)
    print("CRIANDO USUARIO TENANT T1")
    print("="*60)
    conn.execute(text("DELETE FROM t1.user_tenant WHERE email = 'admin@almoxarifado.com'"))
    
    conn.execute(
        text("""
            INSERT INTO t1.user_tenant (nome, email, hashed_password, is_admin, is_active, role)
            VALUES (:nome, :email, :hash, TRUE, TRUE, 'ADMIN'::t1.userroleenum)
        """),
        {"nome": "Admin T1", "email": "admin@almoxarifado.com", "hash": hashed_password}
    )
    conn.commit()
    print("? Usuario admin@almoxarifado.com criado no schema t1")
    
    # Verificar
    print("\n" + "="*60)
    print("VERIFICANDO USUARIOS CRIADOS")
    print("="*60)
    
    print("\n1. SUPERUSUARIO CENTRAL (public.users_central):")
    result = conn.execute(text("""
        SELECT email, is_superuser, is_active, LEFT(hashed_password, 50) as hash 
        FROM public.users_central
    """))
    for row in result:
        print(f"   Email: {row.email}")
        print(f"   Superuser: {row.is_superuser}")
        print(f"   Active: {row.is_active}")
        print(f"   Hash: {row.hash}...")
    
    print("\n2. USUARIOS DE TENANT:")
    result = conn.execute(text("""
        SELECT 'mb1' as schema, email, LEFT(hashed_password, 50) as hash FROM mb1.user_tenant
        UNION ALL
        SELECT 't1' as schema, email, LEFT(hashed_password, 50) as hash FROM t1.user_tenant
    """))
    
    for row in result:
        print(f"   {row.schema}: {row.email} - Hash: {row.hash}...")

print("\n" + "="*60)
print("TODOS OS USUARIOS CRIADOS COM SUCESSO!")
print("="*60)
print("\nCREDENCIAIS:")
print("\n1. LOGIN CENTRAL (Gerenciar Clientes/Tenants):")
print("   Rota: /login")
print("   Email: admin@almoxarifado.com")
print("   Senha: suasenhaforte123")
print("   Acesso: /admin (AdminClientsTab)")
print("\n2. LOGIN TENANT MB1:")
print("   Rota: /login")
print("   Email: vhugo1234@gmail.com")
print("   Senha: suasenhaforte123")
print("   Acesso: /home, /taf")
print("\n3. LOGIN TENANT T1:")
print("   Rota: /login")
print("   Email: admin@almoxarifado.com")
print("   Senha: suasenhaforte123")
print("   Acesso: /home")
print("="*60)
