from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import oauth2_scheme, decode_token
from app.db.connection import get_db
# UserCentral está no modelo 'public' — importe do local correto
from app.db.models.public import UserCentral

def get_current_admin_superuser(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserCentral:
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_claim = (
        payload.get("user_id")
        or payload.get("tenant_user_id")
        or payload.get("id")
        or payload.get("sub")
    )

    if not user_id_claim:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não contém user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = None
    try:
        if isinstance(user_id_claim, int):
            user = db.query(UserCentral).filter(UserCentral.id == user_id_claim).first()
        elif isinstance(user_id_claim, str):
            stripped = user_id_claim.strip()
            if stripped.isdigit():
                uid = int(stripped)
                user = db.query(UserCentral).filter(UserCentral.id == uid).first()
            elif "@" in stripped:
                user = db.query(UserCentral).filter(UserCentral.email == stripped).first()
    except Exception:
        user = None

    if not user:
        email_claim = payload.get("email") or payload.get("sub")
        if email_claim and isinstance(email_claim, str) and "@" in email_claim:
            try:
                user = db.query(UserCentral).filter(UserCentral.email == email_claim).first()
            except Exception:
                user = None

    if not user or not getattr(user, "is_active", False) or not getattr(user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário central não existe, está inativo ou não é superuser.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user