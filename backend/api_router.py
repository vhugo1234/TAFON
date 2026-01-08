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
api_router.include_router(tenant_public_register.router, prefix="/public-register", tags=["Registro Público"])
api_router.include_router(users.router, prefix="/users", tags=["Usuários"])
api_router.include_router(role_tenant.router, prefix="/roles", tags=["Roles"])
api_router.include_router(events_taf.router, prefix="/taf/events", tags=["TAF - Eventos"])
api_router.include_router(exercises_taf.router, prefix="/taf/exercises", tags=["TAF - Exercícios"])
api_router.include_router(candidates.router, prefix="/taf/candidates", tags=["TAF - Candidatos"])
api_router.include_router(evaluators.router, prefix="/taf/evaluators", tags=["TAF - Avaliadores"])
api_router.include_router(execution.router, prefix="/taf/execution", tags=["TAF - Execução"])
api_router.include_router(field_execution.router, prefix="/taf/field", tags=["TAF - Execução em Campo"])
api_router.include_router(results.router, prefix="/taf/results", tags=["TAF - Resultados"])
api_router.include_router(upload_api.router, prefix="/upload-image", tags=["Upload"])
api_router.include_router(password_reset.router, prefix="/password-reset", tags=["Password Reset"])
