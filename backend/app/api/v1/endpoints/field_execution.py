# backend/app/api/v1/endpoints/field_execution.py
# ASCII-only version to avoid encoding issues

from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
import logging

from app.api.deps_tenant import get_tenant_db_session
from app.api.deps import get_current_user
from app.db.models.tenant import Exercise, Candidate, ExecutionResult, PassCriteria, ExerciseEvaluator, UserTenant
from app.schemas.field_execution_schema import (
    CandidateFieldStatus,
    StartEvaluationRequest,
    StartEvaluationResponse,
    FinishEvaluationRequest,
    FinishEvaluationResponse,
    BatchExecutionStatus
)

router = APIRouter(tags=["TAF - Execucao em Campo"])

logger = logging.getLogger("uvicorn.error")

# Simple in-memory lock cache (for prod use Redis)
execution_locks = {}

def _derive_user_id(current_user: Any) -> int | None:
    """Extract user id from payload returned by get_current_user (dict or object)."""
    if not current_user:
        return None
    if isinstance(current_user, dict):
        return current_user.get("id") or current_user.get("user_id") or current_user.get("userId")
    return getattr(current_user, "id", getattr(current_user, "user_id", None))


# Substitua a função get_batch_execution_status pelo conteúdo abaixo

@router.get("/exercise/{exercise_id}/batch", response_model=BatchExecutionStatus)
def get_batch_execution_status(
    exercise_id: int,
    batch_name: str,
    start_date: str | None = None,
    start_time: str | None = None,
    db: Session = Depends(get_tenant_db_session)
):
    # Find exercise
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercicio nao encontrado")

    # Build candidate query: always filter by event_id + batch_name,
    # and also by start_date/start_time if provided (these identify the session)
    from sqlalchemy import and_
    query = db.query(Candidate).filter(
        and_(
            Candidate.event_id == exercise.event_id,
            Candidate.batch_name == batch_name
        )
    )

    if start_date:
        # If Candidate.start_date is a date column, ensure types match (or convert)
        query = query.filter(Candidate.start_date == start_date)
    if start_time:
        query = query.filter(Candidate.start_time == start_time)

    # Order for stable results
    candidates = query.order_by(Candidate.batch_number, Candidate.id).all()

    if not candidates:
        raise HTTPException(status_code=404, detail="Turma nao encontrada")

    # Load pass criteria map by gender
    criteria_map = { c.gender: c for c in db.query(PassCriteria).filter(PassCriteria.exercise_id == exercise_id).all() }

    candidates_status = []
    pending_count = in_progress_count = completed_count = approved_count = failed_count = 0

    for candidate in candidates:
        # Fetch ALL results (ordered by attempt_number)
        results = db.query(ExecutionResult).filter(
            and_(
                ExecutionResult.candidate_id == candidate.id,
                ExecutionResult.exercise_id == exercise_id
            )
        ).order_by(ExecutionResult.attempt_number).all()

        attempts_made = len(results)

        # Determine locks / in_progress
        lock_key = f"{exercise_id}_{candidate.id}"
        if lock_key in execution_locks:
            lock_info = execution_locks[lock_key]
            if lock_info['locked_until'] > datetime.now():
                status_str = 'in_progress'
                evaluator_name = lock_info.get('evaluator_name')
                in_progress_count += 1
            else:
                del execution_locks[lock_key]
                status_str = 'pending' if not results else ('completed' if attempts_made >= exercise.max_attempts else 'awaiting_retry')
                evaluator_name = None
        else:
            status_str = 'pending' if not results else ('completed' if attempts_made >= exercise.max_attempts else 'awaiting_retry')
            evaluator_name = None

        # Approval and best_result logic
        approved_results = [r for r in results if getattr(r, "is_approved_in_exercise", False)]
        is_approved = None
        best_result = None
        concluded_attempt_number = None

        if approved_results:
            approved_results.sort(key=lambda r: r.attempt_number or 0)
            winner = approved_results[0]
            is_approved = True
            best_result = winner.measured_value
            concluded_attempt_number = winner.attempt_number
            status_str = 'completed'
            approved_count += 1
        else:
            valid_results = [r for r in results if r.is_valid and r.measured_value is not None]
            if valid_results:
                if exercise.measurement_type == 'time':
                    best_result = min(r.measured_value for r in valid_results)
                else:
                    best_result = max(r.measured_value for r in valid_results)
                criterion = criteria_map.get(candidate.gender)
                if criterion and best_result is not None:
                    if exercise.measurement_type == 'time':
                        is_approved = best_result <= (criterion.max_time_s or criterion.min_value)
                    else:
                        is_approved = best_result >= criterion.min_value
                    if is_approved:
                        status_str = 'completed'
                        approved_count += 1
            else:
                is_approved = None

        if status_str == 'completed' and not is_approved:
            completed_count += 1
            failed_count += 1
        elif status_str == 'completed' and is_approved:
            completed_count += 1

        if concluded_attempt_number is not None:
            current_attempt = concluded_attempt_number
        elif status_str == 'completed' and attempts_made > 0:
            current_attempt = attempts_made
        else:
            current_attempt = attempts_made + 1

        candidates_status.append(CandidateFieldStatus(
            candidate_id=candidate.id,
            candidate_number=str(candidate.batch_number) if candidate.batch_number else str(candidate.id),
            full_name=candidate.full_name,
            gender=candidate.gender,
            status=status_str,
            evaluator_name=evaluator_name,
            current_attempt=current_attempt,
            max_attempts=exercise.max_attempts,
            results=[{
                'attempt': r.attempt_number,
                'value': r.measured_value,
                'is_valid': r.is_valid,
                'is_approved': getattr(r, "is_approved_in_exercise", None)
            } for r in results],
            best_result=best_result,
            is_approved=is_approved
        ))

    return BatchExecutionStatus(
        exercise_id=exercise_id,
        exercise_name=exercise.name,
        execution_mode=exercise.execution_mode,
        measurement_type=exercise.measurement_type,
        batch_name=batch_name,
        batch_number=None,
        total_candidates=len(candidates),
        candidates=candidates_status,
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        completed_count=completed_count,
        approved_count=approved_count,
        failed_count=failed_count
    )


