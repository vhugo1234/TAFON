# backend/app/schemas/event_schema.py

from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

# Base para leitura/resposta
class EventBase(BaseModel):
    name: str = Field(..., max_length=255)
    date_start: date
    date_end: date
    location: str = Field(..., max_length=255)
    is_active: bool = Field(default=True)

# Schema de criação
class EventCreate(EventBase):
    pass

# Schema de atualização (todos os campos opcionais)
class EventUpdate(EventBase):
    name: Optional[str] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None

# Schema de saída (inclui o ID e data de criação se necessário)
class EventOut(EventBase):
    id: int
    # created_at: datetime # Adicione se seu modelo tiver o campo created_at
    
    class Config:
        from_attributes = True