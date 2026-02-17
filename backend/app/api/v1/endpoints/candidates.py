# -*- coding: utf-8 -*-
# backend/app/api/v1/endpoints/candidates.py

from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy import func, or_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
import logging
from datetime import datetime, date as _date
import unicodedata

from app.api.deps_tenant import get_tenant_db_session 
from app.db.models.tenant import Candidate, Event, ExecutionResult
from app.schemas.candidate_schema import (
    CandidateCreate, CandidateUpdate, CandidateOut, CandidateList,
    BulkCandidateCreate, ImportResult, ImportPreview, GroupingConfig, GroupingResult
)
from app.utils.csv_parser import parse_candidates_csv, generate_sample_csv
from app.utils.cpf_validator import validate_cpf
from app.utils.grouping_algorithm import group_candidates
from app.utils.batch_pdf_generator import generate_attendance_list_pdf, generate_batch_badges_pdf
from app.utils.grouping_algorithm import _build_global_slots, _normalize_config_for_algorithm
from fastapi.responses import PlainTextResponse, StreamingResponse
import io

router = APIRouter(tags=["TAF - Módulo 3: Candidatos"])

# =============================================================================
# ROTAS CRUD DE CANDIDATOS
# =============================================================================

@router.post("/", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(
    candidate_in: CandidateCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """Cria um novo Candidato vinculado a um Evento."""
    # Verifica se o evento existe
    event = db.query(Event).filter(Event.id == candidate_in.event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado."
        )
    
    # Valida CPF
    if not validate_cpf(candidate_in.cpf):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF inválido."
        )
    
    # Verifica duplicidade de CPF
    existing = db.query(Candidate).filter(
        Candidate.event_id == candidate_in.event_id,
        Candidate.cpf == candidate_in.cpf
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe um candidato com o CPF {candidate_in.cpf} neste evento."
        )
    
    # Cria o candidato
    db_candidate = Candidate(**candidate_in.model_dump())
    
    try:
        db.add(db_candidate)
        db.commit()
        db.refresh(db_candidate)
        
        # Adiciona flag se tem resultados
        db_candidate.has_results = False
        
        return db_candidate
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar candidato: {e}"
        )


