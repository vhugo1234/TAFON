from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
import pydantic

# Pydantic v1/v2 compatibility
PYDANTIC_V2 = int(pydantic.__version__.split('.')[0]) >= 2

class ExerciseBase(BaseModel):
    """Base para exercícios do TAF"""
    name: str = Field(..., min_length=3, max_length=255, description="Nome do exercício (ex: Corrida 12min, Barra Fixa)")
    unit_of_measure: str = Field(..., max_length=50, description="Unidade de medida (tempo, repetições, metros)")
    max_attempts: int = Field(default=1, ge=1, le=5, description="Número máximo de tentativas permitidas")
    execution_mode: str = Field(default='individual', pattern="^(individual|collective)$", description="Modo de execucao: individual ou collective")
    measurement_type: str = Field(default='repetitions', pattern="^(time|distance|repetitions)$", description="Tipo de medicao: time, distance ou repetitions")
    
    model_config = ConfigDict(from_attributes=True)

class ExerciseCreate(ExerciseBase):
    """Schema para criação de exercício vinculado a um evento"""
    event_id: int = Field(..., description="ID do evento ao qual o exercício pertence")

class ExerciseUpdate(BaseModel):
    """Schema para atualização de exercício - campos opcionais"""
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    max_attempts: Optional[int] = Field(None, ge=1, le=5)
    execution_mode: Optional[str] = Field(None, pattern="^(individual|collective)$")
    measurement_type: Optional[str] = Field(None, pattern="^(time|distance|repetitions)$")
    
    model_config = ConfigDict(from_attributes=True)

class ExerciseOut(ExerciseBase):
    """Schema de resposta de exercício"""
    id: int
    exercise_id: int # Para contexto, embora não seja essencial na criação

    if PYDANTIC_V2:
        model_config = {'from_attributes': True}
    else:
        class Config:
            from_attributes = True

# ======================================
# SCHEMAS DE CRITÉRIOS DE APROVAÇÃO
# ======================================

class PassCriteriaBase(BaseModel):
    """Base para critérios de aprovação por exercício"""
    gender: str = Field(..., pattern="^[MF]$", description="Sexo (M ou F)")
    min_value: float = Field(..., description="Valor mínimo para aprovação")
    max_time_s: Optional[int] = Field(None, description="Tempo máximo em segundos (para exercícios de tempo)")
    
    model_config = ConfigDict(from_attributes=True)

class PassCriteriaCreate(PassCriteriaBase):
    """Schema para criação de critério de aprovação"""
    # Tornado opcional porque o endpoint fornece exercise_id via path
    exercise_id: Optional[int] = Field(None, description="ID do exercício")

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
    exercise_id: int
    
    model_config = ConfigDict(from_attributes=True)

# ======================================
# SCHEMAS COMPOSTOS
# ======================================

class ExerciseWithCriteria(ExerciseOut):
    """Exercício com seus critérios de aprovação"""
    criteria: List[PassCriteriaOut] = Field(default_factory=list)

class ExerciseList(BaseModel):
    """Lista paginada de exercícios"""
    items: List[ExerciseOut]
    total: int
    page: int
    page_size: int
    
    if PYDANTIC_V2:
        model_config = {'from_attributes': True}
    else:
        class Config:
            from_attributes = True
