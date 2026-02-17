# backend/app/api/v1/endpoints/events_taf.py
# atualizado para suportar event_dates explícitas (versão com logs para debug)
# + endpoint adicional: GET /{event_id}/users -> lista usuários vinculados ao evento
# Hotfix: create_event/update_event retornam JSONResponse seguro para evitar 500 pós-commit
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func, or_, text
from datetime import timedelta, datetime, date
import logging

# 1. Dependência de Multi-Tenancy (Obriga a sessão a ser isolada)
from app.api.deps_tenant import get_tenant_db_session 

# 2. Modelos e Schemas
from app.db.models.tenant import Event, EventDate, Exercise, Candidate, UserTenant, ExerciseEvaluator, EventWorker
from app.schemas.event_schema import EventCreate, EventUpdate, EventOut, EventList

router = APIRouter(tags=["TAF - Módulo 1: Eventos"])

logger = logging.getLogger(__name__)


# -----------------------
# Helpers
# -----------------------
def _date_to_iso(d: Any) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, str):
        return d
    if isinstance(d, (datetime, date)):
        return d.isoformat()
    # fallback try
    try:
        return str(d)
    except Exception:
        return None


def _normalize_event_dates(raw: Any) -> List[str]:
    """
    raw can be:
      - a list of date objects
      - a list of strings 'YYYY-MM-DD'
      - None
    Return list of ISO date strings.
    """
    if not raw:
        return []
    out = []
    for d in raw:
        if d is None:
            continue
        if isinstance(d, (date, datetime)):
            out.append(d.isoformat())
        elif isinstance(d, str):
            out.append(d)
        else:
            try:
                out.append(str(d))
            except Exception:
                continue
    # remove duplicates and sort
    uniq = sorted(set(out))
    return uniq


def _safe_event_dict(ev: Any) -> Dict[str, Any]:
    """
    Build a safe JSON-serializable representation of Event object ev.
    Access attributes defensively to avoid raising exceptions during serialization.
    """
    try:
        # prefer pre-computed event_dates (ev.event_dates) otherwise try ev.dates
        raw_dates = getattr(ev, "event_dates", None)
        if raw_dates is None:
            # try relationship 'dates' that contains EventDate objects
            raw_dates = [getattr(ed, "date", None) for ed in getattr(ev, "dates", [])] if getattr(ev, "dates", None) else []
        event_dates = _normalize_event_dates(raw_dates)
    except Exception:
        logger.exception("[_safe_event_dict] erro ao normalizar event_dates")
        event_dates = []

    try:
        coordinator_id = getattr(ev, "coordinator_id", None)
    except Exception:
        coordinator_id = None

    try:
        # coordinator_name may be a relationship field
        coordinator_name = None
        coord = getattr(ev, "coordinator", None)
        if coord:
            coordinator_name = getattr(coord, "nome", None) or getattr(coord, "full_name", None) or getattr(coord, "name", None)
    except Exception:
        coordinator_name = None

    try:
        total_exercises = getattr(ev, "total_exercises", None)
        if total_exercises is None:
            total_exercises = 0
    except Exception:
        total_exercises = 0

    try:
        total_candidates = getattr(ev, "total_candidates", None)
        if total_candidates is None:
            total_candidates = 0
    except Exception:
        total_candidates = 0

    resp = {
        "id": getattr(ev, "id", None),
        "name": getattr(ev, "name", None),
        "date_start": _date_to_iso(getattr(ev, "date_start", None)),
        "date_end": _date_to_iso(getattr(ev, "date_end", None)),
        "location": getattr(ev, "location", None),
        "is_active": getattr(ev, "is_active", None),
        "total_exercises": total_exercises,
        "total_candidates": total_candidates,
        "event_dates": event_dates,
        "coordinator_id": coordinator_id,
        "coordinator_name": coordinator_name,
    }
    # include other commonly used fields if present
    for fld in ("description", "notes", "created_at", "updated_at"):
        if hasattr(ev, fld):
            try:
                resp[fld] = _date_to_iso(getattr(ev, fld))
            except Exception:
                resp[fld] = None
    return resp