@router.get("/by-event/{event_id}", response_model=CandidateList)
def list_candidates_by_event(
    event_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=2000),
    search: Optional[str] = Query(None, description="Buscar por nome, CPF ou inscrição"),
    gender: Optional[str] = Query(None, pattern="^[MF]$"),
    batch_name: Optional[str] = Query(None),
    db: Session = Depends(get_tenant_db_session)
):
    """Lista todos os Candidatos de um Evento com filtros e paginação."""
    # Verifica se o evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado."
        )
    
    # Query base
    query = db.query(Candidate).filter(Candidate.event_id == event_id)
    
    # Filtros
    if search:
        query = query.filter(
            or_(
                Candidate.full_name.ilike(f"%{search}%"),
                Candidate.cpf.ilike(f"%{search}%"),
                Candidate.registration_number.ilike(f"%{search}%")
            )
        )
    
    if gender:
        query = query.filter(Candidate.gender == gender)
    
    if batch_name:
        query = query.filter(Candidate.batch_name == batch_name)
    
    # Total
    total = query.count()
    
    # ✅ Ordenação alfabética por nome (com suporte a acentuação PT-BR)
    query = query.order_by(func.lower(Candidate.full_name))
    
    # Paginação
    candidates = query.offset((page - 1) * page_size).limit(page_size).all()
    
    # Adiciona flag de resultados
    for candidate in candidates:
        has_results = db.query(func.count(ExecutionResult.id)).filter(
            ExecutionResult.candidate_id == candidate.id
        ).scalar() > 0
        candidate.has_results = has_results
    
    return CandidateList(
        items=candidates,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Busca um Candidato específico pelo ID."""
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).one()
        
        # Adiciona flag de resultados
        has_results = db.query(func.count(ExecutionResult.id)).filter(
            ExecutionResult.candidate_id == candidate.id
        ).scalar() > 0
        candidate.has_results = has_results
        
        return candidate
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato não encontrado."
        )


@router.patch("/{candidate_id}", response_model=CandidateOut)
def update_candidate(
    candidate_id: int,
    candidate_in: CandidateUpdate,
    db: Session = Depends(get_tenant_db_session)
):
    """Atualiza dados de um Candidato existente."""
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).one()
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato não encontrado."
        )

    update_data = candidate_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(candidate, key, value)

    try:
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        # Adiciona flag de resultados
        has_results = db.query(func.count(ExecutionResult.id)).filter(
            ExecutionResult.candidate_id == candidate.id
        ).scalar() > 0
        candidate.has_results = has_results
        
        return candidate
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar candidato: {e}"
        )


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Deleta um Candidato.
    
    ⚠️ ATENÇÃO: Isso também deletará todos os resultados relacionados
    devido ao CASCADE configurado no banco de dados.
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).one()
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato não encontrado."
        )
    
    try:
        db.delete(candidate)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar candidato: {e}"
        )


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_candidates(
    candidate_ids: List[int],
    db: Session = Depends(get_tenant_db_session)
):
    """
    Deleta múltiplos candidatos de uma vez.
    
    ⚠️ ATENÇÃO: Isso também deletará todos os resultados relacionados
    devido ao CASCADE configurado no banco de dados.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not candidate_ids or len(candidate_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum candidato selecionado para exclusão."
        )
    
    logger.info(f"🗑️  Iniciando deleção em massa: {len(candidate_ids)} candidatos")
    
    deleted_count = 0
    failed_count = 0
    errors = []
    
    for candidate_id in candidate_ids:
        try:
            candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            if candidate:
                db.delete(candidate)
                deleted_count += 1
                logger.debug(f"✅ Candidato {candidate_id} deletado - {candidate.full_name}")
            else:
                failed_count += 1
                errors.append(f"Candidato ID {candidate_id} não encontrado")
                logger.warning(f"⚠️  Candidato {candidate_id} não encontrado")
        except Exception as e:
            failed_count += 1
            errors.append(f"Erro ao deletar candidato ID {candidate_id}: {str(e)}")
            logger.error(f"❌ Erro ao deletar candidato {candidate_id}: {e}")
    
    try:
        db.commit()
        message = f"Deleção concluída: {deleted_count} candidatos excluídos"
        if failed_count > 0:
            message += f", {failed_count} falhas"
        
        logger.info(f"✅ {message}")
        
        return {
            "message": message,
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "errors": errors
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro no commit da deleção em massa: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar exclusões no banco de dados: {e}"
        )


# =============================================================================
# ROTAS DE IMPORTAÇÃO CSV
# =============================================================================

@router.get("/sample-csv/download", response_class=PlainTextResponse)
def download_sample_csv():
    """Baixa um arquivo CSV de exemplo para importação."""
    return generate_sample_csv()


@router.post("/upload-preview", response_model=ImportPreview)
async def preview_csv_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_tenant_db_session)
):
    """
    Preview dos dados do CSV antes de importar.
    Retorna TODOS os candidatos válidos (não apenas amostra).
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas arquivos CSV são suportados."
        )
    
    valid_candidates, errors = await parse_candidates_csv(file)
    
    # Log para debug
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📊 Preview CSV: {len(valid_candidates)} candidatos válidos, {len(errors)} erros")
    
    # ✅ CORREÇÃO: retorna TODOS os candidatos válidos (não apenas 10)
    return ImportPreview(
        total_rows=len(valid_candidates) + len(errors),
        valid_rows=len(valid_candidates),
        invalid_rows=len(errors),
        sample_data=valid_candidates,  # TODOS os candidatos válidos
        errors=errors
    )


@router.post("/bulk-import", response_model=ImportResult)
async def bulk_import_candidates(
    bulk_data: BulkCandidateCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """Importa múltiplos candidatos de uma vez."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📥 Iniciando bulk-import: {len(bulk_data.candidates)} candidatos recebidos")
    
    # Verifica se o evento existe
    event = db.query(Event).filter(Event.id == bulk_data.event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado."
        )
    
    result = ImportResult(
        total_rows=len(bulk_data.candidates),
        rows_imported=0,
        rows_failed=0,
        rows_skipped=0,
        errors=[],
        success=False,
        message=""
    )

    # 1) Prepare payload: dedupe internas (mesmo CPF dentro do CSV) e build cleaned list
    cleaned: List[dict] = []
    seen_cpfs = set()
    for idx, candidate_data in enumerate(bulk_data.candidates, start=1):
        try:
            cpf_val = (candidate_data.cpf or "").strip()
            # Keep the original warning semantics for CPF validation
            cpf_valid = validate_cpf(cpf_val)
            if not cpf_valid:
                result.errors.append({
                    'row_number': idx,
                    'field': 'cpf',
                    'error': f'⚠️ AVISO: CPF {cpf_val} não passou na validação matemática. Importado mesmo assim.'
                })
                logger.warning(f"⚠️  Linha {idx}: CPF suspeito mas importado - {cpf_val}")
            # Skip empty CPFs right away (count as failed)
            if not cpf_val:
                result.rows_failed += 1
                result.errors.append({
                    'row_number': idx,
                    'field': 'cpf',
                    'error': 'cpf missing'
                })
                logger.warning(f"❌ Linha {idx}: CPF ausente - será ignorada")
                continue

            key = (cpf_val, bulk_data.event_id)
            if key in seen_cpfs:
                # duplicate inside the uploaded file
                result.rows_skipped += 1
                logger.info(f"⏭️  Linha {idx}: CPF duplicado no arquivo ignorado - {cpf_val}")
                continue
            seen_cpfs.add(key)

            # Build row dict matching Candidate columns
            row = {
                'event_id': bulk_data.event_id,
                'full_name': getattr(candidate_data, 'full_name', '') or '',
                'cpf': cpf_val,
                'registration_number': getattr(candidate_data, 'registration_number', '') or '',
                'gender': getattr(candidate_data, 'gender', '') or '',
                'batch_name': getattr(candidate_data, 'batch_name', None),
                'batch_number': getattr(candidate_data, 'batch_number', None),
                'start_time': getattr(candidate_data, 'start_time', None)
            }

            # Basic presence checks before add to cleaned (these are counted as failures)
            if not row['full_name']:
                result.rows_failed += 1
                result.errors.append({'row_number': idx, 'field': 'full_name', 'error': 'full_name missing'})
                logger.warning(f"❌ Linha {idx}: full_name missing")
                continue
            if not row['registration_number']:
                result.rows_failed += 1
                result.errors.append({'row_number': idx, 'field': 'registration_number', 'error': 'registration_number missing'})
                logger.warning(f"❌ Linha {idx}: registration_number missing")
                continue
            if row['gender'] not in ('M', 'F'):
                result.rows_failed += 1
                result.errors.append({'row_number': idx, 'field': 'gender', 'error': f"Invalid gender: '{row['gender']}'. Use 'M' or 'F'."})
                logger.warning(f"❌ Linha {idx}: gender invalid")
                continue

            cleaned.append(row)
        except Exception as e:
            result.rows_failed += 1
            result.errors.append({'row_number': idx, 'field': 'general', 'error': str(e)})
            logger.error(f"❌ Linha {idx}: Erro preparando linha: {e}")

    # If nothing to insert, return early
    if not cleaned:
        result.success = True
        result.message = "Nenhum candidato válido a importar."
        return result

    try:
        # Count existing candidates for the event before insert
        before_count = db.query(func.count(Candidate.id)).filter(Candidate.event_id == bulk_data.event_id).scalar()

        # Use PostgreSQL ON CONFLICT DO NOTHING to avoid UniqueViolation on (cpf,event_id)
        stmt = pg_insert(Candidate).values(cleaned)
        stmt = stmt.on_conflict_do_nothing(index_elements=['cpf', 'event_id'])
        db.execute(stmt)
        db.commit()

        # Count after to calculate inserted rows
        after_count = db.query(func.count(Candidate.id)).filter(Candidate.event_id == bulk_data.event_id).scalar()
        rows_inserted = max(0, (after_count or 0) - (before_count or 0))
        rows_attempted = len(cleaned)
        rows_skipped_conflicts = rows_attempted - rows_inserted

        result.rows_imported += rows_inserted
        result.rows_skipped += rows_skipped_conflicts  # these were ignored by DB
        result.success = True

        # Build message
        result.message = f"Importação concluída: {result.rows_imported} candidatos importados"
        if result.rows_skipped > 0:
            result.message += f", {result.rows_skipped} duplicados ignorados"
        if result.rows_failed > 0:
            result.message += f", {result.rows_failed} erros"
        warnings_count = len([e for e in result.errors if 'AVISO' in str(e.get('error', ''))])
        if warnings_count > 0:
            result.message += f", {warnings_count} CPFs com formato suspeito (importados mesmo assim)"
        result.message += "."

        logger.info(f"✅ {result.message}")
    except Exception as e:
        db.rollback()
        result.success = False
        result.message = f"Erro ao salvar no banco de dados: {e}"
        logger.error(f"❌ Erro no commit: {e}")

    return result