@router.post("/start", response_model=StartEvaluationResponse)
def start_candidate_evaluation(
    request: StartEvaluationRequest,
    db: Session = Depends(get_tenant_db_session)
):
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato nao encontrado")

    exercise = db.query(Exercise).filter(Exercise.id == request.exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercicio nao encontrado")

    evaluator_name = "Sistema"
    if request.evaluator_user_id:
        evaluator = db.query(UserTenant).filter(UserTenant.id == request.evaluator_user_id).first()
        evaluator_name = evaluator.nome if evaluator else "Sistema"

    attempts_count = db.query(ExecutionResult).filter(
        and_(
            ExecutionResult.candidate_id == request.candidate_id,
            ExecutionResult.exercise_id == request.exercise_id
        )
    ).count()

    if attempts_count >= exercise.max_attempts:
        raise HTTPException(
            status_code=400,
            detail=f"Candidato ja completou o maximo de tentativas ({exercise.max_attempts})"
        )

    lock_key = f"{request.exercise_id}_{request.candidate_id}"
    if lock_key in execution_locks:
        lock_info = execution_locks[lock_key]
        if lock_info['locked_until'] > datetime.now():
            raise HTTPException(
                status_code=409,
                detail=f"Candidato ja esta sendo avaliado por {lock_info['evaluator_name']}"
            )

    locked_until = datetime.now() + timedelta(minutes=10)
    execution_locks[lock_key] = {
        'evaluator_user_id': request.evaluator_user_id or 1,
        'evaluator_name': evaluator_name,
        'locked_until': locked_until
    }

    return StartEvaluationResponse(
        success=True,
        candidate_id=candidate.id,
        candidate_number=str(candidate.batch_number) if candidate.batch_number else str(candidate.id),
        full_name=candidate.full_name,
        gender=candidate.gender,
        current_attempt=attempts_count + 1,
        max_attempts=exercise.max_attempts,
        locked_until=locked_until,
        message=f"Avaliacao iniciada para {candidate.full_name}"
    )


@router.post("/finish", response_model=FinishEvaluationResponse)
def finish_candidate_evaluation(
    request: FinishEvaluationRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: Any = Depends(get_current_user)
):
    evaluator_id = _derive_user_id(current_user)
    if not evaluator_id:
        logger.warning("finish_candidate_evaluation: current_user not resolved; evaluator_id will be None")

    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato nao encontrado")

    exercise = db.query(Exercise).filter(Exercise.id == request.exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercicio nao encontrado")

    criterion = db.query(PassCriteria).filter(
        and_(
            PassCriteria.exercise_id == request.exercise_id,
            PassCriteria.gender == candidate.gender
        )
    ).first()

    is_approved = None
    if criterion:
        if exercise.measurement_type == 'time':
            is_approved = request.measured_value <= (criterion.max_time_s or criterion.min_value)
        else:
            is_approved = request.measured_value >= criterion.min_value

    result = ExecutionResult(
        candidate_id=request.candidate_id,
        exercise_id=request.exercise_id,
        measured_value=request.measured_value,
        attempt_number=request.attempt_number,
        is_valid=request.is_valid,
        is_approved_in_exercise=is_approved,
        evaluator_user_id=evaluator_id
    )

    try:
        db.add(result)
        # ensure id populated on same connection without triggering a separate SELECT on another connection
        db.flush()
        new_id = result.id
        db.commit()

        # try refreshing but do not fail if refresh triggers a search_path/connection error
        try:
            db.refresh(result)
        except Exception as refresh_exc:
            logger.warning("refresh failed after commit for ExecutionResult id=%s: %s", new_id, refresh_exc)

        lock_key = f"{request.exercise_id}_{request.candidate_id}"
        if lock_key in execution_locks:
            del execution_locks[lock_key]

        return FinishEvaluationResponse(
            success=True,
            result_id=new_id,
            is_approved=is_approved,
            message="Resultado salvo com sucesso"
        )
    except Exception as e:
        db.rollback()
        try:
            existing = db.query(ExecutionResult).filter(
                and_(
                    ExecutionResult.candidate_id == request.candidate_id,
                    ExecutionResult.exercise_id == request.exercise_id,
                    ExecutionResult.attempt_number == request.attempt_number
                )
            ).order_by(ExecutionResult.id.desc()).first()
            if existing:
                logger.warning("finish_candidate_evaluation: exception after commit but found record id=%s; returning success-with-warning. exc=%s", existing.id, e)
                lock_key = f"{request.exercise_id}_{request.candidate_id}"
                if lock_key in execution_locks:
                    del execution_locks[lock_key]
                return FinishEvaluationResponse(
                    success=True,
                    result_id=existing.id,
                    is_approved=getattr(existing, "is_approved_in_exercise", None),
                    message="Resultado possivelmente salvo (erro pos-persistencia). Ver logs."
                )
        except Exception:
            pass

        logger.exception("Erro ao salvar resultado em finish_candidate_evaluation: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro ao salvar resultado: {e}")


@router.delete("/cancel/{exercise_id}/{candidate_id}")
def cancel_evaluation(
    exercise_id: int,
    candidate_id: int
):
    lock_key = f"{exercise_id}_{candidate_id}"

    if lock_key in execution_locks:
        del execution_locks[lock_key]
        return {"success": True, "message": "Avaliacao cancelada"}

    raise HTTPException(status_code=404, detail="Nenhuma avaliacao em andamento")