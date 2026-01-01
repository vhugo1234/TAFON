from datetime import date, datetime
from enum import Enum
from typing import Optional, List

# 🚨 IMPORTANTE: ConfigDict é necessário para o Pydantic V2
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


# ----------------------------------------------------------------------
# TIPOS CUSTOMIZADOS (Enum)
# ----------------------------------------------------------------------

class TenantStatus(str, Enum):
    """Representa o status operacional do Tenant."""
    active = "active"
    inactive = "inactive"
    pending = "pending"
    suspended = "suspended"

class TenantType(str, Enum):
    """
    Representa o tipo de plano de assinatura do Tenant.
    CORREÇÃO: Inclui 'starter' para compatibilidade com dados existentes.
    """
    free = "free"
    premium = "premium"
    enterprise = "enterprise"
    starter = "starter" # ⬅️ CORREÇÃO 1: Adicionado para aceitar dados do DB


# ----------------------------------------------------------------------
# 1. BASE SCHEMA (Campos Comuns)
# ----------------------------------------------------------------------

class TenantBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    name: str
    schema_name: str

    responsible_name: Optional[str] = None
    responsible_email: Optional[EmailStr] = None
    responsible_phone: Optional[str] = None

    status: TenantStatus
    plan_type: Optional[TenantType] = None  # ✅ Correção principal
    plan_expires_at: Optional[date] = None

    logo_url: Optional[str] = None
    dominio_url: Optional[str] = None


# ----------------------------------------------------------------------
# 2. CREATE SCHEMA (Dados para criar um novo Tenant)
# ----------------------------------------------------------------------

class TenantCreate(TenantBase):
    # O campo de senha é OPCIONAL. Se não for fornecido, o backend usará a senha padrão.
    admin_password: Optional[str] = None # ⬅️ Mantido Opcional


# ----------------------------------------------------------------------
# 3. UPDATE SCHEMA (Dados para atualizar um Tenant existente)
# ----------------------------------------------------------------------

class TenantUpdate(BaseModel):
    # Herda BaseModel e não TenantBase, pois todos os campos devem ser opcionais
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True) 

    name: Optional[str] = None 
    responsible_name: Optional[str] = None
    responsible_email: Optional[EmailStr] = None
    responsible_phone: Optional[str] = None
    status: Optional[TenantStatus] = None
    plan_type: Optional[TenantType] = None
    plan_expires_at: Optional[date] = None
    dominio_url: Optional[str] = None
    logo_url: Optional[str] = None


# ----------------------------------------------------------------------
# 4. OUT SCHEMA (Resposta da API - Array de Clientes)
# ----------------------------------------------------------------------

class TenantOut(TenantBase):
    id: int
    # ⬅️ CORREÇÃO 3: Tornar 'created_at' Optional, pois o erro indica 'None'
    created_at: Optional[datetime] = None 
    
    # Campos de métricas/simulação para o Admin Dashboard
    users_total: int = 0
    assets_total: int = 0
    last_access: Optional[str] = None 
    
    # A configuração do BaseModel já está na TenantBase e é herdada

# ----------------------------------------------------------------------
# LISTA DE TENANTS
# ----------------------------------------------------------------------

class TenantList(BaseModel):
    """Schema para a lista de tenants (usado na rota GET /tenants)"""
    items: List[TenantOut]
    total_count: int


# FIM: app/schemas/tenant_schema.py