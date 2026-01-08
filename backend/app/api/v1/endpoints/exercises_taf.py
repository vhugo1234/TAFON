# backend/app/api/v1/endpoints/exercises_taf.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func

# 1. Dependência de Multi-Tenancy
from app.api.deps_tenant import get_tenant_db_session 

# 2. Modelos e Schemas
from app.db.models.tenant import Event, Exercise, PassCriteria
from app.schemas.exercise_schema import (
    ExerciseCreate, ExerciseUpdate, ExerciseOut, ExerciseWithCriteria,
    PassCriteriaCreate, PassCriteriaUpdate, PassCriteriaOut
)

router = APIRouter(tags=["TAF - Módulo 2: Exercícios"])

# =============================================================================
# ROTAS DE EXERCÍCIOS
# =============================================================================

@router.post("/", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
def create_exercise(
    exercise_in: ExerciseCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Cria um novo Exercício vinculado a um Evento.
    Usa fallback explícito para execution_mode/measurement_type quando não enviados.
    """
    # usa apenas campos enviados pelo cliente
    data = exercise_in.model_dump(exclude_unset=True)

    # garante que event_id esteja presente
    event_id = data.get("event_id") or getattr(exercise_in, "event_id", None)
    if event_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="event_id é obrigatório.")

    # verifica se o evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado.")

    # normaliza valores (se enviados)
    if "execution_mode" in data and isinstance(data["execution_mode"], str):
        data["execution_mode"] = data["execution_mode"].strip().lower()

    if "measurement_type" in data and isinstance(data["measurement_type"], str):
        data["measurement_type"] = data["measurement_type"].strip().lower()

    # ----------------------------
    # Fallback explícito (INSERIR AQUI)
    # ----------------------------
    execution_mode = data.get("execution_mode")
    measurement_type = data.get("measurement_type")

    # Se não vier execution_mode, aplicamos fallback explícito
    if not execution_mode:
        # exemplo: fallback simples para 'individual'
        execution_mode = "individual"

    # Se não vier measurement_type, tentamos inferir pela unidade (unit_of_measure)
    if not measurement_type:
        uom = (data.get("unit_of_measure") or "")
        if isinstance(uom, str) and uom.strip():
            uom_l = uom.strip().lower()
            # heurísticas comuns
            if uom_l in ("ms", "s", "sec", "seg"):
                measurement_type = "time"
            elif uom_l in ("m", "meter", "meters", "metro", "metros", "km"):
                measurement_type = "distance"
            elif uom_l in ("rep", "reps", "repetition", "repetitions", "x"):
                measurement_type = "repetitions"
            else:
                measurement_type = "repetitions"  # fallback neutro
        else:
            # sem unidade informada, usar fallback neutro
            measurement_type = "repetitions"

    # normaliza novamente (por garantia)
    if isinstance(execution_mode, str):
        execution_mode = execution_mode.strip().lower()
    if isinstance(measurement_type, str):
        measurement_type = measurement_type.strip().lower()

    # validação dos valores (ajuste conjuntos conforme o domínio)
    allowed_execution_modes = {"individual", "collective", "team"}
    allowed_measurement_types = {"time", "distance", "repetitions"}

    if execution_mode not in allowed_execution_modes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"execution_mode inválido. Valores válidos: {sorted(allowed_execution_modes)}")

    if measurement_type not in allowed_measurement_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"measurement_type inválido. Valores válidos: {sorted(allowed_measurement_types)}")
    # ---------------------------- end fallback
    # Força event_id e os campos validados no objeto final
    data["event_id"] = event_id
    data["execution_mode"] = execution_mode
    data["measurement_type"] = measurement_type

    db_exercise = Exercise(**data)

    try:
        db.add(db_exercise)
        db.commit()
        db.refresh(db_exercise)

        total = db.query(func.count(PassCriteria.id)).filter(
            PassCriteria.exercise_id == db_exercise.id
        ).scalar() or 0
        setattr(db_exercise, "total_criteria", total)

        return db_exercise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erro ao criar exercício: {e}")


@router.get("/by-event/{event_id}", response_model=List[ExerciseOut])
def list_exercises_by_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Lista todos os Exercícios de um Evento específico."""
    # Verifica se o evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado."
        )
    
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    
    # Adiciona contador de critérios para cada exercício
    for exercise in exercises:
        exercise.total_criteria = db.query(func.count(PassCriteria.id)).filter(
            PassCriteria.exercise_id == exercise.id
        ).scalar() or 0
    
    return exercises


@router.get("/{exercise_id}", response_model=ExerciseWithCriteria)
def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Busca um Exercicio especifico com seus criterios de aprovacao."""
    try:
        exercise = db.query(Exercise).filter(Exercise.id == exercise_id).one()
        
        # Busca os criterios
        criteria = db.query(PassCriteria).filter(
            PassCriteria.exercise_id == exercise_id
        ).all()
        
        # Cria resposta com criterios - INCLUINDO OS NOVOS CAMPOS
        exercise_dict = {
            'id': exercise.id,
            'name': exercise.name,
            'unit_of_measure': exercise.unit_of_measure,
            'max_attempts': exercise.max_attempts,
            'execution_mode': exercise.execution_mode,  # ADICIONADO
            'measurement_type': exercise.measurement_type,  # ADICIONADO
            'event_id': exercise.event_id,
            'total_criteria': len(criteria),
            'criteria': criteria
        }
        
        return exercise_dict
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercicio nao encontrado."
        )


@router.patch("/{exercise_id}", response_model=ExerciseOut)
def update_exercise(
    exercise_id: int,
    exercise_in: ExerciseUpdate,
    db: Session = Depends(get_tenant_db_session)
):
    """Atualiza dados de um Exercício existente."""
    try:
        exercise = db.query(Exercise).filter(Exercise.id == exercise_id).one()
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercício não encontrado."
        )

    update_data = exercise_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(exercise, key, value)

    try:
        db.add(exercise)
        db.commit()
        db.refresh(exercise)
        
        # Adiciona contador de critérios
        exercise.total_criteria = db.query(func.count(PassCriteria.id)).filter(
            PassCriteria.exercise_id == exercise.id
        ).scalar() or 0
        
        return exercise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar exercício: {e}"
        )


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(
    exercise_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Deleta um Exercício.
    
    ⚠️ ATENÇÃO: Isso também deletará todos os critérios e resultados relacionados
    devido ao CASCADE configurado no banco de dados.
    """
    try:
        exercise = db.query(Exercise).filter(Exercise.id == exercise_id).one()
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercício não encontrado."
        )
    
    try:
        db.delete(exercise)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar exercício: {e}"
        )


