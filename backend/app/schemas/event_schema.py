# backend/app/schemas/event_schema.py

from pydantic import BaseModel, Field, ConfigDict
from datetime import date
from typing import Optional, List

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
    # opcional: lista explícita de dias do evento (YYYY-MM-DD)
    event_dates: Optional[List[date]] = None
    # opcional: id do coordenador (UserTenant.id) para vincular ao evento
    coordinator_id: Optional[int] = None

# Schema de atualização (todos os campos opcionais)
class EventUpdate(BaseModel):
    """Schema para atualização de evento - todos os campos são opcionais"""
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    location: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    # opcional: lista explícita de dias para sobrescrever
    event_dates: Optional[List[date]] = None
    # opcional: id do coordenador para atualizar
    coordinator_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

# Schema de saída (inclui o ID e metadados)
class EventOut(EventBase):
    """Schema de resposta - inclui ID e timestamps"""
    id: int
    
    # Campos calculados/relacionados (opcional)
    total_candidates: Optional[int] = Field(default=0, description="Total de candidatos inscritos")
    total_exercises: Optional[int] = Field(default=0, description="Total de exercícios cadastrados")
    # Lista de dias explícitos do evento (quando usada)
    event_dates: Optional[List[date]] = None
    # Coordenador vinculado (opcional) — retorna o ID e nome se disponível
    coordinator_id: Optional[int] = None
    coordinator_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# Schema para listagem com paginaç��o
class EventList(BaseModel):
    """Schema para resposta de lista paginada de eventos"""
    items: list[EventOut]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)
