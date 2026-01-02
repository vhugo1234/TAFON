from fastapi import APIRouter, Body, HTTPException, status
from typing import Dict

router = APIRouter()

@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
def request_reset(email: str = Body(..., embed=True)):
    # Implementar lógica real: gerar token, enviar email.
    # Por agora retornamos OK (stub).
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Email inválido")
    return {"ok": True, "message": "Se o email existir, instruções foram enviadas."}

@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
def confirm_reset(token: str = Body(...), new_password: str = Body(...)):
    # Implementar validação do token e alteração de senha.
    return {"ok": True, "message": "Senha atualizada (stub)."}