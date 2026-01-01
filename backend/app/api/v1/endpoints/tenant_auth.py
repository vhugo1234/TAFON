from fastapi import APIRouter, Depends, HTTPException, status, Path
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.connection import get_db
from app.db.models.tenant import UserTenant
from app.core.security import verify_password, create_access_token

router = APIRouter(
    prefix="/tenants/{schema_name}/auth",
    tags=["Tenant Auth"]
)

@router.post("/login")
def login_tenant_user(
    schema_name: str = Path(..., min_length=1),
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    try:
        db.execute(text(f"SET search_path TO {schema_name}"))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Schema de tenant inválido ou inexistente.")

    user = db.query(UserTenant).filter(UserTenant.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário inativo.")

    # >>>>>>> ADICIONE ESTE BLOCO AQUI <<<<<<<
    try:
        result = db.execute(text("SELECT nome_empresa, url_logo FROM company_info LIMIT 1")).first()
        empresa = result[0] if result and result[0] else "Empresa"
        logoUrl = result[1] if result and result[1] else "/static/logos/logo_almo.png"
    except Exception as err:
        empresa = "Empresa"
        logoUrl = "/static/logos/logo_almo.png"

    access_token = create_access_token(
        data={
            "sub": user.email,
            "schema": schema_name,
            "user_id": user.id,
            "empresa": empresa,
            "logoUrl": logoUrl
        }
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "schema_name": schema_name,
        "user_id": user.id,
        "role": user.role.value,
        "is_admin": user.is_admin,
        "empresa": empresa,
        "logoUrl": logoUrl
    }