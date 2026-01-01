# backend/app/api/v1/endpoints/events_taf.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

# 1. Dependência de Multi-Tenancy (Obriga a sessão a ser isolada)
from app.api.deps_tenant import get_tenant_db_session 

# 2. Modelos e Schemas
from app.db.models.tenant import Event  # Seu modelo de Evento (tenant.py)
from app.schemas.event_schema import EventCreate, EventUpdate, EventOut

router = APIRouter(tags=["TAF - Módulo 1: Eventos"])

# -----------------------------------------------------------
# Rotas CRUD de Eventos
# -----------------------------------------------------------

@router.post("/", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_tenant_db_session) # <<< USA A DEPENDÊNCIA ISOLADA
):
    """Cria um novo Concurso/Evento dentro do Schema do Cliente."""
    db_event = Event(**event_in.model_dump())
    
    # ⚠️ TODO: Adicionar validação de permissão (ex: apenas Coordenador Geral)
    
    try:
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar evento: {e}")


@router.get("/", response_model=List[EventOut])
def list_events(
    db: Session = Depends(get_tenant_db_session) # <<< USA A DEPENDÊNCIA ISOLADA
):
    """Lista todos os Concursos/Eventos do Cliente."""
    events = db.query(Event).order_by(Event.date_start.desc()).all()
    return events


@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session) # <<< USA A DEPENDÊNCIA ISOLADA
):
    """Busca um Evento específico pelo ID."""
    try:
        event = db.query(Event).filter(Event.id == event_id).one()
        return event
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int,
    event_in: EventUpdate,
    db: Session = Depends(get_tenant_db_session) # <<< USA A DEPENDÊNCIA ISOLADA
):
    """Atualiza dados de um Evento existente."""
    try:
        event = db.query(Event).filter(Event.id == event_id).one()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    update_data = event_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)

    try:
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar evento: {e}")