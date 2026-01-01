# backend/app/api/v1/endpoints/execution.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from app.api.deps_tenant import get_tenant_db_session 
from app.api.deps import get_current_user # Para pegar o ID do avaliador
from app.db.models.tenant import ExecutionResult, Candidate, Exercise, PassCriteria
from app.schemas.execution_schema import ExecutionResultCreate, ExecutionResultOut, ResultSummaryOut

router = APIRouter(tags=["TAF - Módulo 4: Execução"])

# -----------------------------------------------------------
# Rota de Lançamento (Resultado Único)
# -----------------------------------------------------------

@router.post("/", response_model=ExecutionResultOut, status_code=status.HTTP_201_CREATED)
def record_execution_result(
    result_in: ExecutionResultCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user: dict = Depends(get_current_user) # Deve retornar o payload JWT
):
    """
    Registra o resultado de uma tentativa de exercício para um candidato.
    Calcula se o resultado atende aos critérios imediatamente.
    """
    
    # 1. Validação de Candidato e Exercício (E garante que estão no schema do tenant)
    try:
        candidate = db.query(Candidate).filter(Candidate.id == result_in.candidate_id).one()
        exercise = db.query(Exercise).filter(Exercise.id == result_in.exercise_id).one()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Candidato ou Exercício não encontrado.")
    
    # 2. Busca o Critério de Aprovação
    # Assume que o gênero do candidato (candidate.gender) é o critério a ser usado.
    criteria = db.query(PassCriteria).filter(
        PassCriteria.exercise_id == result_in.exercise_id,
        PassCriteria.gender == candidate.gender.upper()
    ).first()
    
    if not criteria:
        raise HTTPException(status_code=400, detail=f"Critério de aprovação para Gênero '{candidate.gender}' não definido neste exercício.")

    # 3. Lógica de Aprovação (Simples)
    # is_passed será 'P' (Pass) ou 'F' (Fail)
    is_passed = "F"
    value = result_in.measured_value

    if exercise.unit_of_measure.lower() in ["repeticoes", "metros", "distancia"]:
        # Se for um valor MÍNIMO a ser atingido (Ex: X repetições, Y metros)
        if value >= criteria.min_value:
            is_passed = "P"
    
    elif exercise.unit_of_measure.lower() in ["tempo (s)", "tempo", "segundos"]:
        # Se for um tempo MÁXIMO a ser atingido (Ex: Corrida, Natação)
        # O valor medido deve ser menor ou igual ao tempo MÁXIMO (max_time_s)
        if criteria.max_time_s is not None and value <= criteria.max_time_s:
            is_passed = "P"

    # 4. Criação do Registro
    evaluator_user_id = current_user.get("user_id") # Pega o ID do payload do JWT
    
    db_result = ExecutionResult(
        candidate_id=result_in.candidate_id,
        exercise_id=result_in.exercise_id,
        measured_value=value,
        attempt_number=result_in.attempt_number,
        evaluator_user_id=evaluator_user_id,
        status=is_passed,
    )
    
    try:
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        return db_result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao registrar resultado: {e}")


# -----------------------------------------------------------
# Rota de Consulta de Histórico
# -----------------------------------------------------------

@router.get("/candidate/{candidate_id}", response_model=List[ExecutionResultOut])
def get_candidate_history(
    candidate_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna o histórico de todas as tentativas de exercícios de um candidato."""
    results = db.query(ExecutionResult).filter(ExecutionResult.candidate_id == candidate_id).all()
    if not results:
        raise HTTPException(status_code=404, detail="Nenhum resultado encontrado para este candidato.")
    
    return results