# backend/api_router.py
from fastapi import APIRouter
from app.api.v1.endpoints import auth, items, asset, acessorios, emprestimos
from app.api.v1.endpoints import admin_tenants, admin_upload
from app.api.v1.endpoints import tenant_auth
from app.api.v1.endpoints import users
from app.api.v1.endpoints import upload_api
from app.api.v1.endpoints.tenant_public_register import router as tenant_public_register_router
from app.api.v1.endpoints import password_reset
from app.api.v1.endpoints import events_taf    # Módulo 1: Criação de Evento
from app.api.v1.endpoints import exercises_taf # Módulo 2: Criação de Regras/Exercícios
from app.api.v1.endpoints import candidates    # Módulo 3: Candidatos/Agrupamento
from app.api.v1.endpoints import execution     # Módulo 4: Lançamento de Dados
from app.api.v1.endpoints import results       # Módulo 5: Resultados e Relatórios

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(admin_tenants.router, prefix="/admin", tags=["Admin - Gerenciamento de Clientes (Tenants)"])
api_router.include_router(admin_upload.router, prefix="/admin", tags=["Admin - Uploads"])
api_router.include_router(users.router, prefix="/users", tags=["Usuários"])
api_router.include_router(events_taf.router, prefix="/taf/events", tags=["TAF - Módulo 1: Eventos"])
api_router.include_router(exercises_taf.router, prefix="/taf/exercises", tags=["TAF - Módulo 2: Exercícios e Regras"])
api_router.include_router(candidates.router, prefix="/taf/candidates", tags=["TAF - Módulo 3: Candidatos e Turmas"])
api_router.include_router(execution.router, prefix="/taf/execution", tags=["TAF - Módulo 4: Execução"])
api_router.include_router(results.router, prefix="/taf/results", tags=["TAF - Módulo 5: Resultados"])
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
