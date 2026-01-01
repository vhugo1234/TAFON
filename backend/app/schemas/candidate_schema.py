# backend/app/schemas/candidate_schema.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CandidateBase(BaseModel):
    event_id: int = Field(..., description="ID do Evento TAF")
    full_name: str
    cpf: str = Field(..., min_length=11, max_length=11)
    registration_number: str = Field(..., description="Número de Inscrição no Concurso/Seleção")
    gender: str = Field(..., max_length=1, description="Gênero: 'M' ou 'F'")
    batch_name: Optional[str] = Field(None, description="Turma ou Bateria de Prova")

class CandidateCreate(CandidateBase):
    pass

class CandidateOut(CandidateBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Schema para a importação (se você for processar um arquivo)
class ImportResult(BaseModel):
    total_rows: int
    rows_imported: int
    rows_failed: int
    errors: List[str]