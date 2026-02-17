# backend/app/api/v1/endpoints/__init__.py
"""
TEMPORARY SHIM: Defensive imports to prevent ModuleNotFoundError.
Creates placeholder routers for missing modules.
"""
import sys
import traceback
from fastapi import APIRouter

# List of expected endpoint modules
EXPECTED_MODULES = [
    "auth", "items", "asset", "acessorios", "emprestimos",
    "admin_tenants", "admin_upload", "tenant_auth", "users",
    "upload_api", "password_reset", "events_taf", "exercises_taf",
    "candidates", "execution", "results", "role_tenant", "company",
    "tenant_public_register"
]

def _create_placeholder_module(module_name: str):
    """Create a placeholder module with an empty router."""
    import types
    module = types.ModuleType(module_name)
    module.router = APIRouter()
    return module

# Try to import each module, create placeholder if it fails
for module_name in EXPECTED_MODULES:
    try:
        exec(f"from . import {module_name}")
    except ImportError as e:
        print(f"[WARNING] Could not import endpoint '{module_name}': {e}")
        print(f"[WARNING] Creating placeholder module for '{module_name}'")
        # Don't mask the error completely - log it
        traceback.print_exc()
        # Create placeholder in sys.modules so future imports work
        full_module_name = f"app.api.v1.endpoints.{module_name}"
        if full_module_name not in sys.modules:
            sys.modules[full_module_name] = _create_placeholder_module(full_module_name)
