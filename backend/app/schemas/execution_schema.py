# backend/app/schemas/execution_schema.py

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

# ------------------------------------------------------------------
# Modelo para Registro de Resultado (Input)
# ------------------------------------------------------------------

class ExecutionResultCreate(BaseModel):
    """
    Schema para registrar o resultado de uma tentativa de exercício.
    """
    candidate_id: int = Field(..., description="ID do candidato que realizou o exercício.")
    exercise_id: int = Field(..., description="ID do exercício realizado.")
    measured_value: float = Field(..., description="Valor medido/registrado (ex: tempo em segundos, repetições).")
    attempt_number: int = Field(..., description="Número da tentativa (1, 2, 3, etc.).")
    # O user_id do avaliador é injetado pela dependência do FastAPI (get_current_user)

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# Modelo para Registro de Resultado (Output)
# ------------------------------------------------------------------

class ExecutionResultOut(BaseModel):
    """
    Schema para retorno de um resultado de execução.
    Corresponde ao modelo ORM ExecutionResult.
    """
    id: int
    candidate_id: int
    exercise_id: int
    measured_value: float
    attempt_number: int
    status: str = Field(..., description="Status da tentativa: 'P' (Pass), 'F' (Fail), 'N/A'.")
    evaluator_user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# ------------------------------------------------------------------
# Modelo para Resumo de Resultados do Candidato
# ------------------------------------------------------------------

class ResultSummaryOut(BaseModel):
    """
    Schema para retornar o resultado final (melhor tentativa) de um exercício.
    """
    exercise_id: int
    exercise_name: str
    best_value: float = Field(..., description="Melhor valor medido (melhor tempo ou maior repetição).")
    best_attempt: int
    final_status: str = Field(..., description="Status final: 'P' (Pass) ou 'F' (Fail).")
    
    class Config:
        from_attributes = True