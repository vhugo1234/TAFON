from pydantic import BaseModel
from typing import Optional

class RoleTenantBase(BaseModel):
    nome: str
    descricao: Optional[str] = None

class RoleTenantCreate(RoleTenantBase):
    pass

class RoleTenantUpdate(BaseModel):
    nome: Optional[str]
    descricao: Optional[str]

class RoleTenantOut(RoleTenantBase):
    id: int
    class Config:
        orm_mode = True