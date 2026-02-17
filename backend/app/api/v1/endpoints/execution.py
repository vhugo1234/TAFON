# backend/app/api/v1/endpoints/execution.py

from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import logging
from pydantic import BaseModel

from app.api.deps_tenant import get_tenant_db_session
from app.api.deps import get_current_user
from app.db.models.tenant import ExecutionResult, Candidate, Exercise, PassCriteria, Event
from app.schemas.execution_schema import (
    ExecutionResultCreate, ExecutionResultOut, ExecutionResultUpdate,
    BulkExecutionCreate, BulkExecutionResult,
    CandidateProgress, ExerciseStats, EventExecutionSummary
)

router = APIRouter(tags=["TAF - Módulo 4: Execução"])

logger = logging.getLogger("uvicorn.error")


class BulkResultsRequest(BaseModel):
    exercise_id: int
    candidate_ids: List[int]


def _get_user_id(current_user: Any) -> Optional[int]:
    """Robust extractor for user id from the dependency (could be dict or object)."""
    if not current_user:
        return None
    if isinstance(current_user, dict):
        return current_user.get("id") or current_user.get("user_id") or current_user.get("userId")
    return getattr(current_user, "id", getattr(current_user, "user_id", None))


# =============================================================================
# ROTAS DE LANÇAMENTO DE RESULTADOS
# =============================================================================

