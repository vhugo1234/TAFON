# backend/app/schemas/execution_schema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

# =============================================================================
# SCHEMAS DE EXECUÇÃO/LANÇAMENTO
# =============================================================================

class ExecutionResultBase(BaseModel):
    """Base para resultado de execução"""
    measured_value: float = Field(..., description="Valor medido (metros, repetições, segundos)")
    attempt_number: int = Field(..., ge=1, le=5, description="Número da tentativa")
    is_valid: bool = Field(default=True, description="Se a tentativa é válida")
    
    model_config = ConfigDict(from_attributes=True)


class ExecutionResultCreate(ExecutionResultBase):
    """Schema para criação de resultado"""
    candidate_id: int = Field(..., description="ID do candidato")
    exercise_id: int = Field(..., description="ID do exercício")


class ExecutionResultUpdate(BaseModel):
    """Schema para atualização de resultado"""
    measured_value: Optional[float] = None
    is_valid: Optional[bool] = None
    is_approved_in_exercise: Optional[bool] = None
    
    model_config = ConfigDict(from_attributes=True)


class ExecutionResultOut(ExecutionResultBase):
    """Schema de resposta de resultado"""
    id: int
    candidate_id: int
    exercise_id: int
    evaluator_user_id: Optional[int] = None
    is_approved_in_exercise: Optional[bool] = None
    
    # Campos relacionados (opcionais)
    candidate_name: Optional[str] = None
    exercise_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SCHEMAS DE LANÇAMENTO EM LOTE
# =============================================================================

class BulkExecutionCreate(BaseModel):
    """Schema para lançamento de múltiplos resultados"""
    results: list[ExecutionResultCreate]


class BulkExecutionResult(BaseModel):
    """Resultado do lançamento em lote"""
    total: int
    success: int
    failed: int
    errors: list[str]


# =============================================================================
# SCHEMAS DE DASHBOARD/RELATÓRIO
# =============================================================================

class CandidateProgress(BaseModel):
    """Progresso de um candidato"""
    candidate_id: int
    candidate_name: str
    registration_number: str
    gender: str
    total_exercises: int
    completed_exercises: int
    approved_exercises: int
    failed_exercises: int
    pending_exercises: int
    overall_status: str  # "approved", "failed", "in_progress"


class ExerciseStats(BaseModel):
    """Estatísticas de um exercício"""
    exercise_id: int
    exercise_name: str
    total_candidates: int
    completed: int
    approved: int
    failed: int
    pending: int
    approval_rate: float


class EventExecutionSummary(BaseModel):
    """Resumo da execução de um evento"""
    event_id: int
    event_name: str
    total_candidates: int
    total_exercises: int
    
    # Estatísticas gerais
    total_results_recorded: int
    candidates_completed: int
    candidates_approved: int
    candidates_failed: int
    candidates_in_progress: int
    
    # Taxa de conclusão
    completion_rate: float
    approval_rate: float
    
    # Por exercício
    exercises_stats: list[ExerciseStats]