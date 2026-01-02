import os
import uuid
import logging
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.connection import get_db
from app.db.models.public import Tenant
from app.api.deps import get_current_user  # reusa a dependência já usada em outros routers

logger = logging.getLogger("app.routers.company")
router = APIRouter(prefix="/company", tags=["Company"])

# Diretorio público já montado no main.py: app.mount("/static/logos", StaticFiles(...))
UPLOAD_DIRECTORY = "static/logos"
PUBLIC_PREFIX = "/static/logos"

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)


def get_schema_name(current_user):
    # compatível tanto com dict quanto com objeto
    if isinstance(current_user, dict):
        return current_user.get("schema_name")
    return getattr(current_user, "schema_name", None)


@router.get("/", response_model=dict)
def get_company(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Retorna os dados da empresa (tenant) associados ao tenant corrente (via current_user.schema_name).
    Busca o registro na tabela central `tenants` que fica no schema `public` — por isso
    ajustamos temporarily o search_path para `public` antes da query.
    """
    schema_name = get_schema_name(current_user)
    if not schema_name:
        raise HTTPException(status_code=400, detail="Tenant não identificado")

    try:
        # Garantir que consultamos a tabela central no schema `public`
        db.execute(text("SET search_path TO public"))
        tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Dados da empresa não encontrados para este tenant")
        return {
            "company_name": getattr(tenant, "nome_empresa", "") or "",
            "company_cnpj": "",  # campo não presente no modelo Tenant central
            "company_address": "",  # campo não presente no modelo Tenant central
            "company_phone": getattr(tenant, "responsible_phone", "") or "",
            "company_email": getattr(tenant, "responsible_email", "") or "",
            "company_website": getattr(tenant, "dominio_url", "") or "",
            "company_logo_path": getattr(tenant, "logo_url", "") or "",
        }
    finally:
        # restaura search_path para o schema do tenant atual (se existir)
        try:
            if schema_name:
                db.execute(text(f"SET search_path TO {schema_name}"))
        except Exception:
            # se não der para restaurar, apenas ignore para não quebrar a API
            pass


@router.put("/", response_model=dict)
async def update_company(
    company_name: Optional[str] = Form(None),
    company_cnpj: Optional[str] = Form(None),
    company_address: Optional[str] = Form(None),
    company_phone: Optional[str] = Form(None),
    company_email: Optional[str] = Form(None),
    company_website: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Atualiza os campos disponíveis no Tenant central para o tenant corrente.
    Aceita multipart/form-data com um campo opcional 'logo' (imagem). Salva o logo em static/logos e grava o caminho em logo_url.
    """
    schema_name = get_schema_name(current_user)
    if not schema_name:
        raise HTTPException(status_code=400, detail="Tenant não identificado")

    try:
        # Garantir que atualizamos o registro central no schema `public`
        db.execute(text("SET search_path TO public"))
        tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant não encontrado")

        changed = False

        if company_name is not None:
            tenant.nome_empresa = company_name
            changed = True
        if company_phone is not None:
            tenant.responsible_phone = company_phone
            changed = True
        if company_email is not None:
            tenant.responsible_email = company_email
            changed = True
        if company_website is not None:
            tenant.dominio_url = company_website
            changed = True

        # tratar logo (se enviado)
        if logo and getattr(logo, "filename", None):
            if not logo.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Arquivo enviado não é uma imagem")
            ext = os.path.splitext(logo.filename)[1] or ""
            unique_name = f"{schema_name}_{uuid.uuid4().hex}{ext}"
            dest_path = os.path.join(UPLOAD_DIRECTORY, unique_name)
            # grava arquivo
            with open(dest_path, "wb") as f:
                content = await logo.read()
                f.write(content)
            # publica caminho que o frontend espera (main.py já montou /static/logos)
            tenant.logo_url = f"{PUBLIC_PREFIX}/{unique_name}"
            changed = True

        if changed:
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        return {
            "company_name": getattr(tenant, "nome_empresa", "") or "",
            "company_cnpj": "",  # sem campo central
            "company_address": "",
            "company_phone": getattr(tenant, "responsible_phone", "") or "",
            "company_email": getattr(tenant, "responsible_email", "") or "",
            "company_website": getattr(tenant, "dominio_url", "") or "",
            "company_logo_path": getattr(tenant, "logo_url", "") or "",
        }

    except HTTPException:
        # re-raise para o cliente com o mesmo status/detail
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Erro ao atualizar dados da empresa: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar dados da empresa: {e}")
    finally:
        # restaura search_path para o schema do tenant atual (se existir)
        try:
            if schema_name:
                db.execute(text(f"SET search_path TO {schema_name}"))
        except Exception:
            pass