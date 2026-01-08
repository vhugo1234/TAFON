# backend/app/api/v1/endpoints/execution.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.api.deps_tenant import get_tenant_db_session 
from app.db.models.tenant import ExecutionResult, Candidate, Exercise, PassCriteria, Event
from app.schemas.execution_schema import (
    ExecutionResultCreate, ExecutionResultOut, ExecutionResultUpdate,
    BulkExecutionCreate, BulkExecutionResult,
    CandidateProgress, ExerciseStats, EventExecutionSummary
)

router = APIRouter(tags=["TAF - Módulo 4: Execução"])

# =============================================================================
# ROTAS DE LANÇAMENTO DE RESULTADOS
# =============================================================================

@router.post("/", response_model=ExecutionResultOut, status_code=status.HTTP_201_CREATED)
def record_execution_result(
    result_in: ExecutionResultCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Registra o resultado de uma tentativa de exercício para um candidato.
    Calcula automaticamente se o resultado atende aos critérios de aprovação.
    """
    # Valida candidato e exercício
    candidate = db.query(Candidate).filter(Candidate.id == result_in.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato não encontrado."
        )
    
    exercise = db.query(Exercise).filter(Exercise.id == result_in.exercise_id).first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercício não encontrado."
        )
    
    # Busca critério de aprovação
    criteria = db.query(PassCriteria).filter(
        and_(
            PassCriteria.exercise_id == result_in.exercise_id,
            PassCriteria.gender == candidate.gender
        )
    ).first()
    
    if not criteria:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Critério de aprovação não definido para o sexo {candidate.gender} neste exercício."
        )
    
    # Valida número máximo de tentativas
    existing_attempts = db.query(func.count(ExecutionResult.id)).filter(
        and_(
            ExecutionResult.candidate_id == result_in.candidate_id,
            ExecutionResult.exercise_id == result_in.exercise_id
        )
    ).scalar()
    
    if existing_attempts >= exercise.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Número máximo de tentativas ({exercise.max_attempts}) já atingido para este exercício."
        )
    
    # Calcula aprovação
    is_approved = _check_approval(result_in.measured_value, criteria, exercise.unit_of_measure)
    
    # Cria o resultado
    db_result = ExecutionResult(
        candidate_id=result_in.candidate_id,
        exercise_id=result_in.exercise_id,
        measured_value=result_in.measured_value,
        attempt_number=result_in.attempt_number,
        is_valid=result_in.is_valid,
        is_approved_in_exercise=is_approved,
        evaluator_user_id=None  # TODO: Pegar do token JWT
    )
    
    try:
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        
        # Adiciona nomes relacionados
        db_result.candidate_name = candidate.full_name
        db_result.exercise_name = exercise.name
        
        return db_result
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar resultado: {e}"
        )


def _check_approval(value: float, criteria: PassCriteria, unit: str) -> bool:
    """Verifica se o valor atende ao critério de aprovação"""
    # Para repetições/metros: valor deve ser >= mínimo
    if 'repet' in unit.lower() or 'metro' in unit.lower() or 'dist' in unit.lower():
        return value >= criteria.min_value
    
    # Para tempo: valor deve ser <= máximo
    if 'tempo' in unit.lower() or 'segundo' in unit.lower():
        if criteria.max_time_s is not None:
            return value <= criteria.max_time_s
        return value <= criteria.min_value  # Fallback
    
    # Padrão: >= mínimo
    return value >= criteria.min_value


@router.post("/bulk", response_model=BulkExecutionResult)
def bulk_record_results(
    bulk_data: BulkExecutionCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """Registra múltiplos resultados de uma vez (útil para sincronização offline)"""
    result = BulkExecutionResult(
        total=len(bulk_data.results),
        success=0,
        failed=0,
        errors=[]
    )
    
    for idx, result_data in enumerate(bulk_data.results, start=1):
        try:
            # Reutiliza a lógica do endpoint individual
            record_execution_result(result_data, db)
            result.success += 1
        except Exception as e:
            result.failed += 1
            result.errors.append(f"Resultado {idx}: {str(e)}")
    
    return result


@router.patch("/{result_id}", response_model=ExecutionResultOut)
def update_execution_result(
    result_id: int,
    result_in: ExecutionResultUpdate,
    db: Session = Depends(get_tenant_db_session)
):
    """Atualiza um resultado existente (correção)"""
    db_result = db.query(ExecutionResult).filter(ExecutionResult.id == result_id).first()
    if not db_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado não encontrado."
        )
    
    update_data = result_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_result, key, value)
    
    try:
        db.commit()
        db.refresh(db_result)
        return db_result
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar resultado: {e}"
        )


@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_execution_result(
    result_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Deleta um resultado (apenas para correções)"""
    db_result = db.query(ExecutionResult).filter(ExecutionResult.id == result_id).first()
    if not db_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado não encontrado."
        )
    
    try:
        db.delete(db_result)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar resultado: {e}"
        )


