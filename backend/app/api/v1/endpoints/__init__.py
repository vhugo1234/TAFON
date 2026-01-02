# backend/app/api/v1/endpoints/__init__.py
import importlib
import types
import traceback
from fastapi import APIRouter

_expected = [
    "auth",
    "admin_tenants",
    "admin_upload",
    "company",
    "tenant_auth",
    "tenant_public_register",
    "users",
    "role_tenant",
    "events_taf",
    "exercises_taf",
    "candidates",
    "execution",
    "results",
    "upload_api",
    "password_reset",
    "password_reset",  # duplicado é tolerado
    "upload_api",      # duplicado tolerado
    "password_reset",
    "password_reset",
    "password_reset",
]

__all__ = []

for mod in {m for m in _expected if m}:  # remove duplicatas e vazios
    fullname = f"app.api.v1.endpoints.{mod}"
    try:
        m = importlib.import_module(fullname)
    except Exception:
        # cria módulo placeholder com um router vazio para manter compatibilidade de import
        m = types.ModuleType(mod)
        m.router = APIRouter()
        # opcional: registrar um endpoint que retorna aviso (não exposto se router não for incluído)
        # m.router.get("/_placeholder")(lambda: {"warning": f"Placeholder router for {mod}"})
        print(f"[WARN] Placeholder module created for missing endpoint: {fullname}")
        traceback.print_exc()
    globals()[mod] = m
    __all__.append(mod)