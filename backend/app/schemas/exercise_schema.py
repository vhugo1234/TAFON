from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

# ======================================
# SCHEMAS DE EXERCÍCIOS
# ======================================

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
    event_id: int
    execution_mode: str
    measurement_type: str
    
    # Contagem de critérios relacionados
    total_criteria: Optional[int] = Field(default=0, description="Total de critérios de aprovação cadastrados")
    
    model_config = ConfigDict(from_attributes=True)

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

class PassCriteriaUpdate(BaseModel):
    """Schema para atualização de critério - campos opcionais"""
    gender: Optional[str] = Field(None, pattern="^[MF]$")
    min_value: Optional[float] = None
    max_time_s: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class PassCriteriaOut(PassCriteriaBase):
    """Schema de resposta de critério de aprovação"""
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
    
    model_config = ConfigDict(from_attributes=True)