@router.post("/", response_model=ExecutionResultOut, status_code=status.HTTP_201_CREATED)
def record_execution_result(
    result_in: ExecutionResultCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user: Any = Depends(get_current_user)
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

    # Valida número máximo de tentativas (aplica-se apenas para criação de novos resultados)
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

    # Pega id do avaliador a partir do token (não confiar no payload enviado pelo cliente)
    evaluator_id = _get_user_id(current_user)

    if not evaluator_id:
        logger.warning("record_execution_result: current_user not resolved; evaluator_user_id will be None (consider investigating get_current_user)")

    # Cria o resultado
    db_result = ExecutionResult(
        candidate_id=result_in.candidate_id,
        exercise_id=result_in.exercise_id,
        measured_value=result_in.measured_value,
        attempt_number=result_in.attempt_number,
        is_valid=result_in.is_valid,
        is_approved_in_exercise=is_approved,
        evaluator_user_id=evaluator_id
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
    db: Session = Depends(get_tenant_db_session),
    current_user: Any = Depends(get_current_user)
):
    """
    Registra múltiplos resultados de uma vez (útil para sincronização offline).

    Comportamento:
    - Se o item vier com `id` (ou `result_id`) -> atualiza esse registro.
    - Senão, se já existir um resultado para (candidate_id, exercise_id, attempt_number) -> atualiza esse registro.
    - Senão -> cria novo resultado, respeitando o limite de tentativas.
    - Retorna summary + updated_results[] para o frontend aplicar optimistic update.
    """
    logger.info("bulk_record_results called: total_incoming=%s evaluator_resolved=%s",
                len(bulk_data.results or []), bool(_get_user_id(current_user)))

    result = BulkExecutionResult(
        total=len(bulk_data.results or []),
        success=0,
        failed=0,
        errors=[]
    )
    updated_results = []

    evaluator_id = _get_user_id(current_user)
    if not evaluator_id:
        logger.warning("bulk_record_results: current_user not resolved; will fallback to payload evaluator_user_id when present")

    for idx, item in enumerate(bulk_data.results or [], start=1):
        try:
            # Normaliza item para dict
            if isinstance(item, dict):
                rd = item
            else:
                rd = item.model_dump() if hasattr(item, "model_dump") else (item.dict() if hasattr(item, "dict") else dict(item))

            logger.debug("Processing bulk item #%s: %s", idx, rd)

            incoming_id = rd.get("id") or rd.get("result_id")
            incoming_evaluator = rd.get("evaluator_user_id")

            # Helpers locais para buscar candidate/exercise safely
            def get_candidate(cid: int):
                try:
                    return db.query(Candidate).filter(Candidate.id == int(cid)).first()
                except Exception as e:
                    # problema com search_path/schema/table
                    logger.exception("DB error when querying Candidate for id=%s: %s", cid, e)
                    raise Exception("Erro de banco ao buscar candidato. Verifique search_path/schema e migrações (relation 'candidates' pode não existir no schema atual).")

            def get_exercise(eid: int):
                try:
                    return db.query(Exercise).filter(Exercise.id == int(eid)).first()
                except Exception as e:
                    logger.exception("DB error when querying Exercise for id=%s: %s", eid, e)
                    raise Exception("Erro de banco ao buscar exercício.")

            # Atualizar se veio id explícito
            if incoming_id:
                db_result = db.query(ExecutionResult).filter(ExecutionResult.id == int(incoming_id)).first()
                if not db_result:
                    raise Exception(f"Resultado com id {incoming_id} não encontrado para atualização.")

                # Atualiza campos permitidos
                if "measured_value" in rd and rd["measured_value"] is not None:
                    db_result.measured_value = rd["measured_value"]
                if "is_valid" in rd and rd["is_valid"] is not None:
                    db_result.is_valid = bool(rd["is_valid"])
                if "attempt_number" in rd and rd["attempt_number"] is not None:
                    db_result.attempt_number = int(rd["attempt_number"])

                # Recalcula aprovação
                candidate = get_candidate(db_result.candidate_id)
                exercise = get_exercise(db_result.exercise_id)
                if not candidate or not exercise:
                    raise Exception("Candidato ou exercício relacionados não encontrados para recalcular aprovação.")

                criteria = db.query(PassCriteria).filter(
                    and_(
                        PassCriteria.exercise_id == db_result.exercise_id,
                        PassCriteria.gender == candidate.gender
                    )
                ).first()
                if criteria and db_result.measured_value is not None:
                    db_result.is_approved_in_exercise = _check_approval(db_result.measured_value, criteria, exercise.unit_of_measure)

                # Prefer evaluator from token
                db_result.evaluator_user_id = evaluator_id or incoming_evaluator

                db.add(db_result)
                db.commit()
                db.refresh(db_result)

                updated_results.append({
                    "id": db_result.id,
                    "candidate_id": db_result.candidate_id,
                    "exercise_id": db_result.exercise_id,
                    "measured_value": db_result.measured_value,
                    "attempt_number": db_result.attempt_number,
                    "is_valid": db_result.is_valid,
                    "is_approved_in_exercise": db_result.is_approved_in_exercise,
                    "evaluator_user_id": db_result.evaluator_user_id
                })
                result.success += 1
                continue

            # Sem id -> tentaremos achar por (candidate_id,exercise_id,attempt_number)
            candidate_id = int(rd.get("candidate_id"))
            exercise_id = int(rd.get("exercise_id"))
            attempt_number = int(rd.get("attempt_number"))

            # Busca exercício/candidato (valida existência)
            candidate = get_candidate(candidate_id)
            if not candidate:
                raise Exception(f"Candidato id={candidate_id} não encontrado.")
            exercise_obj = get_exercise(exercise_id)
            if not exercise_obj:
                raise Exception(f"Exercício id={exercise_id} não encontrado.")

            # Verifica se já existe um resultado para esse attempt_number
            existing_same_attempt = db.query(ExecutionResult).filter(
                ExecutionResult.candidate_id == candidate_id,
                ExecutionResult.exercise_id == exercise_id,
                ExecutionResult.attempt_number == attempt_number
            ).first()

            if existing_same_attempt:
                # Atualiza esse registro ao invés de criar (evita erro de max_attempts quando frontend não passou id)
                if "measured_value" in rd and rd["measured_value"] is not None:
                    existing_same_attempt.measured_value = rd["measured_value"]
                if "is_valid" in rd and rd["is_valid"] is not None:
                    existing_same_attempt.is_valid = bool(rd["is_valid"])

                # recalcula aprovação
                criteria = db.query(PassCriteria).filter(
                    and_(
                        PassCriteria.exercise_id == exercise_id,
                        PassCriteria.gender == candidate.gender
                    )
                ).first()
                if criteria and existing_same_attempt.measured_value is not None:
                    existing_same_attempt.is_approved_in_exercise = _check_approval(existing_same_attempt.measured_value, criteria, exercise_obj.unit_of_measure)

                existing_same_attempt.evaluator_user_id = evaluator_id or incoming_evaluator

                db.add(existing_same_attempt)
                db.commit()
                db.refresh(existing_same_attempt)

                updated_results.append({
                    "id": existing_same_attempt.id,
                    "candidate_id": existing_same_attempt.candidate_id,
                    "exercise_id": existing_same_attempt.exercise_id,
                    "measured_value": existing_same_attempt.measured_value,
                    "attempt_number": existing_same_attempt.attempt_number,
                    "is_valid": existing_same_attempt.is_valid,
                    "is_approved_in_exercise": existing_same_attempt.is_approved_in_exercise,
                    "evaluator_user_id": existing_same_attempt.evaluator_user_id
                })
                result.success += 1
                continue

            # Não existe same_attempt -> vamos criar novo, mas respeitando limite de tentativas
            existing_attempts_count = db.query(func.count(ExecutionResult.id)).filter(
                ExecutionResult.candidate_id == candidate_id,
                ExecutionResult.exercise_id == exercise_id
            ).scalar() or 0

            if existing_attempts_count >= exercise_obj.max_attempts:
                # impossível criar nova tentativa — retorna erro claro
                raise Exception(f"Número máximo de tentativas ({exercise_obj.max_attempts}) já atingido para este exercício.")

            # Cria novo ExecutionResult (logic similar ao record_execution_result mas inline para manter controle)
            measured_value = rd.get("measured_value")
            is_valid = bool(rd.get("is_valid", True))
            is_approved = False

            # Busca criteria para aprovação
            criteria = db.query(PassCriteria).filter(
                and_(
                    PassCriteria.exercise_id == exercise_id,
                    PassCriteria.gender == candidate.gender
                )
            ).first()
            if not criteria:
                raise Exception(f"Critério de aprovação não definido para o sexo {candidate.gender} neste exercício.")

            if measured_value is not None:
                is_approved = _check_approval(float(measured_value), criteria, exercise_obj.unit_of_measure)

            new_result = ExecutionResult(
                candidate_id=candidate_id,
                exercise_id=exercise_id,
                measured_value=measured_value,
                attempt_number=attempt_number,
                is_valid=is_valid,
                is_approved_in_exercise=is_approved,
                evaluator_user_id=evaluator_id or incoming_evaluator
            )

            db.add(new_result)
            db.commit()
            db.refresh(new_result)

            updated_results.append({
                "id": new_result.id,
                "candidate_id": new_result.candidate_id,
                "exercise_id": new_result.exercise_id,
                "measured_value": new_result.measured_value,
                "attempt_number": new_result.attempt_number,
                "is_valid": new_result.is_valid,
                "is_approved_in_exercise": new_result.is_approved_in_exercise,
                "evaluator_user_id": new_result.evaluator_user_id
            })
            result.success += 1

        except Exception as e:
            # rollback and collect error
            try:
                db.rollback()
            except Exception:
                logger.exception("Erro ao dar rollback para item %s", idx)
            result.failed += 1
            err_msg = f"Resultado {idx}: {str(e)}"
            result.errors.append(err_msg)
            logger.exception("bulk_record_results item %s failed: %s", idx, e)

    # Monta retorno
    try:
        return_obj = result.model_dump() if hasattr(result, "model_dump") else (result.dict() if hasattr(result, "dict") else result)
    except Exception:
        return_obj = {
            "total": result.total,
            "success": result.success,
            "failed": result.failed,
            "errors": result.errors
        }

    return_obj["updated_results"] = updated_results
    logger.info("bulk_record_results finished: success=%s failed=%s updated=%s", result.success, result.failed, len(updated_results))
    return return_obj


@router.patch("/{result_id}", response_model=ExecutionResultOut)
def update_execution_result(
    result_id: int,
    result_in: ExecutionResultUpdate,
    db: Session = Depends(get_tenant_db_session),
    current_user: Any = Depends(get_current_user)
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

    # Recalcula aprovação se measured_value presente
    try:
        candidate = db.query(Candidate).filter(Candidate.id == db_result.candidate_id).first()
        exercise = db.query(Exercise).filter(Exercise.id == db_result.exercise_id).first()
        if candidate and exercise and db_result.measured_value is not None:
            criteria = db.query(PassCriteria).filter(
                and_(
                    PassCriteria.exercise_id == db_result.exercise_id,
                    PassCriteria.gender == candidate.gender
                )
            ).first()
            if criteria:
                db_result.is_approved_in_exercise = _check_approval(db_result.measured_value, criteria, exercise.unit_of_measure)
    except Exception:
        # ignore recalculation errors here (will be surfaced on commit if any)
        pass

    # assegura que o avaliador seja o usuário autenticado (ou atualiza para ele)
    evaluator_id = _get_user_id(current_user)
    if evaluator_id:
        db_result.evaluator_user_id = evaluator_id

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
    results = db.query(ExecutionResult).filter(ExecutionResult.exercise_id == exercise_id).all()

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


@router.post("/results/bulk")
def bulk_fetch_results(
    payload: BulkResultsRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: Any = Depends(get_current_user)
):
    """
    Retorna os ExecutionResult agrupados por candidate_id para um dado exercise_id.
    Request body: { "exercise_id": 24, "candidate_ids": [101,102,103] }
    Resposta: { "results": { "101": [ {...}, ... ], "102": [...], ... } }
    """
    exercise_id = int(payload.exercise_id)
    candidate_ids = [int(x) for x in (payload.candidate_ids or [])]

    if not candidate_ids:
        raise HTTPException(status_code=400, detail="candidate_ids is required and must be non-empty")

    MAX_IDS = 500
    if len(candidate_ids) > MAX_IDS:
        raise HTTPException(status_code=400, detail=f"Too many candidate_ids (max {MAX_IDS})")

    try:
        rows = db.query(ExecutionResult).filter(
            ExecutionResult.exercise_id == exercise_id,
            ExecutionResult.candidate_id.in_(candidate_ids)
        ).order_by(ExecutionResult.candidate_id, ExecutionResult.attempt_number).all()
    except Exception as e:
        logger.exception("bulk_fetch_results: db query failed")
        raise HTTPException(status_code=500, detail="Erro ao consultar resultados no banco")

    # agrupa por candidate_id
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for r in rows:
        item = {
            "id": r.id,
            "candidate_id": r.candidate_id,
            "exercise_id": r.exercise_id,
            "attempt_number": r.attempt_number,
            "measured_value": r.measured_value,
            "is_valid": r.is_valid,
            "is_approved_in_exercise": r.is_approved_in_exercise
        }
        grouped.setdefault(int(r.candidate_id), []).append(item)

    # garantir que todas as candidate_ids pedidas existam na resposta (mesmo que vazias)
    results: Dict[str, List[Dict[str, Any]]] = {}
    for cid in candidate_ids:
        arr = grouped.get(int(cid), [])
        # opcional: garantir ordenação por attempt_number
        arr.sort(key=lambda x: (x.get("attempt_number") or 0))
        results[str(cid)] = arr  # usar string keys por segurança no frontend

    return {"results": results}
