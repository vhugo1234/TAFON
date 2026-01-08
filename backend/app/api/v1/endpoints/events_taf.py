# backend/app/api/v1/endpoints/events_taf.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func, or_

# 1. Dependência de Multi-Tenancy (Obriga a sessão a ser isolada)
from app.api.deps_tenant import get_tenant_db_session 

# 2. Modelos e Schemas
from app.db.models.tenant import Event, Exercise, Candidate
from app.schemas.event_schema import EventCreate, EventUpdate, EventOut, EventList

router = APIRouter(tags=["TAF - Módulo 1: Eventos"])

# -----------------------------------------------------------
# Rotas CRUD de Eventos
# -----------------------------------------------------------

@router.post("/", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Cria um novo Concurso/Evento dentro do Schema do Cliente.
    
    Apenas Coordenador Geral pode criar eventos.
    """
    # Validação de datas
    if event_in.date_start > event_in.date_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data de início deve ser anterior à data de término."
        )
    
    db_event = Event(**event_in.model_dump())
    
    try:
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        
        # Adicionar contagens
        db_event.total_exercises = 0
        db_event.total_candidates = 0
        
        return db_event
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar evento: {e}")


@router.get("/", response_model=EventList)
def list_events(
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(10, ge=1, le=100, description="Itens por página"),
    is_active: Optional[bool] = Query(None, description="Filtrar por status ativo/inativo"),
    search: Optional[str] = Query(None, description="Buscar por nome ou local"),
    db: Session = Depends(get_tenant_db_session)
):
    """
    Lista todos os Concursos/Eventos do Cliente com paginação e filtros.
    """
    # Query base
    query = db.query(Event)
    
    # Filtros
    if is_active is not None:
        query = query.filter(Event.is_active == is_active)
    
    if search:
        query = query.filter(
            or_(
                Event.name.ilike(f"%{search}%"),
                Event.location.ilike(f"%{search}%")
            )
        )
    
    # Total de registros
    total = query.count()
    
    # Paginação
    events = query.order_by(Event.date_start.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    # Adicionar contagens para cada evento
    for event in events:
        event.total_exercises = db.query(func.count(Exercise.id)).filter(Exercise.event_id == event.id).scalar() or 0
        event.total_candidates = db.query(func.count(Candidate.id)).filter(Candidate.event_id == event.id).scalar() or 0
    
    return EventList(
        items=events,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Busca um Evento específico pelo ID com estatísticas."""
    try:
        event = db.query(Event).filter(Event.id == event_id).one()
        
        # Adicionar contagens
        event.total_exercises = db.query(func.count(Exercise.id)).filter(Exercise.event_id == event.id).scalar() or 0
        event.total_candidates = db.query(func.count(Candidate.id)).filter(Candidate.event_id == event.id).scalar() or 0
        
        return event
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int,
    event_in: EventUpdate,
    db: Session = Depends(get_tenant_db_session)
):
    """Atualiza dados de um Evento existente."""
    try:
        event = db.query(Event).filter(Event.id == event_id).one()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    update_data = event_in.model_dump(exclude_unset=True)
    
    # Validação de datas se ambas forem fornecidas
    if 'date_start' in update_data and 'date_end' in update_data:
        if update_data['date_start'] > update_data['date_end']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A data de início deve ser anterior à data de término."
            )
    
    for key, value in update_data.items():
        setattr(event, key, value)

    try:
        db.add(event)
        db.commit()
        db.refresh(event)
        
        # Adicionar contagens
        event.total_exercises = db.query(func.count(Exercise.id)).filter(Exercise.event_id == event.id).scalar() or 0
        event.total_candidates = db.query(func.count(Candidate.id)).filter(Candidate.event_id == event.id).scalar() or 0
        
        return event
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar evento: {e}")


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Deleta um Evento.
    
    ⚠️ ATENÇÃO: Isso também deletará todos os dados relacionados (exercícios, candidatos, resultados)
    devido ao CASCADE configurado no banco de dados.
    """
    try:
        event = db.query(Event).filter(Event.id == event_id).one()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    
    try:
        db.delete(event)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar evento: {e}")