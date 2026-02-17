from app.db.connection import SessionLocal, engine
from app.core.security import get_password_hash
from sqlalchemy import text
import os
import traceback

TARGET_EMAIL = os.environ.get("TARGET_ADMIN_EMAIL", "admin@almoxarifado.com")
TARGET_PASSWORD = os.environ.get("TARGET_ADMIN_PASSWORD", "Mudar123!")

def update_central(db):
    try:
        row = db.execute(text("SELECT id FROM public.users_central WHERE email = :email"), {"email": TARGET_EMAIL}).fetchone()
        if not row:
            print("central: usuário não encontrado:", TARGET_EMAIL)
            return
        new_hash = get_password_hash(TARGET_PASSWORD)
        db.execute(
            text("UPDATE public.users_central SET hashed_password = :hp WHERE email = :email"),
            {"hp": new_hash, "email": TARGET_EMAIL}
        )
        db.commit()
        print("central: hashed_password atualizado para", TARGET_EMAIL)
    except Exception:
        traceback.print_exc()
        try:
            db.rollback()
        except Exception:
            pass

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
                    # verifica se tabela existe no schema
                    tbl = f'{schema}.user_tenant'
                    exists = conn.execute(text("SELECT to_regclass(:tbl)"), {"tbl": tbl}).scalar()
                    if not exists:
                        print(f"{schema}: tabela user_tenant não encontrada; pulando")
                        continue
                    new_hash = get_password_hash(TARGET_PASSWORD)
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
    db = SessionLocal()
    try:
        update_central(db)
    finally:
        db.close()

    update_tenants()
    print("Concluído. Recomenda-se testar login e depois mudar a senha em produção.")

if __name__ == "__main__":
    main()