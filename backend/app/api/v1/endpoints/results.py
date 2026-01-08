from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import io

from app.api.deps_tenant import get_tenant_db_session
from app.db.models.tenant import Event, Exercise, Candidate, ExecutionResult, PassCriteria
from app.schemas.result_schema import (
    CandidateResult, ExerciseResult, AttemptResult,
    EventResultsSummary, ExerciseSummary,
    PDFGenerationRequest, PDFGenerationResponse
)
from app.utils.pdf_generator import generate_candidate_pdf, generate_consolidated_report_pdf

router = APIRouter(tags=["TAF - Módulo 5: Resultados"])

# =============================================================================
# ROTAS DE CONSULTA DE RESULTADOS
# =============================================================================

@router.get("/event/{event_id}/candidates", response_model=List[CandidateResult])
def get_event_results(
    event_id: int,
    gender: Optional[str] = None,
    batch_name: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna resultados consolidados de todos os candidatos de um evento"""
    
    # Busca evento
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    # Busca candidatos com filtros
    query = db.query(Candidate).filter(Candidate.event_id == event_id)
    
    if gender:
        query = query.filter(Candidate.gender == gender)
    if batch_name:
        query = query.filter(Candidate.batch_name == batch_name)
    
    candidates = query.all()
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    
    results_list = []
    
    for candidate in candidates:
        exercises_results = []
        
        for exercise in exercises:
            # Busca resultados do candidato neste exercício
            attempts = db.query(ExecutionResult).filter(
                and_(
                    ExecutionResult.candidate_id == candidate.id,
                    ExecutionResult.exercise_id == exercise.id
                )
            ).all()
            
            # Busca critério
            criteria = db.query(PassCriteria).filter(
                and_(
                    PassCriteria.exercise_id == exercise.id,
                    PassCriteria.gender == candidate.gender
                )
            ).first()
            
            attempts_list = [
                AttemptResult(
                    attempt_number=a.attempt_number,
                    measured_value=a.measured_value,
                    is_valid=a.is_valid,
                    is_approved=a.is_approved_in_exercise
                )
                for a in attempts
            ]
            
            # Melhor tentativa
            best = None
            is_approved = None
            if attempts_list:
                # Para repetições/metros: maior valor
                # Para tempo: menor valor
                if 'tempo' in exercise.unit_of_measure.lower():
                    best = min(attempts_list, key=lambda x: x.measured_value)
                else:
                    best = max(attempts_list, key=lambda x: x.measured_value)
                
                is_approved = best.is_approved
            
            exercises_results.append(ExerciseResult(
                exercise_id=exercise.id,
                exercise_name=exercise.name,
                unit_of_measure=exercise.unit_of_measure,
                attempts=attempts_list,
                best_attempt=best,
                is_completed=len(attempts_list) > 0,
                is_approved=is_approved,
                criteria_min_value=criteria.min_value if criteria else None,
                criteria_max_time=criteria.max_time_s if criteria else None
            ))
        
        # Calcula status geral
        completed = sum(1 for e in exercises_results if e.is_completed)
        approved = sum(1 for e in exercises_results if e.is_approved == True)
        failed = sum(1 for e in exercises_results if e.is_approved == False)
        
        if completed == len(exercises):
            if approved == len(exercises):
                overall_status = "approved"
            else:
                overall_status = "failed"
        else:
            overall_status = "in_progress"
        
        # Filtro por status
        if status and overall_status != status:
            continue
        
        results_list.append(CandidateResult(
            candidate_id=candidate.id,
            candidate_name=candidate.full_name,
            registration_number=candidate.registration_number,
            cpf=candidate.cpf,
            gender=candidate.gender,
            batch_name=candidate.batch_name,
            exercises_results=exercises_results,
            total_exercises=len(exercises),
            completed_exercises=completed,
            approved_exercises=approved,
            failed_exercises=failed,
            overall_status=overall_status
        ))
    
    return results_list


@router.get("/event/{event_id}/summary", response_model=EventResultsSummary)
def get_event_summary(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna resumo estatístico do evento"""
    
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    candidates = db.query(Candidate).filter(Candidate.event_id == event_id).all()
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    
    total_candidates = len(candidates)
    total_exercises = len(exercises)
    
    # Conta status dos candidatos
    approved = 0
    failed = 0
    in_progress = 0
    
    for candidate in candidates:
        results_count = db.query(func.count(func.distinct(ExecutionResult.exercise_id))).filter(
            ExecutionResult.candidate_id == candidate.id
        ).scalar()
        
        if results_count == total_exercises:
            # Verifica se todos aprovados
            approved_count = db.query(func.count(ExecutionResult.id)).filter(
                and_(
                    ExecutionResult.candidate_id == candidate.id,
                    ExecutionResult.is_approved_in_exercise == True
                )
            ).scalar()
            
            if approved_count == total_exercises:
                approved += 1
            else:
                failed += 1
        else:
            in_progress += 1
    
    # Taxas
    approval_rate = (approved / total_candidates * 100) if total_candidates > 0 else 0
    completion_rate = ((approved + failed) / total_candidates * 100) if total_candidates > 0 else 0
    
    # Resumo por exercício
    exercises_summary = []
    for exercise in exercises:
        results = db.query(ExecutionResult).filter(
            ExecutionResult.exercise_id == exercise.id
        ).all()
        
        unique_candidates = len(set(r.candidate_id for r in results))
        approved_count = sum(1 for r in results if r.is_approved_in_exercise == True)
        failed_count = sum(1 for r in results if r.is_approved_in_exercise == False)
        
        # Valores
        values = [r.measured_value for r in results if r.is_valid]
        avg_value = sum(values) / len(values) if values else None
        best_value = max(values) if values else None
        worst_value = min(values) if values else None
        
        exercises_summary.append(ExerciseSummary(
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            unit_of_measure=exercise.unit_of_measure,
            total_candidates=total_candidates,
            candidates_completed=unique_candidates,
            candidates_approved=approved_count,
            candidates_failed=failed_count,
            average_value=avg_value,
            best_value=best_value,
            worst_value=worst_value,
            approval_rate=(approved_count / unique_candidates * 100) if unique_candidates > 0 else 0
        ))
    
    return EventResultsSummary(
        event_id=event_id,
        event_name=event.name,
        event_date=str(event.date_start),
        location=event.location,
        total_candidates=total_candidates,
        total_exercises=total_exercises,
        candidates_approved=approved,
        candidates_failed=failed,
        candidates_in_progress=in_progress,
        approval_rate=approval_rate,
        completion_rate=completion_rate,
        exercises_summary=exercises_summary
    )


# =============================================================================
# ROTAS DE GERAÇÃO DE PDF
# =============================================================================

@router.post("/candidate/{candidate_id}/pdf")
def generate_candidate_pdf_endpoint(
    candidate_id: int,
    event_id: int,
    coordinator_name: Optional[str] = None,
    db: Session = Depends(get_tenant_db_session)
):
    """Gera PDF individual do candidato"""
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")
    
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    # Busca resultados
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    exercises_results = []
    
    for exercise in exercises:
        results = db.query(ExecutionResult).filter(
            and_(
                ExecutionResult.candidate_id == candidate_id,
                ExecutionResult.exercise_id == exercise.id
            )
        ).all()
        
        if results:
            # Pega melhor resultado
            if 'tempo' in exercise.unit_of_measure.lower():
                best = min(results, key=lambda x: x.measured_value)
            else:
                best = max(results, key=lambda x: x.measured_value)
            
            exercises_results.append({
                'exercise_name': exercise.name,
                'unit_of_measure': exercise.unit_of_measure,
                'best_value': best.measured_value,
                'is_approved': best.is_approved_in_exercise
            })
    
    # Determina status geral
    if len(exercises_results) == len(exercises):
        all_approved = all(e.get('is_approved') for e in exercises_results)
        overall_status = 'approved' if all_approved else 'failed'
    else:
        overall_status = 'in_progress'
    
    # Dados para o PDF
    candidate_data = {
        'full_name': candidate.full_name,
        'cpf': candidate.cpf,
        'registration_number': candidate.registration_number,
        'gender': candidate.gender,
        'batch_name': candidate.batch_name,
        'overall_status': overall_status
    }
    
    event_data = {
        'name': event.name,
        'date': str(event.date_start),
        'location': event.location
    }
    
    # Gera PDF
    pdf_bytes = generate_candidate_pdf(
        candidate_data=candidate_data,
        exercises_results=exercises_results,
        event_data=event_data,
        coordinator_name=coordinator_name
    )
    
    # Retorna como download
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="resultado_{candidate.registration_number}.pdf"'
        }
    )


