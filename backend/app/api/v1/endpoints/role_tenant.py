from fastapi import APIRouter, Depends, HTTPException, Path as FastAPIPath
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.crud import role_tenant_crud
from app.schemas.role_tenant import RoleTenantCreate, RoleTenantUpdate, RoleTenantOut
from app.db.connection import get_db # <-- Novo caminho
import logging

router = APIRouter(tags=["roles"])

logger = logging.getLogger(__name__)

# NOTE: rotas tenant-scoped: /tenants/{schema_name}/roles
@router.post("/tenants/{schema_name}/roles/", response_model=RoleTenantOut)
def create_role(
    schema_name: str = FastAPIPath(..., min_length=1),
    role_in: RoleTenantCreate = Depends(),  # FastAPI will parse body
    db: Session = Depends(get_db),
):
    # set search_path to tenant schema so CRUD works within tenant
    try:
        db.execute(text(f"SET search_path TO {schema_name}"))
    except Exception as e:
        logger.exception("Erro ao setar search_path para %s: %s", schema_name, e)
        raise HTTPException(status_code=400, detail="Schema inválido ou inacessível.")
    return role_tenant_crud.create_role(db, role_in)


@router.get("/tenants/{schema_name}/roles/", response_model=list[RoleTenantOut])
def list_roles(
    schema_name: str = FastAPIPath(..., min_length=1),
    db: Session = Depends(get_db),
):
    try:
        db.execute(text(f"SET search_path TO {schema_name}"))
    except Exception as e:
        logger.exception("Erro ao setar search_path para %s: %s", schema_name, e)
        raise HTTPException(status_code=400, detail="Schema inválido ou inacessível.")
    return role_tenant_crud.get_roles(db)


@router.get("/tenants/{schema_name}/roles/{role_id}", response_model=RoleTenantOut)
def get_role(
    schema_name: str = FastAPIPath(..., min_length=1),
    role_id: int = FastAPIPath(...),
    db: Session = Depends(get_db),
):
    try:
        db.execute(text(f"SET search_path TO {schema_name}"))
    except Exception as e:
        logger.exception("Erro ao setar search_path para %s: %s", schema_name, e)
        raise HTTPException(status_code=400, detail="Schema inválido ou inacessível.")
    role = role_tenant_crud.get_role(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.patch("/tenants/{schema_name}/roles/{role_id}", response_model=RoleTenantOut)
def update_role(
    schema_name: str = FastAPIPath(..., min_length=1),
    role_id: int = FastAPIPath(...),
    role_in: RoleTenantUpdate = Depends(),
    db: Session = Depends(get_db),
):
    try:
        db.execute(text(f"SET search_path TO {schema_name}"))
    except Exception as e:
        logger.exception("Erro ao setar search_path para %s: %s", schema_name, e)
        raise HTTPException(status_code=400, detail="Schema inválido ou inacessível.")
    role = role_tenant_crud.get_role(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role_tenant_crud.update_role(db, role, role_in)


@router.delete("/tenants/{schema_name}/roles/{role_id}")
def delete_role(
    schema_name: str = FastAPIPath(..., min_length=1),
    role_id: int = FastAPIPath(...),
    db: Session = Depends(get_db),
):
    try:
        db.execute(text(f"SET search_path TO {schema_name}"))
    except Exception as e:
        logger.exception("Erro ao setar search_path para %s: %s", schema_name, e)
        raise HTTPException(status_code=400, detail="Schema inválido ou inacessível.")
    role_tenant_crud.delete_role(db, role_id)
    return {"ok": True}