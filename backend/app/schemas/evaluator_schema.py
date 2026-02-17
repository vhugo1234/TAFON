# backend/app/schemas/evaluator_schema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# =============================================================================
# SCHEMAS DE VINCULACAO DE AVALIADORES
# =============================================================================

class ExerciseEvaluatorBase(BaseModel):
    """Base para vinculacao avaliador-exercicio"""
    exercise_id: int = Field(..., description="ID do exercicio")
    evaluator_user_id: int = Field(..., description="ID do usuario avaliador")
    is_primary: bool = Field(default=False, description="Se e o avaliador principal")
    
    model_config = ConfigDict(from_attributes=True)


class ExerciseEvaluatorCreate(ExerciseEvaluatorBase):
    """Schema para criar vinculacao"""
    pass


class ExerciseEvaluatorOut(ExerciseEvaluatorBase):
    """Schema de resposta"""
    id: int
    evaluator_name: Optional[str] = None
    evaluator_email: Optional[str] = None
    exercise_name: Optional[str] = None
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class BulkEvaluatorAssignment(BaseModel):
    """Atribuir multiplos avaliadores de uma vez"""
    exercise_id: int
    evaluator_ids: List[int]
    primary_evaluator_id: Optional[int] = None


class EvaluatorWithExercises(BaseModel):
    """Avaliador com seus exercicios"""
    user_id: int
    user_name: str
    user_email: str
    exercises: List[ExerciseEvaluatorOut]
    total_exercises: int


class ExerciseWithEvaluators(BaseModel):
    """Exercicio com seus avaliadores"""
    exercise_id: int
    exercise_name: str
    evaluators: List[ExerciseEvaluatorOut]
    total_evaluators: int
    has_primary: bool
