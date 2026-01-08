# -*- coding: utf-8 -*-
# backend/app/schemas/candidate_schema.py

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime

# =============================================================================
# SCHEMAS DE CANDIDATOS
# =============================================================================

class CandidateBase(BaseModel):
    """Base para candidatos do TAF"""
    full_name: str = Field(..., min_length=3, max_length=255, description="Nome completo do candidato")
    cpf: str = Field(..., min_length=11, max_length=11, pattern="^[0-9]{11}$", description="CPF (apenas números)")
    registration_number: str = Field(..., max_length=50, description="Número de inscrição")
    gender: str = Field(..., pattern="^[MF]$", description="Sexo (M ou F)")
    batch_name: Optional[str] = Field(None, max_length=50, description="Nome da turma/bateria")
    batch_number: Optional[int] = Field(None, description="Número do candidato dentro da turma (001, 002, 003...)")
    start_time: Optional[str] = Field(None, max_length=5, pattern="^[0-9]{1,2}:[0-9]{2}$", description="Horário da turma (HH:MM)")  # ✅ NOVO
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('cpf')
    @classmethod
    def validate_cpf_format(cls, v: str) -> str:
        """Valida formato do CPF (apenas números)"""
        if not v.isdigit():
            raise ValueError('CPF deve conter apenas números')
        if len(v) != 11:
            raise ValueError('CPF deve ter 11 dígitos')
        return v
    
    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: str) -> str:
        """Normaliza e valida sexo"""
        v = v.upper()
        if v not in ['M', 'F']:
            raise ValueError('Sexo deve ser M (Masculino) ou F (Feminino)')
        return v


class CandidateCreate(CandidateBase):
    """Schema para criação de candidato"""
    event_id: int = Field(..., description="ID do evento ao qual o candidato pertence")


class CandidateUpdate(BaseModel):
    """Schema para atualização de candidato - campos opcionais"""
    full_name: Optional[str] = Field(None, min_length=3, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=50)
    gender: Optional[str] = Field(None, pattern="^[MF]$")
    batch_name: Optional[str] = Field(None, max_length=50)
    
    model_config = ConfigDict(from_attributes=True)


class CandidateOut(CandidateBase):
    """Schema de resposta de candidato"""
    id: int
    event_id: int
    created_at: Optional[datetime] = None
    
    # Campos calculados
    has_results: Optional[bool] = Field(default=False, description="Se o candidato já tem resultados lançados")
    
    model_config = ConfigDict(from_attributes=True)


class CandidateList(BaseModel):
    """Lista paginada de candidatos"""
    items: List[CandidateOut]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SCHEMAS DE UPLOAD/IMPORTAÇÃO
# =============================================================================

class CandidateImportRow(BaseModel):
    """Schema para cada linha do CSV de importação"""
    full_name: str
    cpf: str
    registration_number: str
    gender: str
    batch_name: Optional[str] = None


class ImportValidationError(BaseModel):
    """Erro de validação em uma linha"""
    row_number: int
    field: str
    error: str


class ImportPreview(BaseModel):
    """Preview dos dados antes de importar"""
    total_rows: int
    valid_rows: int
    invalid_rows: int
    sample_data: List[CandidateImportRow]
    errors: List[ImportValidationError]


class ImportResult(BaseModel):
    """Resultado da importação"""
    total_rows: int
    rows_imported: int
    rows_failed: int
    rows_skipped: int  # Duplicados
    errors: List[ImportValidationError]
    success: bool
    message: str


class BulkCandidateCreate(BaseModel):
    """Schema para criação em lote"""
    event_id: int
    candidates: List[CandidateImportRow]
    skip_duplicates: bool = Field(default=True, description="Pular CPFs duplicados")
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SCHEMAS DE AGRUPAMENTO EM TURMAS
# =============================================================================

class GroupingConfig(BaseModel):
    """Configuração para agrupamento em turmas"""
    event_id: int
    group_size: int = Field(..., ge=1, le=100, description="Tamanho máximo da turma")
    separate_by_gender: bool = Field(default=False, description="Separar turmas por sexo")
    
    # Novas opções avançadas
    gender_priority: Optional[str] = Field(
        default=None, 
        pattern="^(F|M|mixed)$",
        description="Ordem de prioridade: F (Feminino primeiro), M (Masculino primeiro), mixed (Misto)"
    )
    sort_by_registration: bool = Field(
        default=True, 
        description="Ordenar candidatos por número de inscrição"
    )
    registration_order: str = Field(
        default="asc",
        pattern="^(asc|desc)$",
        description="Ordem de inscrição: asc (crescente) ou desc (decrescente)"
    )
    distribution_mode: str = Field(
        default="balanced",
        pattern="^(balanced|sequential)$",
        description="Modo de distribuição: balanced (balanceada) ou sequential (sequencial)"
    )
    allow_partial_groups: bool = Field(
        default=True,
        description="Permitir turmas menores que o tamanho definido"
    )
    
    start_time: Optional[str] = Field(None, description="Horário de início (HH:MM)")
    interval_minutes: Optional[int] = Field(None, ge=0, description="Intervalo entre turmas em minutos")


class TurmaInfo(BaseModel):
    """Informações de uma turma gerada"""
    name: str
    start_time: Optional[str] = None
    candidates: List[CandidateOut]
    total_candidates: int
    gender_distribution: dict  # {"M": 10, "F": 8}


class GroupingResult(BaseModel):
    """Resultado do agrupamento"""
    event_id: int
    total_candidates: int
    total_groups: int
    groups: List[TurmaInfo]
    config: GroupingConfig