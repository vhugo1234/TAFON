from fastapi import APIRouter, Depends, HTTPException, status, Path
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from app.db.connection import get_db, engine
from app.core.security import verify_password, create_access_token
import re
import traceback

router = APIRouter(
    prefix="/tenants/{schema_name}/auth",
    tags=["Tenant Auth"]
)

# Validação simples do nome de schema
_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@router.post("/login")
def login_tenant_user(
    schema_name: str = Path(..., min_length=1),
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db)
):
    if not _SCHEMA_RE.match(schema_name):
        raise HTTPException(status_code=400, detail="Nome de schema inválido.")

    try:
        # consulta direta qualificada por schema para achar o usuário no tenant
        with engine.connect() as conn:
            q = text(
                f'SELECT id, nome, email, hashed_password, is_active, is_admin, role, role_id '
                f'FROM "{schema_name}".user_tenant WHERE email = :email LIMIT 1'
            )
            row = conn.execute(q, {"email": form_data.username}).fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")
            user_id, nome, email_val, hashed_pw, is_active, is_admin, role_val, role_id = row

            if not hashed_pw or not verify_password(form_data.password, hashed_pw):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")
            if is_active is False:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário inativo.")

            # tentar ler company info no schema do tenant, se existir
            try:
                info = conn.execute(text("SELECT nome_empresa, logo_url FROM company_info LIMIT 1")).fetchone()
                empresa = info[0] if info and info[0] else "Empresa"
                logoUrl = info[1] if info and info[1] else "/static/logos/logo_almo.png"
            except Exception:
                traceback.print_exc()
                empresa = "Empresa"
                logoUrl = "/static/logos/logo_almo.png"

            access_token = create_access_token(
                data={
                    "sub": email_val,
                    "schema": schema_name,
                    "user_id": user_id,
                    "empresa": empresa,
                    "logoUrl": logoUrl
                }
            )

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "schema_name": schema_name,
                "user_id": user_id,
                "role": role_val or role_id,
                "is_admin": bool(is_admin),
                "empresa": empresa,
                "logoUrl": logoUrl
            }
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Schema de tenant inválido ou inexistente.")