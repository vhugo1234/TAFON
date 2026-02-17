# -*- coding: utf-8 -*-
# backend/app/schemas/result_schema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Union
from datetime import datetime

# =============================================================================
# SCHEMAS DE RESULTADOS INDIVIDUAIS
# =============================================================================

class CandidateResult(BaseModel):
    """Resultado consolidado de um candidato"""
    candidate_id: int
    candidate_name: str
    registration_number: str
    cpf: str
    gender: str
    batch_name: Optional[str] = None

    # novos campos opcionais para turma/agenda
    batch_number: Optional[Union[int, str]] = None
    start_time: Optional[str] = None  # formato esperado: "HH:MM" ou "HH:MM:SS"
    start_date: Optional[str] = None  # formato esperado: "YYYY-MM-DD"
    
    # Resultados por exercicio
    exercises_results: List['ExerciseResult']
    
    # Status geral
    total_exercises: int
    completed_exercises: int
    approved_exercises: int
    failed_exercises: int
    overall_status: str  # "approved", "failed", "in_progress"
    
    model_config = ConfigDict(from_attributes=True)


class ExerciseResult(BaseModel):
    """Resultado de um exercicio especifico"""
    exercise_id: int
    exercise_name: str
    unit_of_measure: str
    
    # Tentativas
    attempts: List['AttemptResult']
    best_attempt: Optional['AttemptResult'] = None
    
    # Status
    is_completed: bool
    is_approved: Optional[bool] = None
    
    # Criterio
    criteria_min_value: Optional[float] = None
    criteria_max_time: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class AttemptResult(BaseModel):
    """Resultado de uma tentativa"""
    attempt_number: int
    measured_value: float
    is_valid: bool
    is_approved: Optional[bool] = None
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SCHEMAS DE RELATORIOS CONSOLIDADOS
# =============================================================================

class EventResultsSummary(BaseModel):
    """Resumo geral dos resultados de um evento"""
    event_id: int
    event_name: str
    event_date: str
    location: str
    
    # Totais
    total_candidates: int
    total_exercises: int
    
    # Status dos candidatos
    candidates_approved: int
    candidates_failed: int
    candidates_in_progress: int
    
    # Taxas
    approval_rate: float
    completion_rate: float
    
    # Por exercicio
    exercises_summary: List['ExerciseSummary']
    
    model_config = ConfigDict(from_attributes=True)


class ExerciseSummary(BaseModel):
    """Resumo de um exercicio"""
    exercise_id: int
    exercise_name: str
    unit_of_measure: str
    
    # Estatisticas
    total_candidates: int
    candidates_completed: int
    candidates_approved: int
    candidates_failed: int
    
    # Valores
    average_value: Optional[float] = None
    best_value: Optional[float] = None
    worst_value: Optional[float] = None
    
    # Taxa de aprovacao
    approval_rate: float
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SCHEMAS DE EXPORTACAO
# =============================================================================

class ExportFormat(BaseModel):
    """Configuracao de exportacao"""
    format: str = Field(..., pattern="^(pdf|excel|csv)$", description="Formato de exportacao")
    include_signatures: bool = Field(default=True, description="Incluir assinaturas nos PDFs")
    include_photos: bool = Field(default=False, description="Incluir fotos dos candidatos")
    group_by: Optional[str] = Field(None, description="Agrupar por turma, sexo, etc")


class PDFGenerationRequest(BaseModel):
    """Request para geracao de PDF individual"""
    candidate_id: int
    event_id: int
    include_signature: bool = Field(default=True)
    signature_data: Optional[str] = Field(None, description="Base64 da assinatura")
    coordinator_name: Optional[str] = Field(None, description="Nome do coordenador")


class PDFGenerationResponse(BaseModel):
    """Response da geracao de PDF"""
    success: bool
    pdf_url: Optional[str] = None
    error: Optional[str] = None
    file_size_kb: Optional[float] = None


class BulkPDFGenerationRequest(BaseModel):
    """Request para geracao de PDFs em lote"""
    event_id: int
    candidate_ids: Optional[List[int]] = Field(None, description="IDs especificos ou None para todos")
    include_signatures: bool = Field(default=True)
    signature_data: Optional[str] = None
    coordinator_name: Optional[str] = None


class BulkPDFGenerationResponse(BaseModel):
    """Response da geracao em lote"""
    total_requested: int
    total_generated: int
    total_failed: int
    zip_file_url: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# SCHEMAS DE ASSINATURA DIGITAL
# =============================================================================

class SignatureCreate(BaseModel):
    """Criar assinatura"""
    event_id: int
    signature_data: str = Field(..., description="Base64 da imagem da assinatura")
    coordinator_name: str
    coordinator_role: str = Field(default="Coordenador de Educacao Fisica")


class SignatureOut(BaseModel):
    """Assinatura salva"""
    id: int
    event_id: int
    signature_url: str
    coordinator_name: str
    coordinator_role: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SCHEMAS DE FILTROS
# =============================================================================

class ResultsFilter(BaseModel):
    """Filtros para busca de resultados"""
    event_id: int
    gender: Optional[str] = Field(None, pattern="^[MF]$")
    batch_name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(approved|failed|in_progress)$")
    exercise_id: Optional[int] = None
    search: Optional[str] = Field(None, description="Buscar por nome ou inscricao")