# =============================================================================
# ROTAS DE AGRUPAMENTO EM TURMAS
# =============================================================================

@router.post("/group", response_model=GroupingResult)
def group_candidates_into_turmas(
    config: GroupingConfig,
    db: Session = Depends(get_tenant_db_session)
):
    """Agrupa candidatos em turmas baseado nas configurações."""

    logger = logging.getLogger(__name__)

    # Converte o Pydantic config para um dict mutável (para mesclar event.dates se necessário)
    try:
        config_data = config.model_dump() if hasattr(config, "model_dump") else dict(config)
    except Exception:
        config_data = dict(config) if isinstance(config, dict) else {}

    # Se não houver especificação de dias no payload, tentar obter event_dates do evento no DB
    try:
        has_start = bool(config_data.get('start_date'))
        has_days_count = bool(config_data.get('days_count'))
        has_days_field = bool(config_data.get('days'))
        if not (has_start or has_days_count or has_days_field):
            event = db.query(Event).filter(Event.id == config.event_id).first()
            if event and getattr(event, "dates", None):
                event_dates = [ed.date.isoformat() for ed in event.dates]
                if event_dates:
                    config_data['days'] = event_dates
                    logger.info(f"Usando event.dates do evento {event.id}: {event_dates}")
    except Exception as e:
        logger.exception(f"Erro ao tentar carregar event_dates do evento {config.event_id}: {e}")

    # Reconstruir o Pydantic GroupingConfig a partir do dict final
    from app.schemas.candidate_schema import GroupingConfig as GroupingConfigSchema
    try:
        config_obj = GroupingConfigSchema.model_validate(config_data)
    except Exception as e:
        logger.exception(f"Configuração de agrupamento inválida após merge: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Configuração de agrupamento inválida: {e}"
        )

    # Garantir compatibilidade: group_size <- batch_size (legacy/frontend)
    try:
        if getattr(config_obj, "group_size", None) is None and getattr(config_obj, "batch_size", None) is not None:
            try:
                setattr(config_obj, "group_size", config_obj.batch_size)
            except Exception:
                data = config_obj.model_dump()
                data['group_size'] = data.get('batch_size')
                config_obj = GroupingConfigSchema.model_validate(data)
    except Exception as e:
        logger.exception(f"Erro ao normalizar group_size: {e}")

    # Normalizar aliases para start_time e interval_minutes esperados pelo algoritmo
    try:
        # determine start_time: possible sources
        start_candidates = [
            getattr(config_obj, 'start_time', None),
            getattr(config_obj, 'morning_start', None),
            getattr(config_obj, 'morningStart', None),
            getattr(config_obj, 'startDate', None),  # fallback but typically date
            getattr(config_obj, 'start_date', None)
        ]
        start_val = next((s for s in start_candidates if s), None)
        # determine interval_minutes: possible sources
        interval_candidates = [
            getattr(config_obj, 'interval_minutes', None),
            getattr(config_obj, 'interval_between_batches', None),
            getattr(config_obj, 'intervalMinutes', None),
            getattr(config_obj, 'interval_between_batches', None)
        ]
        interval_val = next((i for i in interval_candidates if i is not None), None)

        rebound_needed = False
        data = None

        if start_val and not getattr(config_obj, 'start_time', None):
            # try setattr first
            try:
                setattr(config_obj, 'start_time', start_val)
            except Exception:
                rebound_needed = True
                data = config_obj.model_dump()
                data['start_time'] = start_val

        if interval_val is not None and not getattr(config_obj, 'interval_minutes', None):
            # coerce to int if possible
            try:
                iv = int(interval_val)
            except Exception:
                iv = None
            if iv is None:
                # keep original (may be None) and let validation fail later with clear message
                pass
            else:
                try:
                    setattr(config_obj, 'interval_minutes', iv)
                except Exception:
                    if data is None:
                        data = config_obj.model_dump()
                    data['interval_minutes'] = iv
                    rebound_needed = True

        if rebound_needed and data is not None:
            config_obj = GroupingConfigSchema.model_validate(data)
    except Exception as e:
        logger.exception(f"Erro ao normalizar start_time/interval_minutes: {e}")

    # Validar que temos um group_size válido para evitar TypeError
    gs = getattr(config_obj, "group_size", None)
    if gs is None or (isinstance(gs, int) and gs <= 0):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tamanho da turma (group_size/batch_size) inválido ou ausente."
        )

    # Validar que interval_minutes e start_time quando usados são válidos (mensagem clara)
    # (algoritmo pode exigir ambos para agendamento por slot)
    # Não lançamos erro se o algoritmo tolera ausência, apenas normalizamos; porém,
    # se há um uso claro de agendamento (start_time presente) e interval faltando -> erro.
    if getattr(config_obj, 'start_time', None) and getattr(config_obj, 'interval_minutes', None) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quando start_time é fornecido, interval_minutes (interval_between_batches) também é necessário."
        )

    # Busca candidatos do evento — ordena de forma determinística conforme config
    query = db.query(Candidate).filter(Candidate.event_id == config_obj.event_id)

    # Detecta se a extensão unaccent está disponível no banco (evita erro se não existir)
    has_unaccent = False
    try:
        # consulta pg_extension é segura/rápida
        r = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'unaccent'")).fetchone()
        has_unaccent = bool(r)
    except Exception:
        has_unaccent = False

    # Ordenação baseada na configuração — usa unaccent quando disponível, senão fallback para lower()
    try:
        if getattr(config_obj, "sort_by_registration", True):
            # ordena por registration_number (respeita registration_order)
            reg_order = getattr(config_obj, "registration_order", "asc")
            if reg_order == "desc":
                query = query.order_by(Candidate.registration_number.desc())
            else:
                query = query.order_by(Candidate.registration_number.asc())
        else:
            ordering_field = getattr(config_obj, "ordering", None)
            if ordering_field == "full_name":
                if has_unaccent:
                    query = query.order_by(func.lower(func.unaccent(Candidate.full_name)))
                else:
                    query = query.order_by(func.lower(Candidate.full_name))
            else:
                if has_unaccent:
                    query = query.order_by(func.lower(func.unaccent(Candidate.full_name)))
                else:
                    query = query.order_by(func.lower(Candidate.full_name))
    except Exception:
        # fallback seguro: sem order_by se algo falhar
        pass

    candidates = query.all()
    if not candidates:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum candidato encontrado para este evento.")

    
    # ---------- Accent-insensitive ordering fallback em Python ----------
    def _strip_accents(s: str) -> str:
        if not s:
            return ""
        nfkd = unicodedata.normalize("NFKD", s)
        return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower().strip()

    try:
        # Ordena os objetos retornados pelo DB de forma insensível a acentos
        candidates.sort(key=lambda c: _strip_accents(getattr(c, "full_name", "") or ""))
        logger.info("Candidates sorted in Python with accent-insensitive key for grouping.")
    except Exception:
        logger.exception("Falha ao ordenar candidatos no backend (fallback ignorado).")
    # -------------------------------------------------------------------

    # Converte para estrutura que o algoritmo espera (ajuste conforme sua implementação)
    candidate_list = [
        CandidateOut(
            id=c.id,
            event_id=c.event_id,
            full_name=c.full_name,
            cpf=c.cpf,
            registration_number=c.registration_number,
            gender=c.gender,
            batch_name=c.batch_name
        )
        for c in candidates
    ]

    logger.info(f"Iniciando agrupamento para event_id={config_obj.event_id} com config: {config_obj}")

    # Executa o algoritmo de agrupamento
    groups = group_candidates(candidate_list, config_obj)

    debug_slots = []
    try:
        cfg_ns = _normalize_config_for_algorithm(config_obj)
        slots = _build_global_slots(cfg_ns)
        debug_slots = [(d.isoformat(), t) for d, t in slots]
        logger.info("DEBUG slots generated: %s", debug_slots)
    except Exception as _e:
        logger.exception("Erro ao gerar debug slots: %s", _e)

    # Retorna o mesmo payload mas com debug_slots para facilitar verificação no frontend
    return {
        "event_id": config_obj.event_id,
        "total_candidates": len(candidates),
        "total_groups": len(groups),
        "groups": groups,
        "config": config_obj,
        "debug_slots": debug_slots
    }