# Debug-friendly sync_event_dates
def sync_event_dates(db: Session, event_id: int, dates: List):
    """
    Debug-friendly: sincroniza as datas do evento no schema da sessão atual.
    - dates: lista de strings 'YYYY-MM-DD' ou date objects.
    Retorna o número de linhas inseridas.
    """
    inserted = 0
    try:
        # 1) Log current search_path / schema
        try:
            cur = db.execute(text("SHOW search_path")).fetchone()
            logger.info(f"🔎 current search_path before syncing event_dates: {cur}")
        except Exception as e:
            logger.warning(f"⚠️ Não consegui ler search_path: {e}")

        # 2) Normalize dates -> set único e ordenado
        normalized = set()
        for d in dates or []:
            if d is None:
                continue
            if isinstance(d, str):
                s = d.strip()
                # aceita formatos YYYY-MM-DD
                try:
                    from datetime import datetime as _dt
                    d_obj = _dt.strptime(s, "%Y-%m-%d").date()
                except Exception:
                    logger.warning(f"⚠️ Ignorando data inválida: {s}")
                    continue
            else:
                # assume objeto date-like
                d_obj = d
            normalized.add(d_obj)

        norm_list = sorted(normalized)

        logger.info(f"ℹ️ Sincronizando {len(norm_list)} datas para event_id={event_id}: {norm_list}")

        # 3) Delete existing rows for event in current schema
        db.query(EventDate).filter(EventDate.event_id == event_id).delete()
        db.flush()

        # 4) Insert new rows
        for d_obj in norm_list:
            row = EventDate(event_id=event_id, date=d_obj)
            db.add(row)
            inserted += 1

        # flush to execute SQL statements (without committing)
        try:
            db.flush()
            logger.info(f"✅ Flush OK — {inserted} rows prepared for insert into event_dates.")
        except Exception as e:
            logger.exception(f"❌ Erro no db.flush() ao inserir event_dates: {e}")
            # let caller see commit failure
    except Exception as e:
        logger.exception(f"❌ Erro ao sincronizar event_dates: {e}")
    return inserted


