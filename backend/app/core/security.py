# backend/app/core/security.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.connection import get_db

# DEFINIÇÕES IMPORTANTES (declaradas antes do uso)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")

# OAuth2 scheme — deve estar disponível antes de qualquer Depends(oauth2_scheme)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Funções de hashing / verificação
def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not (plain_password and hashed_password):
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# JWT
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta is None:
        minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
        expires_delta = timedelta(minutes=int(minutes))
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    secret = getattr(settings, "SECRET_KEY", None)
    if not secret:
        raise RuntimeError("SECRET_KEY não está definido em app.core.config.settings")
    token = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    return token

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    secret = getattr(settings, "SECRET_KEY", None)
    if not secret:
        raise RuntimeError("SECRET_KEY não está definido em app.core.config.settings")
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def decode_token(token: str) -> Dict[str, Any]:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

# Dependência pronta para validar superuser central (usada por vários módulos)
def get_current_active_superuser(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    # import local para evitar import circular no topo
    from app.db.models.public import UserCentral

    payload = decode_token(token)

    user_id_claim = (
        payload.get("user_id")
        or payload.get("tenant_user_id")
        or payload.get("id")
        or payload.get("sub")
        or payload.get("email")
    )

    user = None
    try:
        if isinstance(user_id_claim, int):
            user = db.query(UserCentral).filter(UserCentral.id == user_id_claim).first()
        elif isinstance(user_id_claim, str):
            stripped = user_id_claim.strip()
            if stripped.isdigit():
                user = db.query(UserCentral).filter(UserCentral.id == int(stripped)).first()
            elif "@" in stripped:
                user = db.query(UserCentral).filter(UserCentral.email == stripped).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erro ao validar usuário (consulta ao banco).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user or not getattr(user, "is_active", False) or not getattr(user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não existe, está inativo ou não tem privilégios de superuser.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user