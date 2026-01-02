from pydantic import BaseModel
from typing import Optional
import pydantic

# Pydantic v1/v2 compatibility
PYDANTIC_V2 = int(pydantic.__version__.split('.')[0]) >= 2

class RoleTenantBase(BaseModel):
    nome: str
    descricao: Optional[str] = None

class RoleTenantCreate(RoleTenantBase):
    pass

class RoleTenantUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None

class RoleTenantOut(RoleTenantBase):
    id: int
    
    # Pydantic v1/v2 compatibility
    if PYDANTIC_V2:
        model_config = {'from_attributes': True}
    else:
        class Config:
            orm_mode = True