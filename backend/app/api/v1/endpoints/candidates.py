# -*- coding: utf-8 -*-
# backend/app/api/v1/endpoints/candidates.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy import func, or_

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
    
    for idx, candidate_data in enumerate(bulk_data.candidates, start=1):
        try:
            # ⚠️ MUDANÇA: Validação de CPF agora é um WARNING, não um ERROR bloqueante
            cpf_valid = validate_cpf(candidate_data.cpf)
            if not cpf_valid:
                # Adiciona WARNING mas NÃO bloqueia a importação
                result.errors.append({
                    'row_number': idx,
                    'field': 'cpf',
                    'error': f'⚠️ AVISO: CPF {candidate_data.cpf} não passou na validação matemática. Importado mesmo assim.'
                })
                logger.warning(f"⚠️  Linha {idx}: CPF suspeito mas importado - {candidate_data.cpf}")
                # NÃO fazemos continue aqui - candidato será importado!
            
            # Verifica duplicidade
            existing = db.query(Candidate).filter(
                Candidate.event_id == bulk_data.event_id,
                Candidate.cpf == candidate_data.cpf
            ).first()
            
            if existing:
                if bulk_data.skip_duplicates:
                    result.rows_skipped += 1
                    logger.info(f"⏭️  Linha {idx}: CPF duplicado ignorado - {candidate_data.cpf}")
                    continue
                else:
                    result.rows_failed += 1
                    result.errors.append({
                        'row_number': idx,
                        'field': 'cpf',
                        'error': f'CPF {candidate_data.cpf} já existe'
                    })
                    logger.warning(f"❌ Linha {idx}: CPF duplicado - {candidate_data.cpf}")
                    continue
            
            # Cria o candidato (mesmo com CPF "inválido")
            db_candidate = Candidate(
                event_id=bulk_data.event_id,
                **candidate_data.model_dump()
            )
            
            db.add(db_candidate)
            result.rows_imported += 1
            logger.debug(f"✅ Linha {idx}: Candidato adicionado - {candidate_data.full_name}")
            
        except Exception as e:
            result.rows_failed += 1
            result.errors.append({
                'row_number': idx,
                'field': 'general',
                'error': str(e)
            })
            logger.error(f"❌ Linha {idx}: Erro - {e}")
    
    try:
        db.commit()
        result.success = True
        
        # Mensagem incluindo avisos sobre CPFs suspeitos
        warnings_count = len([e for e in result.errors if 'AVISO' in str(e.get('error', ''))])
        
        result.message = f"Importação concluída: {result.rows_imported} candidatos importados"
        if result.rows_skipped > 0:
            result.message += f", {result.rows_skipped} duplicados ignorados"
        if warnings_count > 0:
            result.message += f", {warnings_count} CPFs com formato suspeito (importados mesmo assim)"
        if result.rows_failed > 0:
            result.message += f", {result.rows_failed} erros"
        result.message += ".";
        
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
    # Busca todos os candidatos do evento
    candidates = db.query(Candidate).filter(
        Candidate.event_id == config.event_id
    ).all()
    
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum candidato encontrado para este evento."
        )
    
    # Converte para CandidateOut
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
    
    # Executa o algoritmo de agrupamento
    groups = group_candidates(candidate_list, config)
    
    return GroupingResult(
        event_id=config.event_id,
        total_candidates=len(candidates),
        total_groups=len(groups),
        groups=groups,
        config=config
    )


@router.post("/apply-grouping/{event_id}", status_code=status.HTTP_200_OK)
def apply_grouping_to_candidates(
    event_id: int,
    result: GroupingResult,
    db: Session = Depends(get_tenant_db_session)
):
    """Aplica o agrupamento ao banco de dados, atualizando batch_name, batch_number e start_time dos candidatos."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        for group in result.groups:
            logger.info(f"📝 Aplicando turma '{group.name}' com {len(group.candidates)} candidatos (horário: {group.start_time})")
            
            for candidate in group.candidates:
                db_candidate = db.query(Candidate).filter(Candidate.id == candidate.id).first()
                if db_candidate:
                    db_candidate.batch_name = group.name
                    db_candidate.batch_number = candidate.batch_number
                    db_candidate.start_time = group.start_time  # ✅ NOVO: Salva horário no banco
                    
                    logger.debug(f"  ✅ Candidato {candidate.batch_number} - {candidate.full_name} → Horário: {group.start_time}")
        
        db.commit()
        logger.info(f"✅ Agrupamento aplicado com sucesso! {result.total_groups} turmas criadas.")
        
        return {
            "message": f"Agrupamento aplicado com sucesso! {result.total_groups} turmas criadas.",
            "total_groups": result.total_groups,
            "total_candidates": result.total_candidates
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao aplicar agrupamento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao aplicar agrupamento: {e}"
        )


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