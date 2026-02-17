#!/usr/bin/env python3
"""
Atualiza hashed_password para o email TARGET_ADMIN_EMAIL em public.users_central
e em todos os schemas de tenant que contenham user_tenant, gerando um hash
usando passlib.hash.pbkdf2_sha256 (não depende de bcrypt).
Uso (dentro do container): PYTHONPATH=/app python scripts/reset_to_pbkdf2.py
"""
from passlib.hash import pbkdf2_sha256
from app.db.connection import engine, SessionLocal
from sqlalchemy import text
import os, traceback

TARGET_EMAIL = os.environ.get("TARGET_ADMIN_EMAIL", "admin@almoxarifado.com")
TARGET_PASSWORD = os.environ.get("TARGET_ADMIN_PASSWORD", "Mudar123!")

def update_central():
    db = SessionLocal()
    try:
        row = db.execute(text("SELECT id FROM public.users_central WHERE email = :email"), {"email": TARGET_EMAIL}).fetchone()
        if not row:
            print("central: usuário não encontrado:", TARGET_EMAIL)
            return
        new_hash = pbkdf2_sha256.hash(TARGET_PASSWORD)
        db.execute(text("UPDATE public.users_central SET hashed_password = :hp WHERE email = :email"),
                   {"hp": new_hash, "email": TARGET_EMAIL})
        db.commit()
        print("central: hashed_password atualizado para", TARGET_EMAIL)
    except Exception:
        traceback.print_exc()
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()

def update_tenants():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('information_schema','pg_catalog','public')"
            )).fetchall()
            schemas = [r[0] for r in rows]
            if not schemas:
                print("nenhum schema de tenant encontrado")
                return
            for schema in schemas:
                try:
                    # verifica se tabela user_tenant existe no schema
                    exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": f"{schema}.user_tenant"}).scalar()
                    if not exists:
                        print(f"{schema}: tabela user_tenant não encontrada; pulando")
                        continue
                    new_hash = pbkdf2_sha256.hash(TARGET_PASSWORD)
                    trans = conn.begin()
                    try:
                        conn.execute(
                            text(f'UPDATE "{schema}".user_tenant SET hashed_password = :hp WHERE email = :email'),
                            {"hp": new_hash, "email": TARGET_EMAIL}
                        )
                        trans.commit()
                        print(f"{schema}: hashed_password atualizado para {TARGET_EMAIL}")
                    except Exception:
                        trans.rollback()
                        raise
                except Exception:
                    print(f"{schema}: erro ao atualizar user_tenant")
                    traceback.print_exc()
    except Exception:
        traceback.print_exc()

def main():
    print("TARGET_EMAIL =", TARGET_EMAIL)
    print("Atualizando central...")
    update_central()
    print("Atualizando tenants...")
    update_tenants()
    print("Concluído. Teste o login em seguida.")

if __name__ == "__main__":
    main()