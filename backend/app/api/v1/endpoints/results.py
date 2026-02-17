# backend/app/api/v1/endpoints/results.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
import io
import logging
import os
from datetime import date, datetime
import unicodedata
from fastapi import BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import json
import time
from pathlib import Path

from app.api.deps_tenant import get_tenant_db_session
from app.db.models.tenant import Event, Exercise, Candidate, ExecutionResult, PassCriteria
from app.schemas.result_schema import (
    CandidateResult, ExerciseResult, AttemptResult,
    EventResultsSummary, ExerciseSummary
)
from app.utils.pdf_generator import generate_candidate_pdf, generate_consolidated_report_pdf

router = APIRouter(tags=["TAF - Módulo 5: Resultados"])
logger = logging.getLogger(__name__)


JOBS_DIR = Path(os.environ.get("TAF_JOBS_DIR", "/app/uploads/generated_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

def _job_status_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"

def _job_output_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.pdf"

def _write_job_status(job_id: str, status: str, info: dict = None):
    p = _job_status_path(job_id)
    payload = {"job_id": job_id, "status": status, "updated_at": time.time()}
    if info:
        payload.update(info)
    try:
        # write atomically: write a temp file next to destination e depois replace
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        # os.replace é atômico em POSIX/Windows
        os.replace(str(tmp), str(p))
    except Exception:
        logger.exception("Could not write job status file for %s", job_id)

def _read_job_status(job_id: str):
    p = _job_status_path(job_id)
    try:
        if not p.exists():
            return None
        s = p.read_text(encoding="utf-8").strip()
        if not s:
            # arquivo vazio por algum motivo
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            logger.exception("Invalid JSON in job status file for %s", job_id)
            return None
    except Exception:
        logger.exception("Could not read job status for %s", job_id)
        return None

def _generate_all_fichas_job(job_id: str, event_id: int, db: Session):
    """
    Background job: gera PDF combinado e grava em disco.
    Escreve status em JOBS_DIR/{job_id}.json e resultado em JOBS_DIR/{job_id}.pdf

    Comportamento:
    - resolve company/tenant/coordenador como no endpoint individual
    - tenta resolver/baixar logo e assinatura via _resolve_logo_path
    - escreve status periodicamente via _write_job_status (atomic)
    - fecha a session do DB ao final (se suportado)
    - limpa arquivos temporários criados pelo _resolve_logo_path
    """
    temp_files = []
    try:
        _write_job_status(job_id, "processing", {"progress": 0})
        from PyPDF2 import PdfReader, PdfWriter
        writer = PdfWriter()

        # fetch event / candidates / exercises
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            _write_job_status(job_id, "failed", {"reason": "Evento não encontrado"})
            return

        candidates = db.query(Candidate).filter(Candidate.event_id == event_id).all()
        exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()

        # ---------------------------
        # Resolver company_name / company_logo_path (mesma lógica do endpoint individual)
        # ---------------------------
        company_name = os.environ.get('COMPANY_NAME') or None
        company_logo_path = os.environ.get('COMPANY_LOGO_PATH') or None
        if not company_name:
            company_name = getattr(event, 'company_name', None) or getattr(event, 'organization', None) or getattr(event, 'organizer_name', None)
        if not company_logo_path:
            company_logo_path = getattr(event, 'company_logo', None) or getattr(event, 'logo_url', None) or getattr(event, 'logo', None)

        # Try to resolve tenant info from public schema (same strategy used in individual endpoint)
        tenant_info = None
        try:
            sp = db.execute(text("SHOW search_path")).fetchone()
            schema_name = None
            if sp and sp[0]:
                schema_name = sp[0].split(',')[0].strip().strip('"')

            if schema_name:
                # temporarily switch to public to read Tenant
                db.execute(text("SET search_path TO public"))
                try:
                    from app.db.models.public import Tenant
                    tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
                    if tenant:
                        tenant_info = tenant
                        if not company_name:
                            company_name = getattr(tenant, 'nome_empresa', None) or getattr(tenant, 'name', None)
                        if not company_logo_path:
                            company_logo_path = getattr(tenant, 'logo_url', None) or getattr(tenant, 'logo', None)
                finally:
                    # restore original schema
                    if schema_name:
                        db.execute(text(f'SET search_path TO "{schema_name}"'))
        except Exception:
            logger.exception("Erro ao tentar extrair Tenant do schema public para cabeçalho do PDF (job)")

        # ---------------------------
        # Resolve coordinator (same logic as individual endpoint)
        # ---------------------------
        coord_name = None
        coord_cref = None
        coord_signature = None

        coord_id = getattr(event, "coordinator_id", None)

        if coord_id is not None:
            try:
                Coordinator = None
                try:
                    from app.db.models.tenant import Coordinator as CoordinatorModel
                    Coordinator = CoordinatorModel
                except Exception:
                    try:
                        from app.db.models.public import Coordinator as CoordinatorModel
                        Coordinator = CoordinatorModel
                    except Exception:
                        try:
                            from app.db.models import Coordinator as CoordinatorModel
                            Coordinator = CoordinatorModel
                        except Exception:
                            Coordinator = None

                if Coordinator is not None:
                    coord_obj = db.query(Coordinator).filter(Coordinator.id == coord_id).first()
                    if coord_obj:
                        coord_name = getattr(coord_obj, "full_name", None) or getattr(coord_obj, "name", None) or getattr(coord_obj, "nome", None)
                        coord_cref = getattr(coord_obj, "cref", None) or getattr(coord_obj, "CREF", None)
                        coord_signature = getattr(coord_obj, "signature_url", None) or getattr(coord_obj, "assinatura_url", None) or getattr(coord_obj, "signature", None)
            except Exception:
                logger.debug("Coordinator lookup failed in job", exc_info=True)

        # Fallback robusto via tabelas comuns
        if not coord_name and coord_id is not None:
            table_candidates = ['user_tenant', 'user', 'users', 'users_tenant', 'person', 'people', 'staff', 'employee', 'coordinator']
            for tbl in table_candidates:
                try:
                    q = text(f"SELECT * FROM {tbl} WHERE id = :id LIMIT 1")
                    row = db.execute(q, {"id": coord_id}).fetchone()
                    if not row:
                        continue

                    mapping = {}
                    if hasattr(row, "_mapping"):
                        for k, v in row._mapping.items():
                            mapping[k.lower()] = v
                    elif hasattr(row, "keys"):
                        for idx, k in enumerate(row.keys()):
                            try:
                                mapping[k.lower()] = row[idx]
                            except Exception:
                                mapping[k.lower()] = None
                    else:
                        mapping = {}

                    name_candidates = ['nome', 'full_name', 'name', 'first_name', 'username', 'email']
                    name_val = None
                    for nm in name_candidates:
                        if nm in mapping and mapping[nm]:
                            name_val = mapping[nm]
                            break

                    if not name_val:
                        fn = mapping.get('first_name') or mapping.get('firstname')
                        ln = mapping.get('last_name') or mapping.get('lastname') or mapping.get('surname')
                        if fn or ln:
                            name_val = " ".join(filter(None, [fn, ln]))

                    cref_candidates = ['cref', 'CREF', 'cref_number', 'cref_no']
                    cref_val = None
                    for cm in cref_candidates:
                        if cm.lower() in mapping and mapping[cm.lower()]:
                            cref_val = mapping[cm.lower()]
                            break

                    sig_candidates = ['signature_url', 'assinatura_url', 'signature', 'assinatura', 'signature_path', 'avatar_url']
                    sig_val = None
                    for sm in sig_candidates:
                        if sm.lower() in mapping and mapping[sm.lower()]:
                            sig_val = mapping[sm.lower()]
                            break

                    if not name_val:
                        try:
                            if len(row) >= 2:
                                name_val = row[1]
                            if len(row) >= 3 and not cref_val:
                                possible = row[2]
                                if possible and isinstance(possible, str) and any(ch.isdigit() for ch in possible):
                                    cref_val = possible
                            if len(row) >= 4 and not sig_val:
                                sig_val = row[3]
                        except Exception:
                            pass

                    if name_val:
                        coord_name = str(name_val) if name_val is not None else None
                        coord_cref = str(cref_val) if cref_val is not None else None
                        coord_signature = str(sig_val) if sig_val is not None else None
                        logger.debug("Resolved coordinator via raw SQL table=%s id=%s -> name=%r cref=%r signature=%r (job)", tbl, coord_id, coord_name, coord_cref, coord_signature)
                        break
                except Exception:
                    continue

        # Se não encontrou via coordinator_id, tenta campos diretos no event (ou parâmetro)
        if not coord_name:
            coord_name = getattr(event, 'coordinator_name', None) or getattr(event, 'coordenador', None)
        if not coord_cref:
            coord_cref = getattr(event, 'coordinator_cref', None) or getattr(event, 'coordenador_cref', None)
        if not coord_signature:
            coord_signature = getattr(event, 'coordinator_signature_url', None) or getattr(event, 'coordinator_signature', None)

        # Se ainda não achou, tenta extrair do tenant (se disponível)
        if tenant_info:
            if not coord_name:
                coord_name = getattr(tenant_info, 'coordenador_nome', None) or getattr(tenant_info, 'coordinator_name', None)
            if not coord_cref:
                coord_cref = getattr(tenant_info, 'coordenador_cref', None) or getattr(tenant_info, 'coordinator_cref', None)
            if not coord_signature:
                coord_signature = getattr(tenant_info, 'coordenador_signature_url', None) or getattr(tenant_info, 'coordinator_signature_url', None) or getattr(tenant_info, 'assinatura_url', None)

        # attendance fallback (schema-aware) if no signature yet
        if not coord_signature and coord_id is not None:
            try:
                sp = db.execute(text("SHOW search_path")).fetchone()
                schema = sp[0].split(',')[0].strip().strip('"') if sp and sp[0] else None
                table_full = f'"{schema}".event_worker_attendance' if schema else 'event_worker_attendance'
                q = text(f"""
                    SELECT check_in_signature_path
                    FROM {table_full}
                    WHERE event_id = :event_id
                      AND (user_id = :coord_id OR event_worker_id = :coord_id)
                      AND check_in_signature_path IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                row = db.execute(q, {"event_id": event_id, "coord_id": coord_id}).fetchone()
                if row and row[0]:
                    coord_signature = str(row[0])
            except Exception:
                logger.debug("attendance lookup failed in job", exc_info=True)

        # Tentar resolver caminhos reais (baixar URL se necessário) para logo e assinatura
        try:
            from app.utils.pdf_generator import _resolve_logo_path
            # empresa / logo
            if company_logo_path:
                try:
                    resolved_logo, logo_tmp = _resolve_logo_path(company_logo_path)
                    if resolved_logo and os.path.exists(resolved_logo):
                        company_logo_path = resolved_logo
                        if logo_tmp:
                            temp_files.append(resolved_logo)
                        logger.info("[JOB] resolved company_logo_path -> %s (temp=%s)", company_logo_path, logo_tmp)
                except Exception:
                    logger.debug("logo resolve helper failed in job", exc_info=True)

            # assinatura do coordenador
            if coord_signature:
                try:
                    resolved_sig, sig_tmp = _resolve_logo_path(coord_signature)
                except Exception:
                    resolved_sig, sig_tmp = (None, False)

                if resolved_sig and os.path.exists(resolved_sig):
                    coord_signature = resolved_sig
                    if sig_tmp:
                        temp_files.append(resolved_sig)
                    logger.info("[JOB] resolved coord_signature -> %s (temp=%s)", coord_signature, sig_tmp)
                else:
                    # fallback: tentar prefixes e variantes (mesma heurística usada no endpoint individual)
                    candidates_paths = []
                    try:
                        candidates_paths.extend([
                            coord_signature,
                            str(coord_signature).lstrip('/') if coord_signature else None,
                            os.path.join('/app/uploads', str(coord_signature).lstrip('/')) if coord_signature else None,
                            os.path.join('/app/uploads', 'signatures', str(coord_signature).lstrip('/')) if coord_signature else None,
                            os.path.join('/app/uploads', 'signatures', os.path.basename(str(coord_signature))) if coord_signature else None,
                            os.path.join(os.getcwd(), str(coord_signature).lstrip('/')) if coord_signature else None,
                            os.path.join('backend', 'app', str(coord_signature).lstrip('/')) if coord_signature else None,
                            os.path.join('backend', 'app', 'static', str(coord_signature).lstrip('/')) if coord_signature else None
                        ])
                    except Exception:
                        pass

                    found = None
                    for c in candidates_paths:
                        if not c:
                            continue
                        norm = os.path.normpath(c)
                        try:
                            if os.path.exists(norm):
                                found = norm
                                break
                        except Exception:
                            continue

                    if found:
                        coord_signature = found
                        logger.info("[JOB] found coord_signature via fallback -> %s", coord_signature)
                    else:
                        logger.info("[JOB] coord_signature %r could not be resolved to an existing file", coord_signature)
        except Exception:
            logger.debug("Failed to resolve logo/signature paths in job", exc_info=True)

        logger.info("[JOB START] job=%s event=%s candidates=%d company=%r logo=%r coord=%r cref=%r sig=%r",
                    job_id, event_id, len(candidates), company_name, company_logo_path, coord_name, coord_cref, coord_signature)

        # iterate candidates and append their PDFs
        total = max(len(candidates), 1)
        for idx, candidate in enumerate(candidates, start=1):
            # obter id/identificador do candidato de forma defensiva (suporta ORM object ou string/int)
            cur_candidate_id = None
            try:
                if hasattr(candidate, "id"):
                    cur_candidate_id = candidate.id
                elif hasattr(candidate, "candidate_id"):
                    cur_candidate_id = candidate.candidate_id
                else:
                    cur_candidate_id = candidate
            except Exception:
                cur_candidate_id = candidate

            # build candidate_data
            start_time = getattr(candidate, 'start_time', None) or getattr(candidate, 'batch_start_time', None)
            start_date_obj = getattr(candidate, 'start_date', None) or getattr(candidate, 'batch_date', None)
            if isinstance(start_date_obj, (date, datetime)):
                start_date = start_date_obj.isoformat()
            else:
                start_date = str(start_date_obj) if start_date_obj is not None else None

            candidate_data = {
                'full_name': getattr(candidate, 'full_name', getattr(candidate, 'name', None)),
                'cpf': getattr(candidate, 'cpf', None),
                'registration_number': getattr(candidate, 'registration_number', None),
                'gender': getattr(candidate, 'gender', None),
                'batch_name': getattr(candidate, 'batch_name', None),
                'batch_number': getattr(candidate, 'batch_number', None),
                'start_time': start_time,
                'start_date': start_date,
                'overall_status': None
            }

            # assemble exercises_results_for_candidate
            exercises_results_for_candidate = []
            for exercise in exercises:
                results = db.query(ExecutionResult).filter(
                    and_(
                        ExecutionResult.candidate_id == (getattr(candidate, 'id', getattr(candidate, 'candidate_id', candidate))),
                        ExecutionResult.exercise_id == exercise.id
                    )
                ).all()
                if not results:
                    continue
                unit = (exercise.unit_of_measure or "").lower()
                if 'tempo' in unit:
                    best = min(results, key=lambda r: getattr(r, "measured_value", None) or 0)
                else:
                    best = max(results, key=lambda r: getattr(r, "measured_value", None) or 0)
                exercises_results_for_candidate.append({
                    'exercise_name': exercise.name,
                    'unit_of_measure': exercise.unit_of_measure,
                    'best_value': getattr(best, "measured_value", None),
                    'is_approved': getattr(best, "is_approved_in_exercise", None)
                })

            # overall_status
            if exercises and len(exercises_results_for_candidate) == len(exercises):
                all_approved = all(e.get('is_approved') for e in exercises_results_for_candidate)
                candidate_data['overall_status'] = 'approved' if all_approved else 'failed'
            else:
                candidate_data['overall_status'] = 'in_progress'

            # DEBUG: log do caminho de assinatura usado para este candidato
            try:
                logger.info("[JOB] candidate=%s using coord_signature=%r exists=%s coord_name=%r coord_cref=%r company_logo=%r",
                            cur_candidate_id,
                            coord_signature,
                            os.path.exists(coord_signature) if coord_signature else False,
                            coord_name,
                            coord_cref,
                            company_logo_path)
            except Exception:
                logger.debug("Could not log candidate signature info", exc_info=True)

            try:
                pdf_bytes = generate_candidate_pdf(
                    candidate_data=candidate_data,
                    exercises_results=exercises_results_for_candidate,
                    event_data={'name': event.name, 'date': str(event.date_start), 'location': event.location},
                    signature_path=coord_signature,
                    coordinator_name=coord_name,
                    coordinator_cref=coord_cref,
                    company_name=company_name,
                    company_logo_path=company_logo_path
                )
                if pdf_bytes:
                    reader = PdfReader(io.BytesIO(pdf_bytes))
                    for page in reader.pages:
                        writer.add_page(page)
            except Exception:
                logger.exception("Failed to generate single PDF for candidate %s in job %s", cur_candidate_id, job_id)

        # write final PDF
        out_path = _job_output_path(job_id)
        try:
            with out_path.open("wb") as fh:
                writer.write(fh)
            _write_job_status(job_id, "done", {"progress": 100, "output": str(out_path.name)})
            logger.info("[JOB DONE] job=%s output=%s", job_id, out_path)
        except Exception:
            logger.exception("Failed to write combined PDF for job %s", job_id)
            _write_job_status(job_id, "failed", {"reason": "write_failed"})
    except Exception:
        logger.exception("Unexpected error in job %s", job_id)
        _write_job_status(job_id, "failed", {"reason": "unexpected_error"})
    finally:
        # cleanup temporários criados por _resolve_logo_path (se houver)
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                logger.debug("Could not remove temp file %s for job %s", f, job_id, exc_info=True)

        # Fechar a sessão do DB passada ao job, se suportar .close()
        try:
            if hasattr(db, "close") and callable(db.close):
                db.close()
        except Exception:
            logger.debug("Could not close DB session for job %s", job_id, exc_info=True)


def normalize_for_sort(s: Optional[str]) -> str:
    """
    Normaliza string para ordenação:
      - transforma None -> ''
      - aplica NFD e remove marcas diacríticas (acentos)
      - casefold para comparação case-insensitive adequada
    """
    if not s:
        return ""
    normalized = unicodedata.normalize("NFD", s)
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_accents.casefold()

# =============================================================================
# ROTAS DE CONSULTA DE RESULTADOS
# =============================================================================

@router.get("/event/{event_id}/candidates", response_model=List[CandidateResult])
def get_event_results(
    event_id: int,
    gender: Optional[str] = None,
    batch_name: Optional[str] = None,
    status: Optional[str] = None,
    name: Optional[str] = None,         # novo: filtrar por nome (partial, case-insensitive)
    number: Optional[str] = None,       # novo: filtrar por número (registration_number ou batch_number)
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna resultados consolidados de todos os candidatos de um evento"""
    try:
        # Busca evento
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Evento não encontrado")

        # Busca candidatos com filtros
        query = db.query(Candidate).filter(Candidate.event_id == event_id)

        if gender:
            query = query.filter(Candidate.gender == gender)
        if batch_name:
            query = query.filter(Candidate.batch_name == batch_name)

        # filtro por nome (partial, case-insensitive)
        if name:
            query = query.filter(Candidate.full_name.ilike(f"%{name}%"))

        # filtro por número:
        # - tenta casar registration_number (partial)
        # - e, se number for dígitos e representar um número válido > 0, tenta casar batch_number == int(stripped_leading_zeros)
        if number:
            number_like = f"%{number}%"
            number_filters = [Candidate.registration_number.ilike(number_like)]
            if number.isdigit():
                # evitar interpretar apenas zeros ("00", "000") como batch_number 0:
                stripped = number.lstrip('0')
                if stripped != '':
                    try:
                        num_int = int(stripped)
                        number_filters.append(Candidate.batch_number == num_int)
                    except Exception:
                        # se falhar, não adiciona filtro de batch_number
                        pass
            # combinar OR
            query = query.filter(or_(*number_filters))

        candidates = query.all()
        exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()

        results_list = []

        for candidate in candidates:
            exercises_results = []

            for exercise in exercises:
                # Busca resultados do candidato neste exercício
                attempts = db.query(ExecutionResult).filter(
                    and_(
                        ExecutionResult.candidate_id == candidate.id,
                        ExecutionResult.exercise_id == exercise.id
                    )
                ).all()

                # Busca critério
                criteria = db.query(PassCriteria).filter(
                    and_(
                        PassCriteria.exercise_id == exercise.id,
                        PassCriteria.gender == candidate.gender
                    )
                ).first()

                attempts_list = [
                    AttemptResult(
                        attempt_number=a.attempt_number,
                        measured_value=a.measured_value,
                        is_valid=a.is_valid,
                        is_approved=a.is_approved_in_exercise,
                        created_at=getattr(a, "created_at", None)
                    )
                    for a in attempts
                ]

                # Melhor tentativa
                best = None
                is_approved = None
                if attempts_list:
                    # Para repetições/metros: maior valor
                    # Para tempo: menor valor
                    if 'tempo' in (exercise.unit_of_measure or '').lower():
                        best = min(attempts_list, key=lambda x: x.measured_value)
                    else:
                        best = max(attempts_list, key=lambda x: x.measured_value)

                    is_approved = best.is_approved

                exercises_results.append(ExerciseResult(
                    exercise_id=exercise.id,
                    exercise_name=exercise.name,
                    unit_of_measure=exercise.unit_of_measure,
                    attempts=attempts_list,
                    best_attempt=best,
                    is_completed=len(attempts_list) > 0,
                    is_approved=is_approved,
                    criteria_min_value=criteria.min_value if criteria else None,
                    criteria_max_time=criteria.max_time_s if criteria else None
                ))

            # Calcula status geral
            completed = sum(1 for e in exercises_results if e.is_completed)
            approved = sum(1 for e in exercises_results if e.is_approved == True)
            failed = sum(1 for e in exercises_results if e.is_approved == False)

            if completed == len(exercises):
                if approved == len(exercises):
                    overall_status = "approved"
                else:
                    overall_status = "failed"
            else:
                overall_status = "in_progress"

            # Filtro por status
            if status and overall_status != status:
                continue

            # Normalizar/pegar campos de turma do candidato (existência depende do model)
            batch_number_raw = getattr(candidate, "batch_number", None)
            start_time = getattr(candidate, "start_time", None) or getattr(candidate, "batch_start_time", None)
            start_date_obj = getattr(candidate, "start_date", None) or getattr(candidate, "batch_date", None)

            # Converter date/datetime para string ISO (Pydantic espera string para start_date)
            if isinstance(start_date_obj, (date, datetime)):
                start_date = start_date_obj.isoformat()
            else:
                start_date = str(start_date_obj) if start_date_obj is not None else None

            # Formatar batch_number com 3 dígitos quando possível (ex: 1 -> "001")
            if batch_number_raw is None:
                batch_number = None
            else:
                try:
                    bn_int = int(batch_number_raw)
                    # only pad positive integers (0 will be shown as "000" if present)
                    batch_number = f"{bn_int:03d}"
                except Exception:
                    batch_number = str(batch_number_raw).strip() or None

            results_list.append(CandidateResult(
                candidate_id=candidate.id,
                candidate_name=candidate.full_name,
                registration_number=candidate.registration_number,
                cpf=candidate.cpf,
                gender=candidate.gender,
                batch_name=candidate.batch_name,
                # novos campos (batch_number padded string quando aplicável)
                batch_number=batch_number,
                start_time=start_time,
                start_date=start_date,
                exercises_results=exercises_results,
                total_exercises=len(exercises),
                completed_exercises=completed,
                approved_exercises=approved,
                failed_exercises=failed,
                overall_status=overall_status
            ))

        # Ordenar alfabeticamente por nome do candidato (case-insensitive, tratando acentos)
        results_list.sort(key=lambda r: normalize_for_sort(r.candidate_name))

        return results_list

    except HTTPException:
        # re-raise HTTP exceptions unmodified
        raise
    except Exception:
        logger.exception("[get_event_results] erro ao montar resultados")
        # Em ambiente de produção, retorne uma mensagem genérica
        raise HTTPException(status_code=500, detail="Erro interno ao montar resultados")


@router.get("/event/{event_id}/summary", response_model=EventResultsSummary)
def get_event_summary(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Retorna resumo estatístico do evento"""

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    candidates = db.query(Candidate).filter(Candidate.event_id == event_id).all()
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()

    total_candidates = len(candidates)
    total_exercises = len(exercises)

    # Conta status dos candidatos
    approved = 0
    failed = 0
    in_progress = 0

    for candidate in candidates:
        results_count = db.query(func.count(func.distinct(ExecutionResult.exercise_id))).filter(
            ExecutionResult.candidate_id == candidate.id
        ).scalar()

        if results_count == total_exercises:
            # Verifica se todos aprovados
            approved_count = db.query(func.count(ExecutionResult.id)).filter(
                and_(
                    ExecutionResult.candidate_id == candidate.id,
                    ExecutionResult.is_approved_in_exercise == True
                )
            ).scalar()

            if approved_count == total_exercises:
                approved += 1
            else:
                failed += 1
        else:
            in_progress += 1

    # Taxas
    approval_rate = (approved / total_candidates * 100) if total_candidates > 0 else 0
    completion_rate = ((approved + failed) / total_candidates * 100) if total_candidates > 0 else 0

    # Resumo por exercício
    exercises_summary = []
    for exercise in exercises:
        results = db.query(ExecutionResult).filter(
            ExecutionResult.exercise_id == exercise.id
        ).all()

        unique_candidates = len(set(r.candidate_id for r in results))
        approved_count = sum(1 for r in results if r.is_approved_in_exercise == True)
        failed_count = sum(1 for r in results if r.is_approved_in_exercise == False)

        # Valores
        values = [r.measured_value for r in results if r.is_valid]
        avg_value = sum(values) / len(values) if values else None
        best_value = max(values) if values else None
        worst_value = min(values) if values else None

        exercises_summary.append(ExerciseSummary(
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            unit_of_measure=exercise.unit_of_measure,
            total_candidates=total_candidates,
            candidates_completed=unique_candidates,
            candidates_approved=approved_count,
            candidates_failed=failed_count,
            average_value=avg_value,
            best_value=best_value,
            worst_value=worst_value,
            approval_rate=(approved_count / unique_candidates * 100) if unique_candidates > 0 else 0
        ))

    return EventResultsSummary(
        event_id=event_id,
        event_name=event.name,
        event_date=str(event.date_start),
        location=event.location,
        total_candidates=total_candidates,
        total_exercises=total_exercises,
        candidates_approved=approved,
        candidates_failed=failed,
        candidates_in_progress=in_progress,
        approval_rate=approval_rate,
        completion_rate=completion_rate,
        exercises_summary=exercises_summary
    )


# =============================================================================
# ROTAS DE GERAÇÃO DE PDF
# =============================================================================

@router.api_route("/candidate/{candidate_id}/pdf", methods=["GET", "POST"])
def generate_candidate_pdf_endpoint(
    candidate_id: int,
    event_id: int,
    coordinator_name: Optional[str] = None,
    db: Session = Depends(get_tenant_db_session)
):
    """Gera PDF individual do candidato (inclui coordenador/CREF/assinatura se disponível)."""
    from sqlalchemy import text
    import io
    import logging
    from datetime import date, datetime

    logger = logging.getLogger(__name__)

    # Busca candidato e evento
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # Busca exercícios do evento e resultados do candidato
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()
    exercises_results: List[Dict] = []

    for exercise in exercises:
        results = db.query(ExecutionResult).filter(
            and_(
                ExecutionResult.candidate_id == candidate_id,
                ExecutionResult.exercise_id == exercise.id
            )
        ).all()

        if not results:
            continue

        # Seleciona melhor resultado (menor para tempo, maior caso contrário)
        unit = (exercise.unit_of_measure or "").lower()
        if 'tempo' in unit:
            best = min(results, key=lambda r: getattr(r, "measured_value", None) or 0)
        else:
            best = max(results, key=lambda r: getattr(r, "measured_value", None) or 0)

        exercises_results.append({
            'exercise_name': exercise.name,
            'unit_of_measure': exercise.unit_of_measure,
            'best_value': getattr(best, "measured_value", None),
            'is_approved': getattr(best, "is_approved_in_exercise", None)
        })

    # Determina status geral do candidato
    if len(exercises_results) == len(exercises) and len(exercises) > 0:
        all_approved = all(e.get('is_approved') for e in exercises_results)
        overall_status = 'approved' if all_approved else 'failed'
    else:
        overall_status = 'in_progress'

    # Monta dados do candidato e do evento para o PDF
    start_time = getattr(candidate, 'start_time', None) or getattr(candidate, 'batch_start_time', None)
    start_date_obj = getattr(candidate, 'start_date', None) or getattr(candidate, 'batch_date', None)
    if isinstance(start_date_obj, (date, datetime)):
        start_date = start_date_obj.isoformat()
    else:
        start_date = str(start_date_obj) if start_date_obj is not None else None

    candidate_data = {
        'full_name': candidate.full_name,
        'cpf': candidate.cpf,
        'registration_number': candidate.registration_number,
        'gender': candidate.gender,
        'batch_name': candidate.batch_name,
        'batch_number': getattr(candidate, 'batch_number', None),
        'start_time': start_time,
        'start_date': start_date,
        'overall_status': overall_status
    }

    event_data = {
        'name': event.name,
        'date': str(event.date_start),
        'location': event.location
    }

    # ---------------------------
    # Resolver company_name / company_logo_path
    # ---------------------------
    company_name = os.environ.get('COMPANY_NAME') or None
    company_logo_path = os.environ.get('COMPANY_LOGO_PATH') or None

    if not company_name:
        company_name = getattr(event, 'company_name', None) or getattr(event, 'organization', None) or getattr(event, 'organizer_name', None)

    if not company_logo_path:
        company_logo_path = getattr(event, 'company_logo', None) or getattr(event, 'logo_url', None) or getattr(event, 'logo', None)

    tenant_info = None
    try:
        sp = db.execute(text("SHOW search_path")).fetchone()
        schema_name = None
        if sp and sp[0]:
            schema_name = sp[0].split(',')[0].strip().strip('"')

        if schema_name:
            db.execute(text("SET search_path TO public"))
            try:
                from app.db.models.public import Tenant
                tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
                if tenant:
                    tenant_info = tenant
                    if not company_name:
                        company_name = getattr(tenant, 'nome_empresa', None) or getattr(tenant, 'name', None)
                    if not company_logo_path:
                        company_logo_path = getattr(tenant, 'logo_url', None) or getattr(tenant, 'logo', None)
            finally:
                if schema_name:
                    db.execute(text(f'SET search_path TO "{schema_name}"'))
    except Exception:
        logger.exception("Erro ao tentar extrair Tenant do schema public para cabeçalho do PDF")

    # ---------------------------
    # Resolver dados do COORDENADOR
    # - prioridade: event.coordinator_id -> ORM model (Coordinator) -> fallback SQL (user_tenant, users, etc.)
    # - também tenta campos diretos no event e no tenant
    # ---------------------------
    coord_name = None
    coord_cref = None
    coord_signature = None

    coord_id = getattr(event, "coordinator_id", None)

    if coord_id is not None:
        # tentativa via model (mantém compatibilidade se existir modelo Coordinator)
        try:
            Coordinator = None
            try:
                from app.db.models.tenant import Coordinator as CoordinatorModel
                Coordinator = CoordinatorModel
            except Exception:
                try:
                    from app.db.models.public import Coordinator as CoordinatorModel
                    Coordinator = CoordinatorModel
                except Exception:
                    try:
                        from app.db.models import Coordinator as CoordinatorModel
                        Coordinator = CoordinatorModel
                    except Exception:
                        Coordinator = None

            if Coordinator is not None:
                coord_obj = db.query(Coordinator).filter(Coordinator.id == coord_id).first()
                if coord_obj:
                    coord_name = getattr(coord_obj, "full_name", None) or getattr(coord_obj, "name", None) or getattr(coord_obj, "nome", None)
                    coord_cref = getattr(coord_obj, "cref", None) or getattr(coord_obj, "CREF", None)
                    coord_signature = getattr(coord_obj, "signature_url", None) or getattr(coord_obj, "assinatura_url", None) or getattr(coord_obj, "signature", None)
        except Exception:
            logger.exception("Erro ao buscar Coordinator por coordinator_id=%r", coord_id)

    # Fallback robusto: tenta tabelas comuns por SQL (inclui user_tenant) e usa mapping seguro
    if not coord_name and coord_id is not None:
        table_candidates = ['user_tenant', 'user', 'users', 'users_tenant', 'person', 'people', 'staff', 'employee', 'coordinator']
        for tbl in table_candidates:
            try:
                q = text(f"SELECT * FROM {tbl} WHERE id = :id LIMIT 1")
                row = db.execute(q, {"id": coord_id}).fetchone()
                if not row:
                    continue

                # normalize a row para mapping case-insensitive
                mapping = {}
                if hasattr(row, "_mapping"):  # sqlalchemy Row object
                    for k, v in row._mapping.items():
                        mapping[k.lower()] = v
                elif hasattr(row, "keys"):
                    # keys() may return column names
                    for idx, k in enumerate(row.keys()):
                        try:
                            mapping[k.lower()] = row[idx]
                        except Exception:
                            mapping[k.lower()] = None
                else:
                    # fallback: try to convert tuple to dict by common positions (not ideal)
                    # we will attempt minimal extraction below
                    mapping = {}

                # tenta nomes de coluna preferidos explicitamente
                name_candidates = ['nome', 'full_name', 'name', 'first_name', 'username', 'email']
                name_val = None
                for nm in name_candidates:
                    if nm in mapping and mapping[nm]:
                        name_val = mapping[nm]
                        break

                # se não tem, tenta combinar first_name + last_name
                if not name_val:
                    fn = mapping.get('first_name') or mapping.get('firstname')
                    ln = mapping.get('last_name') or mapping.get('lastname') or mapping.get('surname')
                    if fn or ln:
                        name_val = " ".join(filter(None, [fn, ln]))

                cref_candidates = ['cref', 'CREF', 'cref_number', 'cref_no']
                cref_val = None
                for cm in cref_candidates:
                    if cm.lower() in mapping and mapping[cm.lower()]:
                        cref_val = mapping[cm.lower()]
                        break

                sig_candidates = ['signature_url', 'assinatura_url', 'signature', 'assinatura', 'signature_path', 'avatar_url']
                sig_val = None
                for sm in sig_candidates:
                    if sm.lower() in mapping and mapping[sm.lower()]:
                        sig_val = mapping[sm.lower()]
                        break

                # if mapping is empty (could be tuple), try positional fallback (best-effort)
                if not name_val:
                    try:
                        if len(row) >= 2:
                            name_val = row[1]
                        if len(row) >= 3 and not cref_val:
                            # try second/third position heuristics
                            possible = row[2]
                            # if looks like cref (has digit and '/'), prefer it else ignore
                            if possible and isinstance(possible, str) and any(ch.isdigit() for ch in possible):
                                cref_val = possible
                        if len(row) >= 4 and not sig_val:
                            sig_val = row[3]
                    except Exception:
                        pass

                if name_val:
                    coord_name = str(name_val) if name_val is not None else None
                    coord_cref = str(cref_val) if cref_val is not None else None
                    coord_signature = str(sig_val) if sig_val is not None else None
                    logger.debug("Resolved coordinator via raw SQL table=%s id=%s -> name=%r cref=%r signature=%r", tbl, coord_id, coord_name, coord_cref, coord_signature)
                    break
            except Exception:
                continue

    # Se não encontrou via coordinator_id, tenta campos diretos no event (ou parâmetro coordinator_name)
    if not coord_name:
        coord_name = coordinator_name or getattr(event, 'coordinator_name', None) or getattr(event, 'coordenador', None)
    if not coord_cref:
        coord_cref = getattr(event, 'coordinator_cref', None) or getattr(event, 'coordenador_cref', None)
    if not coord_signature:
        coord_signature = getattr(event, 'coordinator_signature_url', None) or getattr(event, 'coordinator_signature', None)

    # Se ainda não achou, tenta extrair do tenant (se disponível)
    if tenant_info:
        if not coord_name:
            coord_name = getattr(tenant_info, 'coordenador_nome', None) or getattr(tenant_info, 'coordinator_name', None)
        if not coord_cref:
            coord_cref = getattr(tenant_info, 'coordenador_cref', None) or getattr(tenant_info, 'coordinator_cref', None)
        if not coord_signature:
            coord_signature = getattr(tenant_info, 'coordenador_signature_url', None) or getattr(tenant_info, 'coordinator_signature_url', None) or getattr(tenant_info, 'assinatura_url', None)

    # A tabela normalmente existe no schema do tenant (search_path já está ajustado pelo get_tenant_db_session)
    if not coord_signature and coord_id is not None:
        try:
            # use dynamic schema for attendance table lookup
            schema = None
            try:
                sp = db.execute(text("SHOW search_path")).fetchone()
                if sp and sp[0]:
                    schema = sp[0].split(',')[0].strip().strip('"')
            except Exception:
                schema = None

            if schema:
                table_full = f'"{schema}".event_worker_attendance'
            else:
                table_full = 'event_worker_attendance'

            q = text(f"""
                SELECT check_in_signature_path
                FROM {table_full}
                WHERE event_id = :event_id
                  AND (user_id = :coord_id OR event_worker_id = :coord_id)
                  AND check_in_signature_path IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = db.execute(q, {"event_id": event_id, "coord_id": coord_id}).fetchone()
            if row and row[0]:
                coord_signature = str(row[0])
                logger.info("Found coordinator signature from attendance table: %s", coord_signature)
        except Exception:
            logger.exception("Error querying event_worker_attendance for coordinator signature (event=%r coord_id=%r)", event_id, coord_id)

    # sanitize coordinator signature: ignore obvious avatars or thumbnails
    if coord_signature and isinstance(coord_signature, str):
        try:
            original_sig = coord_signature
            # 1) Tentar helper do gerador (pode resolver URLs e paths temporários)
            try:
                from app.utils.pdf_generator import _resolve_logo_path
                resolved, is_temp = _resolve_logo_path(coord_signature)
                if resolved and isinstance(resolved, str) and os.path.exists(resolved):
                    coord_signature = resolved
                    logger.info("[SIGNATURE RESOLVE] helper resolved %r -> %r (temp=%s)", original_sig, resolved, is_temp)
                else:
                    logger.debug("[SIGNATURE RESOLVE] helper did not return an existing file for %r -> %r", original_sig, resolved)
            except Exception:
                logger.debug("Signature helper _resolve_logo_path not available or failed for %r", coord_signature, exc_info=True)

            # ---------- avatar -> apenas tentativa segura por DB (sem fallback global por filesystem) ----------
            try:
                sig_lc = (coord_signature or "").lower()

                # se o valor atual parece um avatar (avatar, /avatars/, thumb, avatar_) então tentamos achar a assinatura correta via DB no schema atual
                if sig_lc and ('avatar' in sig_lc or '/avatars/' in sig_lc or 'avatar_' in sig_lc or 'thumb' in sig_lc):
                    try:
                        # determine schema
                        schema = None
                        try:
                            sp = db.execute(text("SHOW search_path")).fetchone()
                            if sp and sp[0]:
                                schema = sp[0].split(',')[0].strip().strip('"')
                        except Exception:
                            schema = None

                        if coord_id is not None:
                            if schema:
                                table_full = f'"{schema}".event_worker_attendance'
                            else:
                                table_full = 'event_worker_attendance'

                            q = text(f"""
                                SELECT check_in_signature_path
                                FROM {table_full}
                                WHERE event_id = :event_id
                                  AND (user_id = :coord_id OR event_worker_id = :coord_id)
                                  AND check_in_signature_path IS NOT NULL
                                ORDER BY created_at DESC
                                LIMIT 1
                            """)
                            row_att = db.execute(q, {"event_id": event_id, "coord_id": coord_id}).fetchone()
                            if row_att and row_att[0]:
                                coord_signature = str(row_att[0])
                                logger.info("[SIGNATURE RESOLVE] found attendance signature in DB for schema=%s coord_id=%s -> %s", schema or '<default>', coord_id, coord_signature)
                                try:
                                    resolved2, is_temp2 = _resolve_logo_path(coord_signature)
                                    if resolved2 and os.path.exists(resolved2):
                                        coord_signature = resolved2
                                        logger.info("[SIGNATURE RESOLVE] resolved DB attendance path -> %r (temp=%s)", coord_signature, is_temp2)
                                except Exception:
                                    logger.debug("Could not resolve DB attendance signature with helper for %r", coord_signature, exc_info=True)
                            else:
                                logger.info("[SIGNATURE RESOLVE] no attendance signature record in DB for schema=%s event=%s coord=%s; skipping filesystem fallback", schema or '<default>', event_id, coord_id)
                    except Exception:
                        logger.exception("Error querying event_worker_attendance while attempting coordinator-specific fallback (event=%r coord=%r)", event_id, coord_id)
            except Exception:
                logger.exception("Unexpected error in avatar->attendance_sig DB fallback")
            # -----------------------------------------------------------------------------------------------

            # 2) Se ainda não resolvido, tentar prefixos comuns (priorizando /app/uploads, que é onde seus arquivos estão)
            if not (coord_signature and os.path.exists(coord_signature)):
                candidates = []
                # adicionar formas tal como o DB pode conter
                candidates.append(original_sig)                                   # como veio do DB
                candidates.append(original_sig.lstrip('/'))                       # sem leading slash
                # prefixos óbvios para o container
                candidates.append(os.path.join('/app/uploads', original_sig.lstrip('/')))
                candidates.append(os.path.join('/app/uploads', 'signatures', original_sig.lstrip('/')))
                candidates.append(os.path.join('/app/uploads', 'signatures', original_sig.split('/', 1)[-1] if '/' in original_sig else original_sig))
                candidates.append(os.path.join('/uploads', original_sig.lstrip('/')))
                candidates.append(os.path.join(os.getcwd(), original_sig.lstrip('/')))
                candidates.append(os.path.join(os.getcwd(), 'backend', 'app', original_sig.lstrip('/')))
                candidates.append(os.path.join(os.getcwd(), 'backend', 'app', 'static', original_sig.lstrip('/')))
                # retirar duplicações e testar cada candidato
                seen = set()
                for c in candidates:
                    if not c:
                        continue
                    norm = os.path.normpath(c)
                    if norm in seen:
                        continue
                    seen.add(norm)
                    try:
                        if os.path.exists(norm):
                            coord_signature = norm
                            logger.info("[SIGNATURE RESOLVE] found signature for %r -> %s", original_sig, coord_signature)
                            break
                    except Exception:
                        continue

            # 3) Log final do resultado de resolução
            if coord_signature and os.path.exists(coord_signature):
                logger.info("[SIGNATURE RESOLVE] final resolved signature: %r", coord_signature)
            else:
                logger.info("[SIGNATURE RESOLVE] could not resolve signature for %r (tried helper & common prefixes)", original_sig)
        except Exception:
            logger.exception("Unexpected error while trying to resolve coordinator signature path (original=%r)", coord_signature)

    logger.info("[PDF CANDIDATO] resolved company_name=%r company_logo=%r coord_id=%r coord_name=%r coord_cref=%r coord_sig=%r",
                company_name, company_logo_path, coord_id, coord_name, coord_cref, coord_signature)

    # Gera PDF passando as infos do coordenador e da empresa (o gerador trata resolução/cleanup da assinatura)
    pdf_bytes = generate_candidate_pdf(
        candidate_data=candidate_data,
        exercises_results=exercises_results,
        event_data=event_data,
        signature_path=coord_signature,
        coordinator_name=coord_name,
        coordinator_cref=coord_cref,
        company_name=company_name,
        company_logo_path=company_logo_path
    )

    # Retorna como download
    safe_fname = f"resultado_{candidate.registration_number}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{safe_fname}"'}
    )

@router.get("/event/{event_id}/pdf-consolidated")
def generate_consolidated_pdf_endpoint(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Gera PDF consolidado com todos os resultados do evento"""
    from sqlalchemy import text
    logger = logging.getLogger(__name__)

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    candidates = db.query(Candidate).filter(Candidate.event_id == event_id).all()
    exercises = db.query(Exercise).filter(Exercise.event_id == event_id).all()

    # Monta lista de resultados
    candidates_results = []
    approved = 0
    failed = 0

    for candidate in candidates:
        results_count = db.query(func.count(func.distinct(ExecutionResult.exercise_id))).filter(
            ExecutionResult.candidate_id == candidate.id
        ).scalar()

        overall_status = 'in_progress'

        if results_count == len(exercises):
            approved_count = db.query(func.count(ExecutionResult.id)).filter(
                and_(
                    ExecutionResult.candidate_id == candidate.id,
                    ExecutionResult.is_approved_in_exercise == True
                )
            ).scalar()

            if approved_count == len(exercises):
                overall_status = 'approved'
                approved += 1
            else:
                overall_status = 'failed'
                failed += 1

        candidates_results.append({
            'full_name': candidate.full_name,
            'cpf': candidate.cpf,
            'gender': candidate.gender,
            'overall_status': overall_status,
            'registration_number': candidate.registration_number
        })

    event_data = {
        'name': event.name,
        'date': str(event.date_start),
        'location': event.location
    }

    summary = {
        'total_candidates': len(candidates),
        'approved': approved,
        'failed': failed,
        'approval_rate': (approved / len(candidates) * 100) if candidates else 0
    }

    # Ordena alfabeticamente (accent-insensitive) por nome completo
    candidates_results.sort(key=lambda c: normalize_for_sort(c.get('full_name', '')))

    # -------------------------------------------------------
    # Determinar company_name e company_logo_path (robusto)
    # (mantive a lógica existente — não alterei aqui)
    # -------------------------------------------------------
    company_name = os.environ.get('COMPANY_NAME') or None
    company_logo_path = os.environ.get('COMPANY_LOGO_PATH') or None

    if not company_name:
        company_name = getattr(event, 'company_name', None) or getattr(event, 'organization', None) or getattr(event, 'organizer_name', None)

    if not company_logo_path:
        company_logo_path = getattr(event, 'company_logo', None) or getattr(event, 'logo_url', None) or getattr(event, 'logo', None)

    tenant_info = None
    try:
        sp = db.execute(text("SHOW search_path")).fetchone()
        schema_name = None
        if sp and sp[0]:
            schema_name = sp[0].split(',')[0].strip().strip('"')

        if schema_name:
            db.execute(text("SET search_path TO public"))
            try:
                from app.db.models.public import Tenant
                tenant = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
                if tenant:
                    tenant_info = tenant
                    if not company_name:
                        company_name = getattr(tenant, 'nome_empresa', None) or getattr(tenant, 'name', None)
                    if not company_logo_path:
                        company_logo_path = getattr(tenant, 'logo_url', None) or getattr(tenant, 'logo', None)
            finally:
                if schema_name:
                    db.execute(text(f'SET search_path TO "{schema_name}"'))
    except Exception:
        logger.exception("Erro ao tentar extrair Tenant do schema public para cabeçalho do PDF")

    logger.info("[PDF CONSOLIDADO] resolved company_name=%r company_logo_path=%r tenant=%r event_name=%r",
                company_name, company_logo_path, getattr(tenant_info, 'schema_name', None) if tenant_info else None, event.name)

    # --- Gera PDF (passando company info) ---
    pdf_bytes = generate_consolidated_report_pdf(
        event_data=event_data,
        candidates_results=candidates_results,
        summary=summary,
        company_name=company_name,
        company_logo_path=company_logo_path
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="resultado_consolidado_{event.name.replace(" ", "_")}.pdf"'
        }
    )

@router.post("/event/{event_id}/fichas/pdf", status_code=202)
def create_fichas_job(event_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_tenant_db_session)):
    """
    Cria job para gerar PDF com todas as fichas. Retorna job_id e URLs para status/download.
    """
    job_id = str(uuid.uuid4())
    _write_job_status(job_id, "pending", {})
    # try to create a fresh DB session for background job
    sess = None
    sess_gen = None
    try:
        if hasattr(get_tenant_db_session, '__wrapped__'):
            # get_tenant_db_session() -> generator; obter a primeira session
            sess_gen = get_tenant_db_session()
            sess = next(sess_gen)
        else:
            # fallback: chamar e tentar extrair gen
            possible = get_tenant_db_session()
            try:
                sess = next(possible)
                sess_gen = possible
            except Exception:
                sess = db
    except Exception:
        sess = db
    background_tasks.add_task(_generate_all_fichas_job, job_id, event_id, sess)
    return {
        "job_id": job_id,
        "status_url": f"/taf/results/fichas/{job_id}/status",
        "download_url": f"/taf/results/fichas/{job_id}/download"
    }

@router.get("/fichas/{job_id}/status")
def get_fichas_job_status(job_id: str):
    s = _read_job_status(job_id)
    if not s:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return s

@router.get("/fichas/{job_id}/download")
def download_fichas_job(job_id: str):
    s = _read_job_status(job_id)
    if not s:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if s.get("status") != "done":
        raise HTTPException(status_code=409, detail="Job não ready")
    out_path = _job_output_path(job_id)
    if not out_path.exists():
        raise HTTPException(status_code=404, detail="Output not found")
    return FileResponse(str(out_path), media_type="application/pdf", filename=f"fichas_event_{job_id}.pdf")