@router.post("/apply-grouping/{event_id}", status_code=status.HTTP_200_OK)
def apply_grouping_to_candidates(
    event_id: int,
    result: dict,  # receber JSON cru para evitar validação Pydantic estrita
    db: Session = Depends(get_tenant_db_session)
):
    """
    Aplica o agrupamento no banco, atualizando batch_name, batch_number, start_time e start_date.
    Recebe payload cru (dict) para ser tolerante a campos extras/formatos vindos do frontend.
    """
    import logging
    from datetime import datetime, date as _date
    from sqlalchemy import text
    logger = logging.getLogger(__name__)

    try:
        payload = dict(result or {})
        groups = payload.get("groups", []) or []
        total_groups = payload.get("total_groups", len(groups))
        total_candidates = payload.get("total_candidates", 0)

        # Log do search_path (ajuda em ambiente multi-tenant)
        try:
            sp = db.execute(text("SHOW search_path")).fetchone()
            logger.info("DB search_path for apply_grouping: %s", sp)
        except Exception:
            logger.debug("Não foi possível obter search_path")

        logger.info("Aplicando agrupamento event_id=%s: %d turmas, %d candidatos", event_id, total_groups, total_candidates)

        updated_count = 0
        ignored_count = 0

        for idx, group in enumerate(groups):
            # segurança: tratar group como dict
            if not isinstance(group, dict):
                logger.warning("Group[%s] não é dict, ignorando: %r", idx, group)
                continue

            gname = group.get("name")
            gstart = group.get("start_time")
            gdate_raw = group.get("date", None)

            # parse defensivo da data (aceita date object ou ISO string)
            parsed_date = None
            if gdate_raw is not None:
                try:
                    if isinstance(gdate_raw, _date):
                        parsed_date = gdate_raw
                    else:
                        parsed_date = datetime.fromisoformat(str(gdate_raw)).date()
                except Exception:
                    try:
                        parsed_date = datetime.strptime(str(gdate_raw), "%Y-%m-%d").date()
                    except Exception:
                        parsed_date = None

            candidates_list = group.get("candidates", []) or []
            logger.info(" Group[%d] name=%s start_time=%s date_raw=%s candidates=%d", idx, gname, gstart, gdate_raw, len(candidates_list))

            for cand_obj in candidates_list:
                # aceitar dict-like; extrair id com segurança
                cand_id = None
                if isinstance(cand_obj, dict):
                    cand_id = cand_obj.get("id")
                    bn = cand_obj.get("batch_number", None)
                else:
                    # fallback para objetos Pydantic/Out
                    cand_id = getattr(cand_obj, "id", None)
                    bn = getattr(cand_obj, "batch_number", None)

                if not cand_id:
                    ignored_count += 1
                    logger.warning("Candidato sem id no payload (ignorado): %r", cand_obj)
                    continue

                db_candidate = db.query(Candidate).filter(Candidate.id == cand_id).first()
                if not db_candidate:
                    ignored_count += 1
                    logger.warning("Candidato id=%s nao encontrado no DB (ignorado)", cand_id)
                    continue

                # Atualiza campos mínimos e confiáveis
                try:
                    db_candidate.batch_name = gname
                    try:
                        db_candidate.batch_number = int(bn) if (bn is not None and bn != "") else None
                    except Exception:
                        db_candidate.batch_number = None

                    # Atualiza start_time somente se for string no formato HH:MM plausível
                    if isinstance(gstart, str) and len(gstart) >= 3:
                        db_candidate.start_time = gstart

                    # Atualiza start_date somente se parse teve sucesso
                    if parsed_date:
                        db_candidate.start_date = parsed_date

                    db.add(db_candidate)
                    updated_count += 1
                except Exception as _e:
                    logger.exception("Erro atualizando candidato id=%s: %s", cand_id, _e)
                    # continua com os próximos candidatos

        # commit único ao final
        db.commit()
        logger.info("Agrupamento aplicado: %d candidatos atualizados, %d ignorados", updated_count, ignored_count)

        return {
            "message": f"Agrupamento aplicado com sucesso! {total_groups} turmas processadas.",
            "total_groups": total_groups,
            "total_candidates": total_candidates,
            "updated_candidates": updated_count,
            "ignored_candidates": ignored_count
        }
    except Exception as e:
        db.rollback()
        logger.exception("Erro ao aplicar agrupamento: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/batches/{event_id}", response_model=List[str])
