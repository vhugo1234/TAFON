from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class TenantBase(BaseModel):
    nome_empresa: Optional[str] = None
    schema_name: str = Field(..., regex=r"^[a-z0-9_]+$")
    status: Optional[str] = "active"
    plan_type: Optional[str] = None
    responsible_name: Optional[str] = None
    responsible_email: Optional[EmailStr] = None
    responsible_phone: Optional[str] = None
    dominio_url: Optional[str] = None
    logo_url: Optional[str] = None


class TenantCreate(TenantBase):
    admin_name: Optional[str] = None
    admin_email: Optional[EmailStr] = None
    admin_password: Optional[str] = None


class TenantUpdate(BaseModel):
    nome_empresa: Optional[str] = None
    status: Optional[str] = None
    plan_type: Optional[str] = None
    responsible_name: Optional[str] = None
    responsible_email: Optional[EmailStr] = None
    responsible_phone: Optional[str] = None
    dominio_url: Optional[str] = None
    logo_url: Optional[str] = None


class TenantOut(TenantBase):
    id: Optional[int] = None
    users_total: int = 0
    assets_total: int = 0
    created_at: Optional[str] = None
    last_access: Optional[str] = None


class CreateTenantResponse(BaseModel):
    tenant: TenantOut
    admin_temp_password: Optional[str] = None