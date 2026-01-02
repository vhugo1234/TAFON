# backend/app/api/deps_tenant.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Any, Generator

from app.db.connection import get_db
from app.api.deps import get_current_user  # depende de sua implementação de auth

def _validate_schema_name(schema_name: str) -> bool:
    return bool(schema_name and schema_name.replace("_", "").isalnum())

def get_schema_name(current_user: Any) -> str | None:
    if isinstance(current_user, dict):
        return current_user.get("schema_name") or current_user.get("schema")
    return getattr(current_user, "schema_name", None)

def get_tenant_db_session(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
) -> Generator[Session, None, None]:
    schema_name = get_schema_name(current_user)
    if not schema_name or not _validate_schema_name(schema_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não foi possível identificar ou validar o cliente (tenant)."
        )

    try:
        # usar aspas duplas para identificar schema name com segurança após validação
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao configurar o ambiente de dados do cliente: {e}"
        )

    try:
        yield db
    finally:
        try:
            db.execute(text('SET search_path TO public'))
        except Exception:
            pass