# =============================================================================
# ROTAS DE CRITÉRIOS DE APROVAÇÃO
# =============================================================================

@router.post("/{exercise_id}/criteria", response_model=PassCriteriaOut, status_code=status.HTTP_201_CREATED)
def create_pass_criteria(
    exercise_id: int,
    criteria_in: PassCriteriaCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """Cria um novo Critério de Aprovação para um Exercício."""
    # Verifica se o exercício existe
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercício não encontrado."
        )
    
    # Força o exercise_id do path
    criteria_data = criteria_in.model_dump()
    criteria_data['exercise_id'] = exercise_id
    
    db_criteria = PassCriteria(**criteria_data)
    
    try:
        db.add(db_criteria)
        db.commit()
        db.refresh(db_criteria)
        return db_criteria
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar critério: {e}"
        )


@router.get("/{exercise_id}/criteria", response_model=List[PassCriteriaOut])
def list_criteria_by_exercise(
    exercise_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Lista todos os Critérios de Aprovação de um Exercício."""
    # Verifica se o exercício existe
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercício não encontrado."
        )
    
    criteria = db.query(PassCriteria).filter(
        PassCriteria.exercise_id == exercise_id
    ).all()
    
    return criteria


@router.patch("/criteria/{criteria_id}", response_model=PassCriteriaOut)
def update_pass_criteria(
    criteria_id: int,
    criteria_in: PassCriteriaUpdate,
    db: Session = Depends(get_tenant_db_session)
):
    """Atualiza um Critério de Aprovação existente."""
    try:
        criteria = db.query(PassCriteria).filter(PassCriteria.id == criteria_id).one()
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Critério não encontrado."
        )

    update_data = criteria_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(criteria, key, value)

    try:
        db.add(criteria)
        db.commit()
        db.refresh(criteria)
        return criteria
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar critério: {e}"
        )


@router.delete("/criteria/{criteria_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pass_criteria(
    criteria_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Deleta um Critério de Aprovação."""
    try:
        criteria = db.query(PassCriteria).filter(PassCriteria.id == criteria_id).one()
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Critério não encontrado."
        )
    
    try:
        db.delete(criteria)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar critério: {e}"
        )