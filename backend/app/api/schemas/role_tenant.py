# backend/app/api/schemas/role_tenant.py
"""
TEMPORARY SHIM: Re-export role_tenant schemas from app.schemas.role_tenant.
"""
try:
    from app.schemas.role_tenant import (
        RoleTenantBase,
        RoleTenantCreate,
        RoleTenantUpdate,
        RoleTenantOut
    )
    __all__ = ["RoleTenantBase", "RoleTenantCreate", "RoleTenantUpdate", "RoleTenantOut"]
except ImportError as e:
    raise ImportError(
        f"Could not import role_tenant schemas from app.schemas.role_tenant: {e}\n"
        "Make sure app/schemas/role_tenant.py exists and is properly configured."
    )
