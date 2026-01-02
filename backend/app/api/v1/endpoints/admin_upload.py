# app/routers/admin_upload.py

import os
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.connection import get_db
from app.db.models.public import Tenant
from app.core.security import get_current_active_superuser
from app.core.config import settings  # se quiser tornar BASE URL configurável

logger = logging.getLogger("app.routers.admin.upload")
router = APIRouter(
    prefix="/upload",
    dependencies=[Depends(get_current_active_superuser)],
)

# Configuração de Armazenamento (Ajuste para seu ambiente: S3, Azure, Local)
UPLOAD_DIRECTORY = "static/logos"
# URL base para acesso público aos arquivos (use BACKEND_URL + BASE_URL_FOR_LOGOS no frontend)
BASE_URL_FOR_LOGOS = "/static/logos"

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# Segurança para uploads
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2 MB


@router.post("/logo", status_code=status.HTTP_201_CREATED)
async def upload_logo(
    logo: UploadFile = File(...),
    tenant_id: Optional[str] = Form(None),  # Recebe o ID ou 'new' do frontend
    db: Session = Depends(get_db)
):
    """
    Recebe um arquivo de logo, salva-o e retorna o URL público.
    Atualiza o campo logo_url do Tenant se o tenant_id for fornecido.
    """
    # 1) valida content-type básico
    if not logo.content_type or not logo.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O arquivo enviado não é uma imagem.")

    # 2) ler conteúdo (para checar tamanho) — se quiser evitar memória alta, implemente streaming chunked
    content = await logo.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo muito grande. Tamanho máximo permitido: 2MB.")

    # 3) extrair e validar extensão
    filename = (logo.filename or "").rsplit(".", 1)
    if len(filename) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo sem extensão válida.")
    file_extension = filename[-1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extensão de arquivo não permitida.")

    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIRECTORY, unique_filename)
    public_url = f"{BASE_URL_FOR_LOGOS}/{unique_filename}"

    try:
        # 4) salvar arquivo de forma segura
        with open(file_path, "wb") as f:
            f.write(content)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                # fsync pode falhar em alguns ambientes; não quebra o fluxo, apenas loga
                logger.debug("fsync falhou (ambiente pode não suportar): continuing")

        # 5) atualizar tenant se aplicável
        if tenant_id and tenant_id != "new":
            try:
                tenant_id_int = int(tenant_id)
            except ValueError:
                logger.error(f"Tenant ID inválido: {tenant_id}")
                tenant_id_int = None

            if tenant_id_int is not None:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id_int).first()
                if tenant:
                    tenant.logo_url = public_url
                    db.commit()
                    logger.info(f"Logo atualizada para o tenant ID {tenant_id_int}.")
                else:
                    logger.warning(f"Tenant ID {tenant_id_int} não encontrado para atualização de logo.")

        # 6) retornar URL público relativo (frontend deve concatenar BACKEND_URL se necessário)
        return {"message": "Upload de logo realizado com sucesso", "logo_url": public_url}

    except Exception as e:
        logger.exception("Erro no processo de upload de logo.")
        # remover arquivo parcialmente gravado, se existir
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            logger.debug("Falha ao remover arquivo parcial após erro.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha no upload: {e}")