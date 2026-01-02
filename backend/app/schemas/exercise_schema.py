# backend/app/schemas/exercise_schema.py

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
import pydantic

# Pydantic v1/v2 compatibility
PYDANTIC_V2 = int(pydantic.__version__.split('.')[0]) >= 2

# ----------------------------------------------------
# PassCriteria (Critérios Mínimos de Aprovação)
# ----------------------------------------------------

class PassCriteriaBase(BaseModel):
    gender: Literal['M', 'F'] = Field(..., description="Gênero: 'M' ou 'F'")
    min_value: float = Field(..., description="Valor mínimo exigido (repetições, metros, etc.)")
    max_time_s: Optional[int] = Field(None, description="Tempo máximo permitido em segundos (para corridas)")

class PassCriteriaCreate(PassCriteriaBase):
    pass

class PassCriteriaOut(PassCriteriaBase):
    id: int
    exercise_id: int # Para contexto, embora não seja essencial na criação

    if PYDANTIC_V2:
        model_config = {'from_attributes': True}
    else:
        class Config:
            from_attributes = True

# ----------------------------------------------------
# Exercise (A Prova em si)
# ----------------------------------------------------

class ExerciseBase(BaseModel):
    event_id: int = Field(..., description="ID do Evento TAF ao qual o exercício pertence")
    name: str = Field(..., max_length=128, description="Nome do exercício (Ex: Corrida 2400m)")
    unit_of_measure: str = Field(..., max_length=50, description="Unidade (Ex: Repetições, Tempo (s), Metros)")
    max_attempts: int = Field(default=1, description="Número máximo de tentativas")
    
    # Lista aninhada para regras (o core deste módulo)
    criteria: List[PassCriteriaCreate] = Field(..., description="Lista de critérios de aprovação por gênero")

class ExerciseCreate(ExerciseBase):
    pass

class ExerciseUpdate(BaseModel):
    """
    Schema for updating an exercise.
    All fields are optional.
    """
    event_id: Optional[int] = Field(None, description="ID do Evento TAF")
    name: Optional[str] = Field(None, max_length=128, description="Nome do exercício")
    unit_of_measure: Optional[str] = Field(None, max_length=50, description="Unidade")
    max_attempts: Optional[int] = Field(None, description="Número máximo de tentativas")
    criteria: Optional[List[PassCriteriaCreate]] = Field(None, description="Lista de critérios de aprovação")

class ExerciseOut(ExerciseBase):
    id: int
    criteria: List[PassCriteriaOut] # Retorna a lista com IDs
    created_at: Optional[datetime] = None
    
    if PYDANTIC_V2:
        model_config = {'from_attributes': True}
    else:
        class Config:
            from_attributes = True