# =============================================================================
# ROTAS DE CONSULTA/RELATÓRIO
# =============================================================================

@router.get("/candidate/{candidate_id}", response_model=List[ExecutionResultOut])
def get_candidate_results(
    candidate_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna todos os resultados de um candidato"""
    results = db.query(ExecutionResult).filter(
        ExecutionResult.candidate_id == candidate_id
    ).all()
    
    # Adiciona nomes relacionados
    for result in results:
        candidate = db.query(Candidate).filter(Candidate.id == result.candidate_id).first()
        exercise = db.query(Exercise).filter(Exercise.id == result.exercise_id).first()
        
        if candidate:
            result.candidate_name = candidate.full_name
        if exercise:
            result.exercise_name = exercise.name
    
    return results


@router.get("/exercise/{exercise_id}", response_model=List[ExecutionResultOut])
def get_exercise_results(
    exercise_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna todos os resultados de um exercício"""
    results = db.query(ExecutionResult).filter(
        ExecutionResult.exercise_id == exercise_id
    ).all()
    
    # Adiciona nomes
    for result in results:
        candidate = db.query(Candidate).filter(Candidate.id == result.candidate_id).first()
        if candidate:
            result.candidate_name = candidate.full_name
    
    return results


@router.get("/event/{event_id}/progress", response_model=List[CandidateProgress])
def get_event_progress(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna o progresso de todos os candidatos de um evento"""
    # Busca candidatos e exercícios do evento
    candidates = db.query(Candidate).filter(Candidate.event_id == event_id).all()
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    
    total_exercises = len(exercises)
    progress_list = []
    
    for candidate in candidates:
        # Busca resultados do candidato
        results = db.query(ExecutionResult).filter(
            ExecutionResult.candidate_id == candidate.id
        ).all()
        
        # Conta exercícios únicos completados
        completed_exercise_ids = set(r.exercise_id for r in results)
        completed = len(completed_exercise_ids)
        
        # Conta aprovações
        approved = sum(1 for r in results if r.is_approved_in_exercise == True)
        failed = sum(1 for r in results if r.is_approved_in_exercise == False)
        pending = total_exercises - completed
        
        # Status geral
        if completed == total_exercises:
            if approved == total_exercises:
                overall_status = "approved"
            else:
                overall_status = "failed"
        else:
            overall_status = "in_progress"
        
        progress_list.append(CandidateProgress(
            candidate_id=candidate.id,
            candidate_name=candidate.full_name,
            registration_number=candidate.registration_number,
            gender=candidate.gender,
            total_exercises=total_exercises,
            completed_exercises=completed,
            approved_exercises=approved,
            failed_exercises=failed,
            pending_exercises=pending,
            overall_status=overall_status
        ))
    
    return progress_list


@router.get("/event/{event_id}/summary", response_model=EventExecutionSummary)
def get_event_summary(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna o resumo completo da execução de um evento"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    candidates = db.query(Candidate).filter(Candidate.event_id == event_id).all()
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    
    total_candidates = len(candidates)
    total_exercises = len(exercises)
    
    # Estatísticas gerais
    total_results = db.query(func.count(ExecutionResult.id)).join(
        Candidate
    ).filter(Candidate.event_id == event_id).scalar()
    
    # Calcula taxas
    completion_rate = 0.0
    approval_rate = 0.0
    
    if total_candidates > 0 and total_exercises > 0:
        expected_results = total_candidates * total_exercises
        completion_rate = (total_results / expected_results) * 100 if expected_results > 0 else 0
    
    # Estatísticas por exercício
    exercises_stats = []
    for exercise in exercises:
        exercise_results = db.query(ExecutionResult).filter(
            ExecutionResult.exercise_id == exercise.id
        ).all()
        
        unique_candidates = len(set(r.candidate_id for r in exercise_results))
        approved_count = sum(1 for r in exercise_results if r.is_approved_in_exercise == True)
        failed_count = sum(1 for r in exercise_results if r.is_approved_in_exercise == False)
        
        exercises_stats.append(ExerciseStats(
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            total_candidates=total_candidates,
            completed=unique_candidates,
            approved=approved_count,
            failed=failed_count,
            pending=total_candidates - unique_candidates,
            approval_rate=(approved_count / unique_candidates * 100) if unique_candidates > 0 else 0
        ))
    
    return EventExecutionSummary(
        event_id=event_id,
        event_name=event.name,
        total_candidates=total_candidates,
        total_exercises=total_exercises,
        total_results_recorded=total_results or 0,
        candidates_completed=0,  # TODO: Calcular
        candidates_approved=0,
        candidates_failed=0,
        candidates_in_progress=total_candidates,
        completion_rate=completion_rate,
        approval_rate=approval_rate,
        exercises_stats=exercises_stats
    )