@router.get("/event/{event_id}/pdf-consolidated")
def generate_consolidated_pdf_endpoint(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Gera PDF consolidado com todos os resultados do evento"""
    
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    candidates = db.query(Candidate).filter(Candidate.event_id == event_id).all()
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    
    # Monta lista de resultados
    candidates_results = []
    approved = 0
    failed = 0
    
    for candidate in candidates:
        results_count = db.query(func.count(func.distinct(ExecutionResult.exercise_id))).filter(
            ExecutionResult.candidate_id == candidate.id
        ).scalar()
        
        overall_status = 'in_progress'
        
        if results_count == len(exercises):
            approved_count = db.query(func.count(ExecutionResult.id)).filter(
                and_(
                    ExecutionResult.candidate_id == candidate.id,
                    ExecutionResult.is_approved_in_exercise == True
                )
            ).scalar()
            
            if approved_count == len(exercises):
                overall_status = 'approved'
                approved += 1
            else:
                overall_status = 'failed'
                failed += 1
        
        candidates_results.append({
            'full_name': candidate.full_name,
            'cpf': candidate.cpf,
            'gender': candidate.gender,
            'overall_status': overall_status
        })
    
    event_data = {
        'name': event.name,
        'date': str(event.date_start),
        'location': event.location
    }
    
    summary = {
        'total_candidates': len(candidates),
        'approved': approved,
        'failed': failed,
        'approval_rate': (approved / len(candidates) * 100) if candidates else 0
    }
    
    # Gera PDF
    pdf_bytes = generate_consolidated_report_pdf(
        event_data=event_data,
        candidates_results=candidates_results,
        summary=summary
    )
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="resultado_consolidado_{event.name.replace(" ", "_")}.pdf"'
        }
    )