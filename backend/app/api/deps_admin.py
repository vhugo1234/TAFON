from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import oauth2_scheme, decode_token
from app.db.connection import get_db
from app.db.models.tenant import UserCentral

def get_current_admin_superuser(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserCentral:
    print(">>> [ADMIN DEP] Dependency chamado")
    print(">>> [ADMIN DEP] Token recebido:", token)
    try:
        print(">>> [ADMIN DEP] Tentando decodificar o token...")
        payload = decode_token(token)
        print(">>> [ADMIN DEP] Payload decodificado:", payload)
    except Exception as e:
        print(">>> [ADMIN DEP] ERRO no decode_token:", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extrair candidate_id (pode ser numeric user_id, tenant_user_id, id, ou email/sub)
    user_id_claim = (
        payload.get("user_id")
        or payload.get("tenant_user_id")
        or payload.get("id")
        or payload.get("sub")  # às vezes sub é o id ou o email
    )
    print(">>> [ADMIN DEP] user_id_claim extraído:", user_id_claim)

    if not user_id_claim:
        print(">>> [ADMIN DEP] Nenhum user_id encontrado no token!")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não contém user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = None

    # 1) Se for inteiro ou string numérica, usar como id
    try:
        if isinstance(user_id_claim, int):
            user = db.query(UserCentral).filter(UserCentral.id == user_id_claim).first()
        elif isinstance(user_id_claim, str):
            stripped = user_id_claim.strip()
            if stripped.isdigit():
                uid = int(stripped)
                user = db.query(UserCentral).filter(UserCentral.id == uid).first()
            elif "@" in stripped:
                # parece email: buscar por email
                user = db.query(UserCentral).filter(UserCentral.email == stripped).first()
    except Exception as e:
        # Log e continue com tentativas de fallback (evita crash por tipo incorreto)
        print(f">>> [ADMIN DEP] Erro ao buscar UserCentral por claim ({user_id_claim}): {e}")
        user = None

    # 2) Se não encontrou ainda, tente claims alternativos (email ou sub)
    if not user:
        email_claim = payload.get("email") or payload.get("sub")
        if email_claim and isinstance(email_claim, str) and "@" in email_claim:
            try:
                user = db.query(UserCentral).filter(UserCentral.email == email_claim).first()
                print(">>> [ADMIN DEP] Tentativa fallback por email_claim:", email_claim, "->", user)
            except Exception as e:
                print(f">>> [ADMIN DEP] Erro ao buscar UserCentral por email_claim ({email_claim}): {e}")
                user = None

    print(">>> [ADMIN DEP] Resultado da busca UserCentral:", user)
    if not user:
        print(">>> [ADMIN DEP] Usuário central não encontrado no banco.")
    elif not user.is_active:
        print(">>> [ADMIN DEP] Usuário encontrado, mas inativo.")
    elif not user.is_superuser:
        print(">>> [ADMIN DEP] Usuário encontrado, mas não é superuser.")
    if not user or not user.is_active or not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário central não existe, está inativo ou não é superuser.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(">>> [ADMIN DEP] Usuário autenticado OK!")
    return user