def list_batches(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Lista todos os nomes de turmas de um evento."""
    # Verifica se o evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado."
        )
    
    # Busca turmas únicas
    batches = db.query(Candidate.batch_name).filter(
        Candidate.event_id == event_id,
        Candidate.batch_name.isnot(None)
    ).distinct().order_by(Candidate.batch_name).all()
    
    return [batch[0] for batch in batches]



@router.get("/batches/{event_id}/detailed", response_model=List[Dict[str, Any]])
def list_batches_detailed(
    event_id: int,
    db: Session = Depends(get_tenant_db_session),
    limit: int = Query(5000, description="Max candidates to scan (safety)")
):
    """
    Retorna grupos de turma com chave composta e membros (ids).
    Key: batch_name||batch_number||gender||start_date||start_time
    Label é legível (ex: "Turma 01 • #001 • Masculino • 17/01/2026 • 08:00 (N)").
    """
    try:
        candidates = db.query(Candidate).filter(Candidate.event_id == int(event_id)).limit(limit).all()
    except Exception as e:
        logger.exception("Erro ao consultar candidatos para event_id=%s: %s", event_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao buscar candidatos")

    if not candidates:
        return []

    groups: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        batch_name = (getattr(c, "batch_name", "") or "").strip() or "(sem turma)"
        batch_number = "" if getattr(c, "batch_number", None) in (None, "") else str(getattr(c, "batch_number"))
        gender = (getattr(c, "gender", "") or "").strip()
        start_date_raw = getattr(c, "start_date", None)
        start_date = start_date_raw.isoformat() if start_date_raw is not None else ""
        start_time = (getattr(c, "start_time", "") or "").strip()

        key = f"{batch_name}||{batch_number}||{gender}||{start_date}||{start_time}"

        if key not in groups:
            label_parts = [batch_name]
            if batch_number:
                label_parts.append(f"#{batch_number}")
            if gender:
                label_parts.append("Masculino" if gender.upper().startswith("M") else ("Feminino" if gender.upper().startswith("F") else gender))
            if start_date:
                try:
                    y, m, d = start_date.split("-")
                    label_parts.append(f"{d}/{m}/{y}")
                except Exception:
                    label_parts.append(start_date)
            if start_time:
                label_parts.append(start_time)
            label = " • ".join([p for p in label_parts if p])
            groups[key] = {"key": key, "label": label, "count": 0, "members": [], "start_date": start_date, "start_time": start_time}

        groups[key]["count"] += 1

        # Normaliza id do candidato (id / candidate_id / candidateId)
        candidate_id = None
        for attr in ("id", "candidate_id", "candidateId"):
            raw = getattr(c, attr, None)
            if raw is not None:
                try:
                    candidate_id = int(raw)
                    break
                except Exception:
                    continue
        if candidate_id is not None:
            groups[key]["members"].append(candidate_id)

    # Dedupe members e monta lista ordenada
    result = []
    for key, v in groups.items():
        members = sorted(list(set(v["members"])))
        result.append({
            "key": key,
            "label": f"{v['label']}{' ('+str(v['count'])+')' if v['count'] else ''}",
            "count": v["count"],
            "members": members,
            "start_date": v.get("start_date", ""),
            "start_time": v.get("start_time", "")
        })

    # Ordene por start_date (vazio por último) e label
    def sort_key(item):
        sd = item.get("start_date") or ""
        st = item.get("start_time") or ""
        return (sd == "", sd, st, item.get("label") or "")

    result.sort(key=sort_key)
    return result


@router.get("/batch/{event_id}/{batch_name}", response_model=List[CandidateOut])
def get_candidates_by_batch(
    event_id: int,
    batch_name: str,
    db: Session = Depends(get_tenant_db_session)
):
    """Lista todos os candidatos de uma turma específica, ordenados por batch_number."""
    # Verifica se o evento existe
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado."
        )
    
    # Busca candidatos da turma
    candidates = db.query(Candidate).filter(
        Candidate.event_id == event_id,
        Candidate.batch_name == batch_name
    ).order_by(Candidate.batch_number).all()
    
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum candidato encontrado na turma '{batch_name}'."
        )
    
    # Adiciona flag de resultados
    for candidate in candidates:
        has_results = db.query(func.count(ExecutionResult.id)).filter(
            ExecutionResult.candidate_id == candidate.id
        ).scalar() > 0
        candidate.has_results = has_results
    
    return candidates


@router.get("/batch/{event_id}/{batch_name}/attendance-pdf")
def generate_batch_attendance_pdf(
    event_id: int,
    batch_name: str,
    db: Session = Depends(get_tenant_db_session)
):
    """Gera PDF de lista de presenca da turma com logo, horário e data BR."""
    from sqlalchemy import text
    from app.db.models.public import Tenant
    
    # Busca evento
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    # Busca candidatos da turma
    candidates = db.query(Candidate).filter(
        Candidate.event_id == event_id,
        Candidate.batch_name == batch_name
    ).order_by(Candidate.batch_number).all()
    
    if not candidates:
        raise HTTPException(status_code=404, detail=f"Turma '{batch_name}' não encontrada")
    
    # Busca dados da empresa/tenant atual (incluindo logo)
    company_data = {'name': 'TAFON', 'logo_url': None}
    
    try:
        # Pega schema atual
        result = db.execute(text("SHOW search_path")).fetchone()
        if result:
            schema_name = result[0].split(',')[0].strip().strip('"')
            
            # Busca tenant no schema public
            db.execute(text("SET search_path TO public"))
            tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
            
            if tenant:
                company_data = {
                    'name': tenant.nome_empresa or 'TAFON',
                    'logo_url': tenant.logo_url
                }
            
            # Restaura search_path
            db.execute(text(f'SET search_path TO "{schema_name}"'))
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Erro ao buscar dados da empresa: {e}")
    
    # Busca horário da turma - TENTA MÚLTIPLAS FORMAS
    start_time = None
    
    # 1. Se houver um campo start_time no candidato (futuro)
    if candidates and hasattr(candidates[0], 'start_time') and candidates[0].start_time:
        start_time = candidates[0].start_time
    
    # 2. Extrai do nome da turma (padrões aceitos: "08:00", "8:00", "Horário: 08:00", "- 08:00")
    if not start_time and batch_name:
        import re
        # Aceita vários formatos: 08:00, 8:00, horario: 08:00, - 08:00, etc
        match = re.search(r'(\d{1,2}:\d{2})', batch_name)
        if match:
            start_time = match.group(1)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ Horário extraído da turma '{batch_name}': {start_time}")
    
    # Dados para o PDF
    event_data = {
        'name': event.name,
        'date': str(event.date_start),
        'location': event.location,
        'start_time': start_time  # ✅ NOVO: horário da turma
    }
    
    candidates_data = [
        {
            'batch_number': c.batch_number or 0,
            'full_name': c.full_name,
            'cpf': c.cpf,
            'registration_number': c.registration_number
        }
        for c in candidates
    ]
    
    # Gera PDF com empresa E horário
    pdf_bytes = generate_attendance_list_pdf(event_data, batch_name, candidates_data, company_data)
    
    # Retorna como download
    safe_batch_name = batch_name.replace(' ', '_').replace('/', '-')
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="lista_presenca_{safe_batch_name}.pdf"'
        }
    )


@router.get("/batch/{event_id}/{batch_name}/badges-pdf")
def generate_batch_badges_pdf_endpoint(
    event_id: int,
    batch_name: str,
    db: Session = Depends(get_tenant_db_session)
):
    """Gera PDF de espelhos/etiquetas numeradas da turma com dados da empresa e logo."""
    from sqlalchemy import text
    from app.db.models.public import Tenant
    
    # Busca evento
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    # Busca candidatos da turma
    candidates = db.query(Candidate).filter(
        Candidate.event_id == event_id,
        Candidate.batch_name == batch_name
    ).order_by(Candidate.batch_number).all()
    
    if not candidates:
        raise HTTPException(status_code=404, detail=f"Turma '{batch_name}' não encontrada")
    
    # Busca dados da empresa/tenant atual (incluindo logo)
    company_data = {'name': 'TAFON', 'phone': '', 'email': '', 'logo_url': None}
    
    try:
        # Pega schema atual (está no search_path)
        result = db.execute(text("SHOW search_path")).fetchone()
        if result:
            schema_name = result[0].split(',')[0].strip().strip('"')
            
            # Busca tenant correspondente no schema public
            db.execute(text("SET search_path TO public"))
            tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
            
            if tenant:
                company_data = {
                    'name': tenant.nome_empresa or 'TAFON',
                    'phone': tenant.responsible_phone or '',
                    'email': tenant.responsible_email or '',  # ✅ CORRIGIDO
                    'logo_url': tenant.logo_url
                }
                
                # ✅ NOVO: Logging detalhado
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"📊 Dados da empresa para espelhos:")
                logger.info(f"   Nome: {company_data['name']}")
                logger.info(f"   Logo: {company_data['logo_url']}")
                logger.info(f"   Schema: {schema_name}")
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"⚠️  Tenant não encontrado para schema '{schema_name}'")
            
            # Restaura search_path
            db.execute(text(f'SET search_path TO "{schema_name}"'))
    except Exception as e:
        # Se falhar, usa dados padrão
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Erro ao buscar dados da empresa: {e}")
    
    # Busca horário da turma
    start_time = None
    if candidates and hasattr(candidates[0], 'start_time'):
        start_time = candidates[0].start_time
    
    # Se não tem start_time, tenta extrair do nome da turma
    if not start_time and batch_name:
        import re
        match = re.search(r'(\d{1,2}:\d{2})', batch_name)
        if match:
            start_time = match.group(1)
    
    # Dados para o PDF
    event_data = {
        'name': event.name,
        'date': str(event.date_start),
        'location': event.location,
        'start_time': start_time
    }
    
    candidates_data = [
        {
            'batch_number': c.batch_number or 0,
            'full_name': c.full_name,
            'registration_number': c.registration_number,
            'gender': c.gender
        }
        for c in candidates
    ]
    
    # Gera PDF com dados da empresa, LOGO E HORÁRIO
    pdf_bytes = generate_batch_badges_pdf(event_data, batch_name, candidates_data, company_data)
    
    # Retorna como download
    safe_batch_name = batch_name.replace(' ', '_').replace('/', '-')
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="espelhos_{safe_batch_name}.pdf"'
        }
    )


# =============================================================================
# ✅ NOVOS ENDPOINTS: GERAR PDFS DE TODAS AS TURMAS DE UMA VEZ
# =============================================================================

@router.get("/event/{event_id}/all-attendance-pdf")
def generate_all_attendance_lists_pdf(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Gera PDF com TODAS as listas de presença de todas as turmas do evento.
    
    📋 Útil para imprimir todas as listas de uma vez!
    """
    from sqlalchemy import text
    from app.db.models.public import Tenant
    import logging
    logger = logging.getLogger(__name__)
    
    # Busca evento
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    # Busca todas as turmas do evento
    batches_query = db.query(Candidate.batch_name).filter(
        Candidate.event_id == event_id,
        Candidate.batch_name.isnot(None)
    ).distinct().order_by(Candidate.batch_name).all()
    
    batch_names = [b[0] for b in batches_query]
    
    if not batch_names:
        raise HTTPException(status_code=404, detail="Nenhuma turma encontrada neste evento")
    
    logger.info(f"📋 Gerando listas de presença para {len(batch_names)} turmas do evento {event.name}")
    
    # Busca dados da empresa
    company_data = {'name': 'TAFON', 'logo_url': None}
    try:
        result = db.execute(text("SHOW search_path")).fetchone()
        if result:
            schema_name = result[0].split(',')[0].strip().strip('"')
            db.execute(text("SET search_path TO public"))
            tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
            if tenant:
                company_data = {
                    'name': tenant.nome_empresa or 'TAFON',
                    'logo_url': tenant.logo_url
                }
            db.execute(text(f'SET search_path TO "{schema_name}"'))
    except Exception as e:
        logger.warning(f"Erro ao buscar dados da empresa: {e}")
    
    # Gera PDFs de todas as turmas e concatena
    from PyPDF2 import PdfMerger
    merger = PdfMerger()
    
    for batch_name in batch_names:
        # Busca candidatos da turma
        candidates = db.query(Candidate).filter(
            Candidate.event_id == event_id,
            Candidate.batch_name == batch_name
        ).order_by(Candidate.batch_number).all()
        
        if not candidates:
            continue
        
        # Busca horário
        start_time = None
        if candidates and hasattr(candidates[0], 'start_time') and candidates[0].start_time:
            start_time = candidates[0].start_time
        
        # Dados para o PDF
        event_data = {
            'name': event.name,
            'date': str(event.date_start),
            'location': event.location,
            'start_time': start_time
        }
        
        candidates_data = [
            {
                'batch_number': c.batch_number or 0,
                'full_name': c.full_name,
                'cpf': c.cpf,
                'registration_number': c.registration_number
            }
            for c in candidates
        ]
        
        # Gera PDF da turma
        pdf_bytes = generate_attendance_list_pdf(event_data, batch_name, candidates_data, company_data)
        merger.append(io.BytesIO(pdf_bytes))
        
        logger.info(f"  ✅ Lista gerada: {batch_name} ({len(candidates)} candidatos)")
    
    # Salva PDF final
    output = io.BytesIO()
    merger.write(output)
    merger.close()
    output.seek(0)
    
    logger.info(f"✅ PDF completo gerado com {len(batch_names)} turmas")
    
    # Retorna como download
    safe_event_name = event.name.replace(' ', '_').replace('/', '-')
    return StreamingResponse(
        output,
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="listas_presenca_{safe_event_name}_todas_turmas.pdf"'
        }
    )


