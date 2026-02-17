# backend/app/schemas/event_schema.py

from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import Optional

# Base para leitura/resposta
class EventBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=255, description="Nome do evento/concurso")
    date_start: date = Field(..., description="Data de início do evento")
    date_end: date = Field(..., description="Data de término do evento")
    location: str = Field(..., max_length=255, description="Local do evento")
    is_active: bool = Field(default=True, description="Se o evento está ativo")
    
    model_config = ConfigDict(from_attributes=True)

# Schema de criação
class EventCreate(EventBase):
    """Schema para criação de novo evento"""
    pass

# Schema de atualização (todos os campos opcionais)
class EventUpdate(BaseModel):
    """Schema para atualização de evento - todos os campos são opcionais"""
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    location: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    
    model_config = ConfigDict(from_attributes=True)

# Schema de saída (inclui o ID e metadados)
class EventOut(EventBase):
    """Schema de resposta - inclui ID e timestamps"""
    id: int
    
    # Campos calculados/relacionados (opcional)
    total_candidates: Optional[int] = Field(default=0, description="Total de candidatos inscritos")
    total_exercises: Optional[int] = Field(default=0, description="Total de exercícios cadastrados")
    
    model_config = ConfigDict(from_attributes=True)

# Schema para listagem com paginação
class EventList(BaseModel):
    """Schema para resposta de lista paginada de eventos"""
    items: list[EventOut]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)