from pydantic import BaseModel, EmailStr
from typing import Optional
import pydantic
from datetime import datetime

# Detecta se estamos usando Pydantic v2
_PYDANTIC_V2 = int(pydantic.__version__.split(".")[0]) >= 2

class UserTenantBase(BaseModel):
    nome: str
    username: Optional[str]
    email: EmailStr
    is_active: bool = True
    role_id: Optional[int]
    cpf: Optional[str]
    phone: Optional[str]
    department: Optional[str]
    institution: Optional[str]
    birth_date: Optional[str]
    notes: Optional[str]
    address: Optional[str]
    avatar_url: Optional[str]
    specialty: Optional[str]
    accepted_terms: Optional[bool] = False
    is_admin: Optional[bool] = False
    cref: Optional[str] = None
    # banking fields
    bank_name: Optional[str] = None
    pix: Optional[str] = None
    bank_account: Optional[str] = None
    agency: Optional[str] = None

class UserTenantCreate(UserTenantBase):
    password: str

class UserTenantUpdate(BaseModel):
    nome: Optional[str]
    username: Optional[str]
    email: Optional[EmailStr]
    password: Optional[str]
    is_active: Optional[bool]
    role_id: Optional[int]
    cpf: Optional[str]
    phone: Optional[str]
    department: Optional[str]
    institution: Optional[str]
    birth_date: Optional[str]
    notes: Optional[str]
    address: Optional[str]
    avatar_url: Optional[str]
    specialty: Optional[str]
    accepted_terms: Optional[bool]
    is_admin: Optional[bool]
    cref: Optional[str]
    bank_name: Optional[str]
    pix: Optional[str]
    bank_account: Optional[str]
    agency: Optional[str]

# Saída compatível com pydantic v1 e v2
if _PYDANTIC_V2:
    class UserTenantOut(UserTenantBase):
        id: int
        username: Optional[str]
        cpf: Optional[str]
        phone: Optional[str]
        department: Optional[str]
        institution: Optional[str]
        birth_date: Optional[str]
        notes: Optional[str]
        address: Optional[str]
        avatar_url: Optional[str]
        specialty: Optional[str]
        accepted_terms: Optional[bool]
        is_admin: Optional[bool]
        bank_name: Optional[str]
        pix: Optional[str]
        bank_account: Optional[str]
        agency: Optional[str]

        # signature metadata (exposição somente em saída)
        signature_path: Optional[str] = None
        signature_hash: Optional[str] = None
        signature_uploaded_at: Optional[datetime] = None
        signature_verified: Optional[bool] = None

        model_config = {"from_attributes": True}
else:
    class UserTenantOut(UserTenantBase):
        id: int
        username: Optional[str]
        cpf: Optional[str]
        phone: Optional[str]
        department: Optional[str]
        institution: Optional[str]
        birth_date: Optional[str]
        notes: Optional[str]
        address: Optional[str]
        avatar_url: Optional[str]
        specialty: Optional[str]
        accepted_terms: Optional[bool]
        is_admin: Optional[bool]
        bank_name: Optional[str]
        pix: Optional[str]
        bank_account: Optional[str]
        agency: Optional[str]

        # signature metadata (exposição somente em saída)
        signature_path: Optional[str] = None
        signature_hash: Optional[str] = None
        signature_uploaded_at: Optional[datetime] = None
        signature_verified: Optional[bool] = None

        class Config:
            orm_mode = True
