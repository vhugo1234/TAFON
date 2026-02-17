# backend/app/schemas/field_execution_schema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# =============================================================================
# SCHEMAS PARA AVALIACAO EM CAMPO
# =============================================================================

class CandidateFieldStatus(BaseModel):
    """Status de um candidato na avaliacao em campo"""
    candidate_id: int
    candidate_number: str = Field(..., description="Numero de peito do candidato")
    full_name: str
    gender: str
    status: str = Field(..., description="pending, in_progress, completed, awaiting_retry")
    evaluator_name: Optional[str] = None
    current_attempt: int = Field(default=1)
    max_attempts: int
    results: List[dict] = Field(default_factory=list)
    best_result: Optional[float] = None
    is_approved: Optional[bool] = None
    
    model_config = ConfigDict(from_attributes=True)


class StartEvaluationRequest(BaseModel):
    """Inicia avaliacao de um candidato (lock)"""
    candidate_id: int
    exercise_id: int
    evaluator_user_id: Optional[int] = Field(default=1, description="ID do avaliador (opcional, padrao: sistema)")


class StartEvaluationResponse(BaseModel):
    """Resposta ao iniciar avaliacao"""
    success: bool
    candidate_id: int
    candidate_number: str
    full_name: str
    gender: str
    current_attempt: int
    max_attempts: int
    locked_until: datetime
    message: str


class FinishEvaluationRequest(BaseModel):
    """Finaliza avaliacao e salva resultado"""
    candidate_id: int
    exercise_id: int
    measured_value: float
    attempt_number: int
    is_valid: bool = True


class FinishEvaluationResponse(BaseModel):
    """Resposta ao finalizar avaliacao"""
    success: bool
    result_id: int
    is_approved: Optional[bool] = None
    message: str


class BatchExecutionStatus(BaseModel):
    exercise_id: int
    exercise_name: str
    execution_mode: str
    measurement_type: str

    batch_name: str
    batch_number: Optional[int] = None   # 👈 ADICIONAR

    total_candidates: int
    candidates: List[CandidateFieldStatus]

    pending_count: int
    in_progress_count: int
    completed_count: int
    approved_count: int
    failed_count: int


class QuickResultInput(BaseModel):
    """Input rapido para modo coletivo"""
    candidate_id: int
    measured_value: float
    is_valid: bool = True
