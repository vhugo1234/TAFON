# -*- coding: utf-8 -*-
# backend/app/schemas/candidate_schema.py

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Dict, Union
from datetime import datetime, date

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
    start_time: Optional[str] = Field(None, max_length=5, pattern="^[0-9]{1,2}:[0-9]{2}$", description="Horário da turma (HH:MM)")
    start_date: Optional[date] = Field(None, description="Data da turma (YYYY-MM-DD)")
    
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
    """Configuração para agrupamento em turmas (aceita payload do frontend)."""
    # Primary identifier
    event_id: int

    # batch_size é o nome usado no frontend; mantemos compatibilidade com 'group_size'
    batch_size: int = Field(..., ge=1, le=1000, description="Tamanho máximo da turma")
    group_size: Optional[int] = Field(None, description="Alias legacy para batch_size (será mapeado automaticamente)")

    # Separação / ordenação / distribuição
    separate_by_gender: bool = Field(default=False, description="Separar turmas por sexo")
    gender_priority: Optional[str] = Field(default=None, pattern="^(F|M|mixed)$", description="Prioridade de gênero")
    sort_by_registration: bool = Field(default=True, description="Ordenar por inscrição")
    registration_order: str = Field(default="asc", pattern="^(asc|desc)$", description="Ordem de inscrição")
    distribution_mode: str = Field(default="balanced", pattern="^(balanced|sequential)$", description="Modo de distribuição")
    allow_partial_groups: bool = Field(default=True, description="Permitir turmas incompletas")

    # Scheduling / time slots (opções avançadas)
    slot_duration: Optional[int] = Field(None, description="Duração por candidato (minutos)")
    interval_between_batches: Optional[int] = Field(None, description="Intervalo entre turmas (minutos)")
    morning_start: Optional[str] = Field(None, pattern="^[0-9]{1,2}:[0-9]{2}$", description="Horario inicio manha (HH:MM)")
    morning_end_limit: Optional[str] = Field(None, pattern="^[0-9]{1,2}:[0-9]{2}$", description="Horario limite da manha (HH:MM)")
    afternoon_start_min: Optional[str] = Field(None, pattern="^[0-9]{1,2}:[0-9]{2}$", description="Horario inicio tarde (HH:MM)")
    start_date: Optional[date] = Field(None, description="Data inicial (YYYY-MM-DD)")
    days_count: Optional[int] = Field(None, ge=1, description="Numero de dias a distribuir")
    # Permitir lista explícita de dias (frontend envia 'days' quando há event_dates)
    days: Optional[List[date]] = Field(None, description="Lista explícita de dias (YYYY-MM-DD)")

    # Naming / presentation
    ordering: Optional[str] = Field(default="registration_number", description="Campo para ordenacao (registration_number|full_name)")
    batch_name_with_time: bool = Field(default=True, description="Incluir horario no nome da turma")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='before')
    def normalize_input(cls, values):
        """
        Aceita payloads que venham com 'group_size' (legacy) e mapeia para 'batch_size'.
        Também aceita 'slotDuration' camelCase if present (very defensive).
        """
        if not isinstance(values, dict):
            return values
        # legacy alias
        if 'group_size' in values and 'batch_size' not in values:
            values['batch_size'] = values.pop('group_size')
        # camelCase fallback keys (se por acaso o frontend enviar assim)
        if 'slotDuration' in values and 'slot_duration' not in values:
            values['slot_duration'] = values.pop('slotDuration')
        if 'intervalBetweenBatches' in values and 'interval_between_batches' not in values:
            values['interval_between_batches'] = values.pop('intervalBetweenBatches')
        if 'batchNameWithTime' in values and 'batch_name_with_time' not in values:
            values['batch_name_with_time'] = values.pop('batchNameWithTime')
        # if days provided as comma-separated string -> try to split (defensive)
        if 'days' in values and values.get('days') and isinstance(values.get('days'), str):
            values['days'] = [d.strip() for d in values['days'].split(',') if d.strip()]
        return values


class TurmaInfo(BaseModel):
    """Informações de uma turma gerada"""
    name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    # aceita string ISO (YYYY-MM-DD) ou date; será normalizado pelo validator abaixo
    date: Optional[Union[date, str]] = None
    candidates: List[CandidateOut]
    total_candidates: int
    gender_distribution: Dict[str, int]  # {"M": 10, "F": 8}

    model_config = ConfigDict(from_attributes=True)

    @field_validator('date', mode='before')
    @classmethod
    def parse_date(cls, v):
        """
        Aceita:
         - None -> retorna None
         - date -> retorna date
         - string 'YYYY-MM-DD' (ou ISO) -> converte para date
         - string vazia -> None
        """
        if v is None or v == '':
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s == '':
                return None
            # tenta ISO first (fromisoformat aceita 'YYYY-MM-DD')
            try:
                return datetime.fromisoformat(s).date()
            except Exception:
                try:
                    return datetime.strptime(s, "%Y-%m-%d").date()
                except Exception:
                    raise ValueError("date must be in YYYY-MM-DD (ISO) format")
        return v


class GroupingResult(BaseModel):
    """Resultado do agrupamento"""
    event_id: int
    total_candidates: int
    total_groups: int
    groups: List[TurmaInfo]
    config: GroupingConfig

    model_config = ConfigDict(from_attributes=True)