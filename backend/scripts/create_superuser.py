# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
Script para criar superusuario no TAFON
Uso: python scripts/create_superuser.py
"""
import os
import sys

# Adicionar app ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.security import get_password_hash

# Usar variavel de ambiente ou fallback
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://tafon_user:tafon123456@db:5432/tafon_central_db"
    )
)

def create_superuser(email: str, password: str, nome: str = "Super Admin"):
    """
    Cria um superusuario no schema public (users_central).
    
    Args:
        email: Email do superusuario
        password: Senha em texto plano (sera hasheada)
        nome: Nome completo do superusuario
    
    Returns:
        bool: True se criado com sucesso, False caso contrario
    """
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Garantir que estamos no schema public
        db.execute(text("SET search_path TO public"))
        
        # Verificar se ja existe
        result = db.execute(
            text("SELECT id, email FROM users_central WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if result:
            print(f"ERRO: Superusuario com email '{email}' ja existe (ID: {result[0]})!")
            return False
        
        # Hash da senha
        hashed_password = get_password_hash(password)
        
        # Criar superusuario
        db.execute(
            text("""
                INSERT INTO users_central (email, nome, hashed_password, is_superuser, is_active)
                VALUES (:email, :nome, :hashed_password, TRUE, TRUE)
            """),
            {
                "email": email,
                "nome": nome,
                "hashed_password": hashed_password
            }
        )
        db.commit()
        
        print(f"\n{'='*60}")
        print(f"SUCESSO: Superusuario criado com sucesso!")
        print(f"{'='*60}")
        print(f"   Email: {email}")
        print(f"   Nome: {nome}")
        print(f"   Senha: {password}")
        print(f"{'='*60}\n")
        print(f"IMPORTANTE: Guarde essas credenciais em local seguro!")
        print(f"IMPORTANTE: Altere a senha apos o primeiro login!\n")
        
        return True
        
    except Exception as e:
        print(f"\nERRO ao criar superusuario: {e}\n")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            db.close()
        except:
            pass

def main():
    """Funcao principal com input interativo."""
    print("\n" + "="*60)
    print("TAFON - Criacao de Superusuario")
    print("="*60 + "\n")
    
    # Solicitar dados
    email = input("Email do superusuario: ").strip()
    if not email or "@" not in email:
        print("ERRO: Email invalido!")
        sys.exit(1)
    
    password = input("Senha (minimo 8 caracteres): ").strip()
    if len(password) < 8:
        print("ERRO: Senha deve ter pelo menos 8 caracteres!")
        sys.exit(1)
    
    nome = input("Nome completo [Super Admin]: ").strip()
    if not nome:
        nome = "Super Admin"
    
    print(f"\nCriando superusuario...")
    
    success = create_superuser(email, password, nome)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    # Verificar se ha argumentos de linha de comando
    if len(sys.argv) == 4:
        # Modo nao-interativo: python create_superuser.py <email> <senha> <nome>
        email = sys.argv[1]
        password = sys.argv[2]
        nome = sys.argv[3]
        success = create_superuser(email, password, nome)
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1:
        print("Uso: python create_superuser.py [email] [senha] [nome]")
        print("     ou execute sem argumentos para modo interativo")
        sys.exit(1)
    else:
        # Modo interativo
        main()