@router.get("/coordinators", response_model=List[dict])
def list_coordinators(
    search: Optional[str] = Query(None, description="Filtro por nome ou email"),
    include_inactive: Optional[bool] = Query(False, description="Incluir usuários inativos?"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de resultados"),
    db: Session = Depends(get_tenant_db_session)
):
    """
    Retorna os usuários do tenant com role_id = 3 (coordenadores).
    O router events_taf está montado em /taf/events, então a URL final será:
      GET /taf/events/coordinators
    """
    try:
        q = db.query(UserTenant.id, UserTenant.nome, UserTenant.email).filter(UserTenant.role_id == 3)
        if not include_inactive:
            q = q.filter(UserTenant.is_active == True)
        if search:
            like = f"%{search}%"
            q = q.filter(or_(UserTenant.nome.ilike(like), UserTenant.email.ilike(like)))
        rows = q.order_by(UserTenant.nome).limit(limit).all()

        result = []
        for r in rows:
            result.append({
                "id": getattr(r, "id", None),
                "nome": getattr(r, "nome", None),
                "email": getattr(r, "email", None)
            })
        return result
    except Exception as e:
        logger.exception("[events_taf.list_coordinators] Erro ao listar coordenadores")
        raise HTTPException(status_code=500, detail=f"Erro ao listar coordenadores: {e}")


# -----------------------------------------------------------
# Rotas CRUD de Eventos
# -----------------------------------------------------------

@router.post("/", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Cria um novo Concurso/Evento dentro do Schema do Cliente.
    """
    # Log diagnóstico do search_path and payload (temporário)
    try:
        cur_sp = db.execute(text("SHOW search_path")).fetchone()
        logger.info(f"[DEBUG create_event] search_path={cur_sp}")
    except Exception:
        logger.exception("[DEBUG create_event] não consegui ler search_path")

    try:
        logger.debug(f"[DEBUG create_event] payload summary: {event_in.model_dump(exclude={'event_dates'})}")
    except Exception:
        logger.debug("[DEBUG create_event] não foi possível serializar payload para debug")

    # Validação de datas (quando fornecidas no payload base)
    if event_in.date_start > event_in.date_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data de início deve ser anterior à data de término."
        )

    # Se vier coordinator_id no payload, validar existência no tenant atual
    if getattr(event_in, "coordinator_id", None):
        coord_row = db.query(UserTenant).filter(UserTenant.id == event_in.coordinator_id).first()
        if not coord_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="coordinator_id inválido (usuário não encontrado no tenant atual).")
    
    db_event = Event(**event_in.model_dump(exclude={'event_dates'}))
    
    try:
        db.add(db_event)
        db.flush()  # para obter db_event.id sem commitar ainda

        # Se o payload trouxe event_dates explícitas, persiste-as
        if event_in.event_dates:
            sync_event_dates(db, db_event.id, event_in.event_dates)
        else:
            # Compatibilidade: popular a partir do intervalo date_start..date_end
            if db_event.date_start and db_event.date_end:
                days = []
                delta_days = (db_event.date_end - db_event.date_start).days
                for i in range(delta_days + 1):
                    days.append(db_event.date_start + timedelta(days=i))
                sync_event_dates(db, db_event.id, days)

        db.commit()
        db.refresh(db_event)

        # --- SAFETY: pós-processamento protegido para evitar 500 mesmo que algo falhe ---
        try:
            # Contagens e event_dates
            db_event.total_exercises = db.query(func.count(Exercise.id)).filter(Exercise.event_id == db_event.id).scalar() or 0
            db_event.total_candidates = db.query(func.count(Candidate.id)).filter(Candidate.event_id == db_event.id).scalar() or 0
            db_event.event_dates = [ed.date for ed in db_event.dates] if getattr(db_event, "dates", None) else []

            # Nome do coordenador (protege internamente caso falhe)
            try:
                db_event.coordinator_name = db_event.coordinator.nome if getattr(db_event, "coordinator", None) else None
            except Exception:
                db_event.coordinator_name = None

        except Exception:
            logger.exception("[create_event] pós-processamento falhou, mas evento já foi salvo. Retornando com valores fallback.")
            db_event.total_exercises = getattr(db_event, "total_exercises", 0)
            db_event.total_candidates = getattr(db_event, "total_candidates", 0)
            db_event.event_dates = getattr(db_event, "event_dates", [])
            db_event.coordinator_name = getattr(db_event, "coordinator_name", None)

        # Retornar resposta segura como JSON (hotfix para evitar erros de serialização)
        try:
            return JSONResponse(status_code=status.HTTP_201_CREATED, content=_safe_event_dict(db_event))
        except Exception:
            logger.exception("[create_event] erro ao montar resposta segura")
            return JSONResponse(status_code=status.HTTP_201_CREATED, content={"id": getattr(db_event, "id", None)})

    except Exception as e:
        # rollback defensivo
        try:
            db.rollback()
        except Exception:
            pass

        # tentativa de fallback: checar evento existente com mesmo nome/data
        try:
            existing = db.query(Event).filter(
                Event.name == event_in.name,
                Event.date_start == event_in.date_start
            ).first()
            if existing:
                existing.total_exercises = db.query(func.count(Exercise.id)).filter(Exercise.event_id == existing.id).scalar() or 0
                existing.total_candidates = db.query(func.count(Candidate.id)).filter(Candidate.event_id == existing.id).scalar() or 0
                existing.event_dates = [ed.date for ed in existing.dates] if getattr(existing, "dates", None) else []
                # preencher coordinator_name caso exista
                try:
                    existing.coordinator_name = existing.coordinator.nome if getattr(existing, "coordinator", None) else None
                except Exception:
                    existing.coordinator_name = None
                return JSONResponse(status_code=status.HTTP_201_CREATED, content=_safe_event_dict(existing))
        except Exception:
            pass

        logger.exception("[create_event] Erro ao criar evento")
        raise HTTPException(status_code=500, detail=f"Erro ao criar evento: {e}")


@router.get("/", response_model=EventList)
def list_events(
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(10, ge=1, le=100, description="Itens por página"),
    is_active: Optional[bool] = Query(None, description="Filtrar por status ativo/inativo"),
    search: Optional[str] = Query(None, description="Buscar por nome ou local"),
    db: Session = Depends(get_tenant_db_session)
):
    """
    Lista todos os Concursos/Eventos do Cliente com paginação e filtros.
    """
    query = db.query(Event)
    
    if is_active is not None:
        query = query.filter(Event.is_active == is_active)
    
    if search:
        query = query.filter(
            or_(
                Event.name.ilike(f"%{search}%"),
                Event.location.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    events = query.order_by(Event.date_start.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    for event in events:
        event.total_exercises = db.query(func.count(Exercise.id)).filter(Exercise.event_id == event.id).scalar() or 0
        event.total_candidates = db.query(func.count(Candidate.id)).filter(Candidate.event_id == event.id).scalar() or 0
        # Preenche event_dates para resposta
        event.event_dates = [ed.date for ed in event.dates] if getattr(event, "dates", None) else []
        # preencher nome do coordenador se relationship existir
        try:
            event.coordinator_name = event.coordinator.nome if getattr(event, "coordinator", None) else None
        except Exception:
            event.coordinator_name = None
    
    return EventList(
        items=events,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Busca um Evento específico pelo ID com estatísticas."""
    try:
        event = db.query(Event).filter(Event.id == event_id).one()
        
        event.total_exercises = db.query(func.count(Exercise.id)).filter(Exercise.event_id == event.id).scalar() or 0
        event.total_candidates = db.query(func.count(Candidate.id)).filter(Candidate.event_id == event.id).scalar() or 0
        event.event_dates = [ed.date for ed in event.dates] if getattr(event, "dates", None) else []

        # preencher nome do coordenador se relationship existir
        try:
            event.coordinator_name = event.coordinator.nome if getattr(event, "coordinator", None) else None
        except Exception:
            event.coordinator_name = None
        
        return event
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int,
    event_in: EventUpdate,
    db: Session = Depends(get_tenant_db_session)
):
    """Atualiza dados de um Evento existente."""
    # Log diagnóstico do search_path and payload (temporário)
    try:
        cur_sp = db.execute(text("SHOW search_path")).fetchone()
        logger.info(f"[DEBUG update_event] search_path={cur_sp}")
    except Exception:
        logger.exception("[DEBUG update_event] não consegui ler search_path")

    try:
        logger.debug(f"[DEBUG update_event] payload summary: {event_in.model_dump(exclude_unset=True)}")
    except Exception:
        logger.debug("[DEBUG update_event] não foi possível serializar payload para debug")

    try:
        event = db.query(Event).filter(Event.id == event_id).one()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    update_data = event_in.model_dump(exclude_unset=True)
    
    # Validação de datas se ambas forem fornecidas
    if 'date_start' in update_data and 'date_end' in update_data:
        if update_data['date_start'] > update_data['date_end']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A data de início deve ser anterior à data de término."
            )

    # Se o payload inclui coordinator_id, validar que o usuário existe no tenant atual
    if 'coordinator_id' in update_data and update_data.get('coordinator_id') is not None:
        coord_row = db.query(UserTenant).filter(UserTenant.id == update_data['coordinator_id']).first()
        if not coord_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="coordinator_id inválido (usuário não encontrado no tenant atual).")
    
    for key, value in update_data.items():
        # não setar event_dates diretamente aqui; tratamos abaixo
        if key == 'event_dates':
            continue
        setattr(event, key, value)

    try:
        db.add(event)
        db.flush()

        # Se vierem event_dates no payload, sincroniza explicitamente
        if 'event_dates' in update_data and update_data.get('event_dates') is not None:
            sync_event_dates(db, event.id, update_data['event_dates'])
        else:
            # Se data_start e data_end atualizadas (ou existentes) -> repopular event_dates automaticamente
            if getattr(event, 'date_start', None) and getattr(event, 'date_end', None):
                days = []
                delta_days = (event.date_end - event.date_start).days
                for i in range(delta_days + 1):
                    days.append(event.date_start + timedelta(days=i))
                sync_event_dates(db, event.id, days)
            # Caso contrário, mantém as event_dates atuais no DB

        db.commit()
        db.refresh(event)

        # --- SAFETY: pós-processamento protegido para evitar 500 mesmo que algo falhe ---
        try:
            event.total_exercises = db.query(func.count(Exercise.id)).filter(Exercise.event_id == event.id).scalar() or 0
            event.total_candidates = db.query(func.count(Candidate.id)).filter(Candidate.event_id == event.id).scalar() or 0
            event.event_dates = [ed.date for ed in event.dates] if getattr(event, "dates", None) else []

            try:
                event.coordinator_name = event.coordinator.nome if getattr(event, "coordinator", None) else None
            except Exception:
                event.coordinator_name = None

        except Exception:
            logger.exception("[update_event] pós-processamento falhou, mas evento já foi atualizado. Retornando com valores fallback.")
            event.total_exercises = getattr(event, "total_exercises", 0)
            event.total_candidates = getattr(event, "total_candidates", 0)
            event.event_dates = getattr(event, "event_dates", [])
            event.coordinator_name = getattr(event, "coordinator_name", None)

        # Retornar resposta segura como JSON (hotfix)
        try:
            return JSONResponse(status_code=status.HTTP_200_OK, content=_safe_event_dict(event))
        except Exception:
            logger.exception("[update_event] erro ao montar resposta segura")
            return JSONResponse(status_code=status.HTTP_200_OK, content={"id": getattr(event, "id", None)})

    except Exception as e:
        db.rollback()
        logger.exception("[update_event] Erro ao atualizar evento")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar evento: {e}")


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Deleta um Evento.
    """
    try:
        event = db.query(Event).filter(Event.id == event_id).one()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    
    try:
        db.delete(event)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar evento: {e}")


# -----------------------------------------------------------
# Novo endpoint: usuários vinculados a um evento
# -----------------------------------------------------------
@router.get("/{event_id}/users", response_model=List[dict])
def users_for_event(
    event_id: int,
    include_inactive: Optional[bool] = Query(False, description="Incluir usuários inativos?"),
    db: Session = Depends(get_tenant_db_session)
):
    """
    Retorna os usuários vinculados ao evento por meio de exercise_evaluators -> exercises.
    Retorna campos úteis: id, nome, username, email, cpf, phone, bank_name, pix, bank_account, agency, cref, role_id, custom_role, is_active
    """
    try:
        # Faz join: user_tenant <- exercise_evaluators <- exercises (filtrando por event_id)
        q = db.query(
            UserTenant.id, UserTenant.nome, UserTenant.username, UserTenant.email,
            UserTenant.cpf, UserTenant.phone, UserTenant.bank_name, UserTenant.pix,
            UserTenant.bank_account, UserTenant.agency, UserTenant.cref,
            UserTenant.role_id, UserTenant.custom_role, UserTenant.is_active
        ).distinct().join(
            ExerciseEvaluator, ExerciseEvaluator.evaluator_user_id == UserTenant.id
        ).join(
            Exercise, Exercise.id == ExerciseEvaluator.exercise_id
        ).filter(
            Exercise.event_id == event_id
        )

        if not include_inactive:
            q = q.filter(UserTenant.is_active == True)

        q = q.order_by(UserTenant.nome)
        rows = q.all()

        # Converte para lista de dicts (evita dependência direta com schemas)
        result = []
        for r in rows:
            # r can be a named tuple / Row; convert safely
            item = {
                "id": getattr(r, "id", None),
                "nome": getattr(r, "nome", None),
                "username": getattr(r, "username", None),
                "email": getattr(r, "email", None),
                "cpf": getattr(r, "cpf", None),
                "phone": getattr(r, "phone", None),
                "bank_name": getattr(r, "bank_name", None),
                "pix": getattr(r, "pix", None),
                "bank_account": getattr(r, "bank_account", None),
                "agency": getattr(r, "agency", None),
                "cref": getattr(r, "cref", None),
                "role_id": getattr(r, "role_id", None),
                "custom_role": getattr(r, "custom_role", None),
                "is_active": getattr(r, "is_active", None),
            }
            result.append(item)

        return result
    except Exception as e:
        logger.exception("[events_taf.users_for_event] Erro ao buscar usuários vinculados")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar usuários vinculados: {e}")


@router.get("/{event_id}/participants", response_model=List[dict])
def participants_for_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Retorna os participantes vinculados explicitamente ao evento (event_workers).
    Inclui dados do user (quando user_id presente).
    """
    try:
        q = db.query(
            EventWorker.id,
            EventWorker.event_id,
            EventWorker.user_id,
            EventWorker.role_id,
            EventWorker.role_name,
            EventWorker.days_assigned,
            EventWorker.created_at,
            UserTenant.nome, UserTenant.username, UserTenant.email,
            UserTenant.cpf, UserTenant.phone, UserTenant.bank_name, UserTenant.pix,
            UserTenant.bank_account, UserTenant.agency, UserTenant.cref
        ).outerjoin(UserTenant, UserTenant.id == EventWorker.user_id).filter(EventWorker.event_id == event_id).order_by(EventWorker.created_at.desc())

        rows = q.all()
        out = []
        for r in rows:
            out.append({
                "event_worker_id": getattr(r, "id", None),
                "event_id": getattr(r, "event_id", None),
                "user_id": getattr(r, "user_id", None),
                "role_id": getattr(r, "role_id", None),
                "role_name": getattr(r, "role_name", None),
                "days_assigned": getattr(r, "days_assigned", None),
                "created_at": getattr(r, "created_at", None),
                "nome": getattr(r, "nome", None),
                "username": getattr(r, "username", None),
                "email": getattr(r, "email", None),
                "cpf": getattr(r, "cpf", None),
                "phone": getattr(r, "phone", None),
                "bank_name": getattr(r, "bank_name", None),
                "pix": getattr(r, "pix", None),
                "bank_account": getattr(r, "bank_account", None),
                "agency": getattr(r, "agency", None),
                "cref": getattr(r, "cref", None),
            })
        return out
    except Exception as e:
        logger.exception("[events_taf.participants_for_event] erro")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar participantes: {e}")

