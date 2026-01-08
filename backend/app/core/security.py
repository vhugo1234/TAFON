from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from passlib.context import CryptContext
from passlib.hash import pbkdf2_sha256
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.connection import get_db
import logging

logger = logging.getLogger(__name__)

# Configure CryptContext para suportar bcrypt e pbkdf2_sha256.
# Preferimos bcrypt quando disponível, mas incluímos pbkdf2_sha256
# para compatibilidade com hashes existentes.
pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")

# JWT / OAuth2
ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica a senha fornecida comparando com o hash armazenado.
    - Primeiro tenta pwd_context.verify (suporta bcrypt/pbkdf2).
    - Se houver exceção ou resultado False e o hash for pbkdf2, tenta pbkdf2_sha256.verify direto.
    - Retorna False em qualquer outro caso.
    """
    if not (plain_password and hashed_password):
        return False

    try:
        ok = pwd_context.verify(plain_password, hashed_password)
        if ok:
            return True
    except Exception as exc:
        logger.warning("pwd_context.verify falhou: %s. Tentando fallback pbkdf2 se aplicável.", exc)

    # Fallback explícito para hashes pbkdf2 (caso o pwd_context não consiga verificar)
    try:
        if isinstance(hashed_password, str) and hashed_password.startswith("$pbkdf2-sha256$"):
            return pbkdf2_sha256.verify(plain_password, hashed_password)
    except Exception:
        logger.exception("pbkdf2_sha256.verify falhou no fallback.")

    return False


def get_password_hash(password: str) -> str:
    """
    Gera o hash da senha. Tenta usar pwd_context.hash; em caso de erro faz fallback
    para pbkdf2_sha256.hash para garantir compatibilidade em ambientes sem bcrypt funcional.
    """
    try:
        return pwd_context.hash(password)
    except Exception as exc:
        logger.warning("pwd_context.hash falhou (%s). Fazendo fallback para pbkdf2_sha256.", exc)
        try:
            return pbkdf2_sha256.hash(password)
        except Exception:
            logger.exception("pbkdf2_sha256.hash também falhou.")
            raise


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Cria JWT usando settings.SECRET_KEY e settings.JWT_ALGORITHM.
    """
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


# Dependência para checar superuser central (mantenho compatibilidade com código existente)
def get_current_active_superuser(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
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