@router.get("/event/{event_id}/all-badges-pdf")
def generate_all_badges_pdf(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Gera PDF com TODOS os espelhos numerados de todas as turmas do evento.
    
    🏷️ Útil para imprimir todos os espelhos de uma vez!
    """
    from sqlalchemy import text
    from app.db.models.public import Tenant
    import logging
    logger = logging.getLogger(__name__)
    
    # Busca evento
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    
    # Busca todas as turmas do evento
    batches_query = db.query(Candidate.batch_name).filter(
        Candidate.event_id == event_id,
        Candidate.batch_name.isnot(None)
    ).distinct().order_by(Candidate.batch_name).all()
    
    batch_names = [b[0] for b in batches_query]
    
    if not batch_names:
        raise HTTPException(status_code=404, detail="Nenhuma turma encontrada neste evento")
    
    logger.info(f"🏷️  Gerando espelhos para {len(batch_names)} turmas do evento {event.name}")
    
    # Busca dados da empresa
    company_data = {'name': 'TAFON', 'phone': '', 'email': '', 'logo_url': None}
    try:
        result = db.execute(text("SHOW search_path")).fetchone()
        if result:
            schema_name = result[0].split(',')[0].strip().strip('"')
            db.execute(text("SET search_path TO public"))
            tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
            if tenant:
                company_data = {
                    'name': tenant.nome_empresa or 'TAFON',
                    'phone': tenant.responsible_phone or '',
                    'email': tenant.responsible_email or '',
                    'logo_url': tenant.logo_url
                }
            db.execute(text(f'SET search_path TO "{schema_name}"'))
    except Exception as e:
        logger.warning(f"Erro ao buscar dados da empresa: {e}")
    
    # Gera PDFs de todas as turmas e concatena
    from PyPDF2 import PdfMerger
    merger = PdfMerger()
    
    total_candidates = 0
    
    for batch_name in batch_names:
        # Busca candidatos da turma
        candidates = db.query(Candidate).filter(
            Candidate.event_id == event_id,
            Candidate.batch_name == batch_name
        ).order_by(Candidate.batch_number).all()
        
        if not candidates:
            continue
        
        total_candidates += len(candidates)
        
        # Busca horário
        start_time = None
        if candidates and hasattr(candidates[0], 'start_time') and candidates[0].start_time:
            start_time = candidates[0].start_time
        
        # Dados para o PDF
        event_data = {
            'name': event.name,
            'date': str(event.date_start),
            'location': event.location,
            'start_time': start_time
        }
        
        candidates_data = [
            {
                'batch_number': c.batch_number or 0,
                'full_name': c.full_name,
                'registration_number': c.registration_number,
                'gender': c.gender
            }
            for c in candidates
        ]
        
        # Gera PDF da turma
        pdf_bytes = generate_batch_badges_pdf(event_data, batch_name, candidates_data, company_data)
        merger.append(io.BytesIO(pdf_bytes))
        
        logger.info(f"  ✅ Espelhos gerados: {batch_name} ({len(candidates)} candidatos)")
    
    # Salva PDF final
    output = io.BytesIO()
    merger.write(output)
    merger.close()
    output.seek(0)
    
    logger.info(f"✅ PDF completo gerado: {total_candidates} espelhos de {len(batch_names)} turmas")
    
    # Retorna como download
    safe_event_name = event.name.replace(' ', '_').replace('/', '-')
    return StreamingResponse(
        output,
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="espelhos_{safe_event_name}_todas_turmas.pdf"'
        }
    )
