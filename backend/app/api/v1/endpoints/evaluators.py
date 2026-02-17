# backend/app/api/v1/endpoints/evaluators.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.api.deps_tenant import get_tenant_db_session
from app.db.models.tenant import ExerciseEvaluator, Exercise, UserTenant
from app.schemas.evaluator_schema import (
    ExerciseEvaluatorCreate,
    ExerciseEvaluatorOut,
    BulkEvaluatorAssignment,
    EvaluatorWithExercises,
    ExerciseWithEvaluators
)

router = APIRouter(tags=["TAF - Avaliadores"])

# =============================================================================
# ROTAS DE VINCULAÇÃO DE AVALIADORES
# =============================================================================

@router.post("/", response_model=ExerciseEvaluatorOut, status_code=status.HTTP_201_CREATED)
def assign_evaluator_to_exercise(
    assignment: ExerciseEvaluatorCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """Vincula um avaliador a um exercicio"""
    
    # Verifica se exercicio existe
    exercise = db.query(Exercise).filter(Exercise.id == assignment.exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercicio nao encontrado")
    
    # Verifica se usuario existe
    user = db.query(UserTenant).filter(UserTenant.id == assignment.evaluator_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    
    # Verifica se ja esta vinculado
    existing = db.query(ExerciseEvaluator).filter(
        and_(
            ExerciseEvaluator.exercise_id == assignment.exercise_id,
            ExerciseEvaluator.evaluator_user_id == assignment.evaluator_user_id
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Avaliador ja vinculado a este exercicio")
    
    # Se for primario, remove primario anterior
    if assignment.is_primary:
        db.query(ExerciseEvaluator).filter(
            and_(
                ExerciseEvaluator.exercise_id == assignment.exercise_id,
                ExerciseEvaluator.is_primary == True
            )
        ).update({"is_primary": False})
    
    # Cria vinculacao
    db_assignment = ExerciseEvaluator(**assignment.model_dump())
    
    try:
        db.add(db_assignment)
        db.commit()
        db.refresh(db_assignment)
        
        # Adiciona nomes
        db_assignment.evaluator_name = user.nome
        db_assignment.evaluator_email = user.email
        db_assignment.exercise_name = exercise.name
        
        return db_assignment
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao vincular avaliador: {e}")


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_assign_evaluators(
    assignment: BulkEvaluatorAssignment,
    db: Session = Depends(get_tenant_db_session)
):
    """Atribui multiplos avaliadores a um exercicio de uma vez"""
    
    # Verifica exercicio
    exercise = db.query(Exercise).filter(Exercise.id == assignment.exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercicio nao encontrado")
    
    # Remove vinculacoes anteriores
    db.query(ExerciseEvaluator).filter(
        ExerciseEvaluator.exercise_id == assignment.exercise_id
    ).delete()
    
    created = []
    
    for evaluator_id in assignment.evaluator_ids:
        # Verifica usuario
        user = db.query(UserTenant).filter(UserTenant.id == evaluator_id).first()
        if not user:
            continue  # Pula IDs invalidos
        
        is_primary = (evaluator_id == assignment.primary_evaluator_id)
        
        db_assignment = ExerciseEvaluator(
            exercise_id=assignment.exercise_id,
            evaluator_user_id=evaluator_id,
            is_primary=is_primary
        )
        
        db.add(db_assignment)
        created.append(evaluator_id)
    
    try:
        db.commit()
        return {
            "success": True,
            "exercise_id": assignment.exercise_id,
            "evaluators_assigned": len(created),
            "evaluator_ids": created
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atribuir avaliadores: {e}")


@router.get("/exercise/{exercise_id}", response_model=ExerciseWithEvaluators)
def list_exercise_evaluators(
    exercise_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Lista todos os avaliadores de um exercicio"""
    
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercicio nao encontrado")
    
    assignments = db.query(ExerciseEvaluator).filter(
        ExerciseEvaluator.exercise_id == exercise_id
    ).all()
    
    evaluators_list = []
    has_primary = False
    
    for assignment in assignments:
        user = db.query(UserTenant).filter(UserTenant.id == assignment.evaluator_user_id).first()
        if user:
            evaluators_list.append(ExerciseEvaluatorOut(
                id=assignment.id,
                exercise_id=assignment.exercise_id,
                evaluator_user_id=assignment.evaluator_user_id,
                is_primary=assignment.is_primary,
                evaluator_name=user.nome,
                evaluator_email=user.email,
                exercise_name=exercise.name,
                created_at=assignment.created_at
            ))
            if assignment.is_primary:
                has_primary = True
    
    return ExerciseWithEvaluators(
        exercise_id=exercise_id,
        exercise_name=exercise.name,
        evaluators=evaluators_list,
        total_evaluators=len(evaluators_list),
        has_primary=has_primary
    )


@router.get("/user/{user_id}", response_model=EvaluatorWithExercises)
def list_user_exercises(
    user_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Lista todos os exercicios atribuidos a um avaliador"""
    
    user = db.query(UserTenant).filter(UserTenant.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    
    assignments = db.query(ExerciseEvaluator).filter(
        ExerciseEvaluator.evaluator_user_id == user_id
    ).all()
    
    exercises_list = []
    
    for assignment in assignments:
        exercise = db.query(Exercise).filter(Exercise.id == assignment.exercise_id).first()
        if exercise:
            exercises_list.append(ExerciseEvaluatorOut(
                id=assignment.id,
                exercise_id=assignment.exercise_id,
                evaluator_user_id=assignment.evaluator_user_id,
                is_primary=assignment.is_primary,
                evaluator_name=user.nome,
                evaluator_email=user.email,
                exercise_name=exercise.name,
                created_at=assignment.created_at
            ))
    
    return EvaluatorWithExercises(
        user_id=user_id,
        user_name=user.nome,
        user_email=user.email,
        exercises=exercises_list,
        total_exercises=len(exercises_list)
    )


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_evaluator_from_exercise(
    assignment_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Remove vinculacao de um avaliador com um exercicio"""
    
    assignment = db.query(ExerciseEvaluator).filter(ExerciseEvaluator.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Vinculacao nao encontrada")
    
    try:
        db.delete(assignment)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao remover vinculacao: {e}")


@router.patch("/{assignment_id}/primary", response_model=ExerciseEvaluatorOut)
def set_primary_evaluator(
    assignment_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Define um avaliador como primario para um exercicio"""
    
    assignment = db.query(ExerciseEvaluator).filter(ExerciseEvaluator.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Vinculacao nao encontrada")
    
    # Remove primario anterior do mesmo exercicio
    db.query(ExerciseEvaluator).filter(
        and_(
            ExerciseEvaluator.exercise_id == assignment.exercise_id,
            ExerciseEvaluator.is_primary == True,
            ExerciseEvaluator.id != assignment_id
        )
    ).update({"is_primary": False})
    
    # Define novo primario
    assignment.is_primary = True
    
    try:
        db.commit()
        db.refresh(assignment)
        
        # Adiciona nomes
        user = db.query(UserTenant).filter(UserTenant.id == assignment.evaluator_user_id).first()
        exercise = db.query(Exercise).filter(Exercise.id == assignment.exercise_id).first()
        
        if user:
            assignment.evaluator_name = user.nome
            assignment.evaluator_email = user.email
        if exercise:
            assignment.exercise_name = exercise.name
        
        return assignment
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao definir avaliador primario: {e}")
