# backend/app/db/models/__init__.py
# Re-exporta os principais modelos para facilitar imports e evitar caminhos quebrados.

# Importar explicitamente os módulos (evitar lógica pesada aqui)
from .public import Base as PublicBase, Tenant, UserCentral
from .tenant import TenantBase, UserTenant, RoleTenant, UserRoleEnum

__all__ = [
    "PublicBase",
    "Tenant",
    "UserCentral",
    "TenantBase",
    "UserTenant",
    "RoleTenant",
    "UserRoleEnum",
]