@router.get("/{event_id}/participants", response_model=List[dict])
def participants_for_event(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """
    Retorna participantes vinculados ao evento (event_workers).
    Versão defensiva: captura exceções e retorna lista vazia em caso de erro,
    enquanto registra o erro para investigação.
    """
    try:
        q = db.query(
            EventWorker.id.label("event_worker_id"),
            EventWorker.event_id,
            EventWorker.user_id,
            EventWorker.role_id,
            EventWorker.role_name,
            EventWorker.days_assigned,
            EventWorker.created_at,
            UserTenant.nome, UserTenant.username, UserTenant.email,
            UserTenant.cpf, UserTenant.phone, UserTenant.bank_name, UserTenant.pix,
            UserTenant.bank_account, UserTenant.agency, UserTenant.cref
        ).outerjoin(UserTenant, UserTenant.id == EventWorker.user_id).filter(EventWorker.event_id == event_id).order_by(EventWorker.created_at.desc())

        rows = q.all()
        out = []
        for r in rows:
            out.append({
                "event_worker_id": getattr(r, "event_worker_id", None),
                "event_id": getattr(r, "event_id", None),
                "user_id": getattr(r, "user_id", None),
                "role_id": getattr(r, "role_id", None),
                "role_name": getattr(r, "role_name", None),
                "days_assigned": getattr(r, "days_assigned", None),
                "created_at": getattr(r, "created_at", None),
                "nome": getattr(r, "nome", None),
                "username": getattr(r, "username", None),
                "email": getattr(r, "email", None),
                "cpf": getattr(r, "cpf", None),
                "phone": getattr(r, "phone", None),
                "bank_name": getattr(r, "bank_name", None),
                "pix": getattr(r, "pix", None),
                "bank_account": getattr(r, "bank_account", None),
                "agency": getattr(r, "agency", None),
                "cref": getattr(r, "cref", None),
            })
        return out
    except Exception as e:
        logger.exception("[events_taf.participants_for_event] Erro ao buscar participantes")
        # Não vaza o stack pro cliente; retorna lista vazia e loga o erro
        return []
