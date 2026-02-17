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
    # novos endpoints
    event_workers,
    attendance,
    coordinator_signature,
    financials,  # <-- adicionado (assegure que app/api/v1/endpoints/financials.py exista)
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(admin_tenants.router, prefix="/admin", tags=["Admin - Tenants"])
api_router.include_router(admin_upload.router, prefix="/admin/upload", tags=["Admin - Uploads"])
api_router.include_router(company.router, prefix="/company", tags=["Empresa"])
api_router.include_router(tenant_auth.router, prefix="/tenants", tags=["Tenant Auth"])
api_router.include_router(tenant_public_register.router)
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

# Rotas dos novos módulos:
# - event_workers.router define rotas prefixed com /event (por isso incluímos sem prefix aqui)
# - attendance.router adiciona endpoints de checkin/checkout (/event/... conforme implementado)
# - coordinator_signature.router adiciona endpoint para upload de assinatura (/coordinator/{id}/signature)
api_router.include_router(event_workers.router)         # ex.: /{event_id}/workers (definido no router)
api_router.include_router(attendance.router)            # ex.: /event/{event_id}/worker/{worker_id}/attendance/...
api_router.include_router(coordinator_signature.router) # ex.: /coordinator/{coord_id}/signature

# financials router
# Se você manteve o caminho interno no router como "/financials/export" (full path),
# incluir sem prefix preserva esse caminho (resultado: /api/v1/financials/export).
# Se no arquivo financials.py você definiu as rotas com paths relativos (ex.: router.post("/export")),
# prefira incluir com prefix="/financials" em vez de incluí-lo sem prefix.
api_router.include_router(financials.router)  # -> expõe /financials/export conforme router definido
