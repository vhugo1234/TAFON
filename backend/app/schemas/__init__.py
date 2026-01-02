# Shim package para compatibilidade: app.api.schemas -> delega para app.schemas
# Mantemos o package leve; módulos específicos (ex.: role_tenant.py) reexportam de app.schemas.

__all__ = []