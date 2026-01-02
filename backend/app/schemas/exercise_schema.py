from typing import Optional, List
from pydantic import BaseModel
import pydantic

# Detecta Pydantic v2
_PYDANTIC_V2 = int(pydantic.__version__.split(".")[0]) >= 2

# -------------------------
# PassCriteria schemas
# -------------------------
class PassCriteriaBase(BaseModel):
    descricao: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unidade: Optional[str] = None

class PassCriteriaCreate(PassCriteriaBase):
    pass

if _PYDANTIC_V2:
    class PassCriteriaOut(PassCriteriaBase):
        id: int
        model_config = {"from_attributes": True}
else:
    class PassCriteriaOut(PassCriteriaBase):
        id: int
        class Config:
            orm_mode = True

# -------------------------
# Exercise schemas
# -------------------------
class ExerciseBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    unidade: Optional[str] = None  # ex: "segundos", "repetições", "metros"
    pontuacao_maxima: Optional[float] = None
    # se houver critérios embutidos
    criterios: Optional[List[PassCriteriaOut]] = None

class ExerciseCreate(ExerciseBase):
    pass

class ExerciseUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    unidade: Optional[str] = None
    pontuacao_maxima: Optional[float] = None
    criterios: Optional[List[PassCriteriaOut]] = None

if _PYDANTIC_V2:
    class ExerciseOut(ExerciseBase):
        id: int
        model_config = {"from_attributes": True}
else:
    class ExerciseOut(ExerciseBase):
        id: int
        class Config:
            orm_mode = True