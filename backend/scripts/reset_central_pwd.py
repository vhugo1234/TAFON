# backend/scripts/reset_central_pwd.py
import os
from app.db.connection import SessionLocal
from app.db.models.public import UserCentral
try:
    from app.core.security import get_password_hash
except Exception:
    get_password_hash = None

from passlib.hash import pbkdf2_sha256 as _pbkdf2

def hash_pwd(pwd: str) -> str:
    if get_password_hash:
        try:
            return get_password_hash(pwd)
        except Exception:
            pass
    if _pbkdf2:
        return _pbkdf2.hash(pwd)
    raise RuntimeError("No hashing function available")

def main():
    email = os.environ.get("TARGET_ADMIN_EMAIL", "admin@almoxarifado.com")
    new_pwd = os.environ.get("TARGET_ADMIN_PASSWORD", "Mudar123!")
    db = SessionLocal()
    try:
        u = db.query(UserCentral).filter(UserCentral.email == email).first()
        if not u:
            print("Usuário central não encontrado:", email)
            return
        u.hashed_password = hash_pwd(new_pwd)
        db.add(u)
        db.commit()
        print("Senha do usuário central atualizada com sucesso para", email)
    finally:
        db.close()

if __name__ == "__main__":
    main()