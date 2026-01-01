# backend/app/api/deps_tenant.py

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Any, Generator

from app.db.connection import get_db
from app.api.deps import get_current_user  # Presumindo que você tem essa dependência para o JWT

def get_schema_name(current_user: Any) -> str | None:
    """
    Extrai o 'schema_name' do payload do JWT ou do objeto de usuário logado.
    O JWT deve ter sido criado com o 'schema' ou 'schema_name'.
    """
    if isinstance(current_user, dict):
        # Caso o payload JWT venha como dict (comum em `get_current_user`)
        return current_user.get("schema_name") or current_user.get("schema")
    # Caso o resultado do deps.get_current_user seja um objeto
    return getattr(current_user, "schema_name", None)

def get_tenant_db_session(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
) -> Generator[Session, None, None]:
    """
    Dependência que configura o search_path para o schema do tenant logado.
    Esta função deve ser usada em TODOS os endpoints que acessam dados do TAF.
    """
    schema_name = get_schema_name(current_user)

    if not schema_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não foi possível identificar o cliente (tenant) associado ao usuário logado."
        )

    # 1. Configura o search_path: Busca primeiro no schema do tenant, depois no público.
    try:
        # Usamos text() para evitar SQL injection, garantindo que schema_name é seguro
        # antes de ser passado como f-string no texto (o que sua implementação já faz)
        db.execute(text(f"SET search_path TO {schema_name}, public"))
    except Exception as e:
        # A falha aqui pode indicar que o schema não existe ou o nome é inválido
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao configurar o ambiente de dados do cliente: {e}"
        )

    # 2. Yield a sessão configurada para o endpoint
    try:
        yield db
    finally:
        # 3. Restaura o search_path para 'public'
        # Isso é crucial para evitar vazamento de contexto em um pool de conexões
        try:
            db.execute(text("SET search_path TO public"))
            db.close() # Garante que a sessão é fechada e a conexão retornada ao pool
        except Exception:
            # Apenas loga, mas não interrompe a resposta
            pass