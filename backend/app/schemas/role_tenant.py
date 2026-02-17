from typing import Optional
from pydantic import BaseModel, Field
import pydantic

# Pydantic v1/v2 compatibility
PYDANTIC_V2 = int(pydantic.__version__.split('.')[0]) >= 2

# Importa validators compatíveis com v1/v2
if _PYDANTIC_V2:
    from pydantic import field_validator as _field_validator  # type: ignore
else:
    from pydantic import validator as _validator  # type: ignore


class RoleTenantBase(BaseModel):
    """
    Schema base para RoleTenant.
    - nome: nome do papel (obrigatório, máximo 100 caracteres)
    - descricao: descrição opcional
    """
    nome: str = Field(..., min_length=1, max_length=100, description="Nome do papel")
    descricao: Optional[str] = Field(None, max_length=255, description="Descrição opcional do papel")


class RoleTenantCreate(RoleTenantBase):
    pass


class RoleTenantUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=1, max_length=100)
    descricao: Optional[str] = Field(None, max_length=255)


# Validação/normalização (strip) compatível com Pydantic v1 e v2
if _PYDANTIC_V2:
    class RoleTenantBase(RoleTenantBase):  # re-abre para anexar validator em v2
        @classmethod
        @_field_validator("nome", mode="before")
        def _strip_nome(cls, v):
            if isinstance(v, str):
                return v.strip()
            return v

        @classmethod
        @_field_validator("descricao", mode="before")
        def _strip_descricao(cls, v):
            if isinstance(v, str):
                return v.strip()
            return v
else:
    class RoleTenantBase(RoleTenantBase):  # re-abre para anexar validator em v1
        @_validator("nome", pre=True, always=True)
        def _strip_nome(cls, v):
            if isinstance(v, str):
                return v.strip()
            return v

        @_validator("descricao", pre=True, always=True)
        def _strip_descricao(cls, v):
            if isinstance(v, str):
                return v.strip()
            return v


# Saída (compatível com pydantic v1 e v2)
if _PYDANTIC_V2:
    class RoleTenantOut(RoleTenantBase):
        id: int
        model_config = {"from_attributes": True, "json_schema_extra": {"example": {"id": 1, "nome": "Administrador Geral", "descricao": "Papel global"}}}
else:
    class RoleTenantOut(RoleTenantBase):
        id: int

        class Config:
            orm_mode = True
            schema_extra = {"example": {"id": 1, "nome": "Administrador Geral", "descricao": "Papel global"}}