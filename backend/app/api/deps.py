from fastapi import Depends, HTTPException, status
from typing import Dict, Any

from app.core.security import oauth2_scheme, decode_token

def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Dependência mínima que decodifica o JWT e retorna o payload (claims) como dict.
    Uso:
      current_user = Depends(get_current_user)
    Observações:
      - decode_token já lança HTTPException em caso de token inválido/expirado.
      - Se você preferir retornar um objeto ORM (UserCentral/UserTenant), eu adapto para buscar no DB.
    """
    payload = decode_token(token)  # já lança HTTPException quando inválido
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload