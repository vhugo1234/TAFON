from typing import Optional
from pydantic import BaseModel
import pydantic

# Detecta se estamos usando Pydantic v2
_PYDANTIC_V2 = int(pydantic.__version__.split(".")[0]) >= 2

class RoleTenantBase(BaseModel):
    nome: str
    descricao: Optional[str] = None

class RoleTenantCreate(RoleTenantBase):
    pass

class RoleTenantUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None

# Saída (compatível com pydantic v1 e v2)
if _PYDANTIC_V2:
    # Pydantic v2: usar model_config
    class RoleTenantOut(RoleTenantBase):
        id: int
        model_config = {"from_attributes": True}
else:
    # Pydantic v1: usar Config.orm_mode
    class RoleTenantOut(RoleTenantBase):
        id: int
        class Config:
            orm_mode = True