# backend/api_router.py
from fastapi import APIRouter

# Importe somente os módulos reais do seu repositório (ajuste nomes se necessário)
from app.api.v1.endpoints import (
    auth,
    admin_tenants,
    admin_upload,
    company,
    tenant_auth,
    tenant_public_register,
    users,
    role_tenant,
    events_taf,
    exercises_taf,
    candidates,
    execution,
    results,
    evaluators,
    field_execution,
    password_reset,
    upload_api,
)



api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(admin_tenants.router, prefix="/admin", tags=["Admin - Tenants"])
api_router.include_router(admin_upload.router, prefix="/admin/upload", tags=["Admin - Uploads"])
api_router.include_router(company.router, prefix="/company", tags=["Empresa"])
api_router.include_router(tenant_auth.router, prefix="/tenants", tags=["Tenant Auth"])
api_router.include_router(upload_api.router, prefix="/upload", tags=["Upload de Imagens"])
api_router.include_router(tenant_public_register_router)
api_router.include_router(password_reset.router, prefix="/password-reset", tags=["Password Reset"])

# TEMPORARY SHIM: Include placeholder routers for legacy endpoints
# These can be removed once the actual implementations are ready
api_router.include_router(items.router, prefix="/items", tags=["Items (Legacy)"])
api_router.include_router(asset.router, prefix="/asset", tags=["Asset (Legacy)"])
api_router.include_router(acessorios.router, prefix="/acessorios", tags=["Acessorios (Legacy)"])
api_router.include_router(emprestimos.router, prefix="/emprestimos", tags=["Emprestimos (Legacy)"])
