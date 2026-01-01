# backend/app/api/v1/endpoints/exercises_taf.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

# 1. Dependência de Multi-Tenancy
from app.api.deps_tenant import get_tenant_db_session 

# 2. Modelos e Schemas
from app.db.models.tenant import Event, Exercise, PassCriteria
from app.schemas.exercise_schema import ExerciseCreate, ExerciseUpdate, ExerciseOut, PassCriteriaCreate, PassCriteriaOut

router = APIRouter(tags=["TAF - Módulo 2: Exercícios e Regras"])

# -----------------------------------------------------------
# Funções CRUD Aninhado (Exercise e Criteria)
# -----------------------------------------------------------

@router.post("/", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
def create_exercise(
    exercise_in: ExerciseCreate,
    db: Session = Depends(get_tenant_db_session) # <<< USA A DEPENDÊNCIA ISOLADA
):
    """Cria um novo Exercício e seus Critérios de Aprovação."""
    
    # 1. Verifica se o Evento existe
    event = db.query(Event).filter(Event.id == exercise_in.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento (Event ID) não encontrado.")

    # 2. Extrai e remove os critérios para criar o Exercise principal
    criteria_data = exercise_in.criteria
    exercise_data = exercise_in.model_dump(exclude={"criteria"})

    db_exercise = Exercise(**exercise_data)
    
    try:
        db.add(db_exercise)
        db.flush() # flush para obter o ID do exercise antes de comitar

        # 3. Cria os critérios e associa ao Exercise
        for criterion in criteria_data:
            db_criterion = PassCriteria(exercise_id=db_exercise.id, **criterion.model_dump())
            db.add(db_criterion)

        db.commit()
        db.refresh(db_exercise)
        
        # O refresh deve trazer os critérios associados.
        return db_exercise 
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar exercício e critérios: {e}")


@router.get("/by_event/{event_id}", response_model=List[ExerciseOut])
def list_exercises_by_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session) # <<< USA A DEPENDÊNCIA ISOLADA
):
    """Lista todos os Exercícios de um Evento específico."""
    events = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    if not events and not db.query(Event).filter(Event.id == event_id).first():
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
        
    return events


# ... Adicione endpoints para GET by ID, PATCH (atualização) e DELETE (remova criteria na deleção)
# A atualização (PATCH) será mais complexa, pois deve remover ou adicionar critérios.