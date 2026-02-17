from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Any, Dict, Iterable, Set
from app.api.deps_tenant import get_tenant_db_session
from app.schemas.event_worker_schema import EventWorkerCreate, EventWorkerUpdate, EventWorkerOut

# adapt your auth dependency
try:
    from app.api.deps import get_current_user
except Exception:
    def get_current_user():
        return None

router = APIRouter(tags=["Event Workers"], prefix="/event")


def row_to_dict(row: Any) -> Dict[str, Any]:
    try:
        return dict(row._mapping)
    except Exception:
        try:
            return {c: getattr(row, c) for c in row.keys()}
        except Exception:
            try:
                return dict(row)
            except Exception:
                return {"raw": str(row)}


def fetch_role_labels_for_ids(db: Session, ids: Iterable[int]) -> Dict[int, str]:
    """
    Tenta obter rótulos (labels) de roles para os ids fornecidos.
    Tenta, em ordem, tabelas candidatas: role_tenant, roles, role.
    Retorna um dicionário id -> label. Falha silenciosa se nenhuma tabela existir.
    """
    ids = [int(i) for i in set(ids) if i is not None]
    if not ids:
        return {}
    id_list = ",".join(map(str, ids))
    candidate_tables = ["role_tenant", "roles", "role"]
    labels: Dict[int, str] = {}
    for tbl in candidate_tables:
        try:
            q = text(f"SELECT id, COALESCE(name, label, title) AS label FROM {tbl} WHERE id IN ({id_list})")
            rows = db.execute(q).fetchall()
            for r in rows:
                rd = row_to_dict(r)
                try:
                    labels[int(rd.get("id"))] = rd.get("label")
                except Exception:
                    continue
            # if we found some labels, stop trying other tables
            if labels:
                break
        except Exception:
            # table might not exist in this tenant schema — ignore and continue
            continue
    return labels


@router.get("/{event_id}/workers", response_model=List[EventWorkerOut])
def list_event_workers(event_id: int, db: Session = Depends(get_tenant_db_session)):
    q = text("""
        SELECT ew.*,
               u.id AS user_id,
               u.nome AS user_nome,
               u.username AS user_username,
               u.email AS user_email,
               u.avatar_url AS user_avatar_url,
               u.role_id AS user_role_id
        FROM event_workers ew
        LEFT JOIN user_tenant u ON u.id = ew.user_id
        WHERE ew.event_id = :event_id
        ORDER BY ew.created_at
    """)
    rows = db.execute(q, {"event_id": event_id}).fetchall()

    items = []
    missing_role_ids: Set[int] = set()
    for r in rows:
        rd = row_to_dict(r)
        # build user sub-object (keep top-level user_id)
        user = None
        if rd.get("user_id") is not None:
            user = {
                "id": rd.get("user_id"),
                "nome": rd.get("user_nome"),
                "username": rd.get("user_username"),
                "email": rd.get("user_email"),
                "avatar_url": rd.get("user_avatar_url"),
                "role_id": rd.get("user_role_id"),
            }
            # remove aliased user_* helpers to avoid duplication
            rd.pop("user_nome", None)
            rd.pop("user_username", None)
            rd.pop("user_email", None)
            rd.pop("user_avatar_url", None)
            rd.pop("user_role_id", None)
        rd["user"] = user

        # collect role_id if event_worker has none role_name
        # prefer ew.role_id, then user's role_id as fallback for label resolution
        role_id = rd.get("role_id") or (user and user.get("role_id"))
        if (rd.get("role_name") is None or str(rd.get("role_name")).strip() == "") and role_id:
            try:
                missing_role_ids.add(int(role_id))
            except Exception:
                pass

        items.append(rd)

    # fetch labels in batch (if any)
    if missing_role_ids:
        labels_map = fetch_role_labels_for_ids(db, missing_role_ids)
        # apply labels to items that miss role_name
        for it in items:
            if (it.get("role_name") is None or str(it.get("role_name")).strip() == ""):
                role_id = it.get("role_id") or (it.get("user") and it["user"].get("role_id"))
                if role_id:
                    lbl = labels_map.get(int(role_id))
                    if lbl:
                        it["role_name"] = lbl

    # instantiate Pydantic models when possible
    result = []
    for it in items:
        try:
            result.append(EventWorkerOut(**it))
        except Exception:
            result.append(it)
    return result


from sqlalchemy.exc import IntegrityError

@router.post("/{event_id}/workers", response_model=EventWorkerOut, status_code=status.HTTP_201_CREATED)
def add_event_worker(event_id: int, payload: EventWorkerCreate, db: Session = Depends(get_tenant_db_session), current_user = Depends(get_current_user)):
    """
    Cria um vínculo de usuário ao evento.
    Defesa: limpa transações abortadas antes do INSERT, faz um retry único se necessário,
    e trata IntegrityError para retornar 409 em vez de 500.
    """
    from sqlalchemy.exc import IntegrityError

    try:
        # verify event exists
        ev = db.execute(text("SELECT id FROM events WHERE id = :id"), {"id": event_id}).fetchone()
        if not ev:
            raise HTTPException(status_code=404, detail="Evento não encontrado")

        # verify user exists and read user's role_id
        user_row = db.execute(
            text("SELECT id, nome, email, username, avatar_url, role_id FROM user_tenant WHERE id = :id"),
            {"id": payload.user_id}
        ).fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado no tenant")
        user = row_to_dict(user_row)

        # prevent duplicate
        dup = db.execute(text("SELECT id FROM event_workers WHERE event_id = :event_id AND user_id = :user_id"),
                         {"event_id": event_id, "user_id": payload.user_id}).fetchone()
        if dup:
            raise HTTPException(status_code=409, detail="Usuário já vinculado a esse evento")

        # decide role to insert
        role_id_to_insert = payload.role_id if getattr(payload, "role_id", None) is not None else user.get("role_id")
        role_name_to_insert = payload.role_name if getattr(payload, "role_name", None) is not None else None

        # try to resolve role_name if missing and role_id present (best-effort)
        if (not role_name_to_insert) and role_id_to_insert:
            try:
                labels = fetch_role_labels_for_ids(db, [int(role_id_to_insert)])
                role_name_to_insert = labels.get(int(role_id_to_insert))
            except Exception:
                role_name_to_insert = None

        # defensive: clear any aborted transaction before attempting INSERT
        try:
            db.rollback()
        except Exception:
            pass

        # attempt insert, with single retry if session was previously aborted
        created = None
        last_exc = None
        for attempt in (1, 2):
            try:
                ins = text("""
                    INSERT INTO event_workers (event_id, user_id, role_id, role_name, days_assigned, created_at)
                    VALUES (:event_id, :user_id, :role_id, :role_name, :days_assigned, now())
                    RETURNING *
                """)
                r = db.execute(ins, {
                    "event_id": event_id,
                    "user_id": payload.user_id,
                    "role_id": role_id_to_insert,
                    "role_name": role_name_to_insert,
                    "days_assigned": payload.days_assigned
                })
                created = r.fetchone()
                db.commit()
                last_exc = None
                break
            except IntegrityError as ie:
                db.rollback()
                raise HTTPException(status_code=409, detail=f"Conflito ao criar vínculo: {ie.orig.pgerror if getattr(ie, 'orig', None) else str(ie)}")
            except Exception as e:
                # attempt rollback then retry once if transaction was aborted
                msg = str(e).lower()
                last_exc = e
                try:
                    db.rollback()
                except Exception:
                    pass
                if "current transaction is aborted" in msg or "infailedsqltransaction" in msg:
                    if attempt == 1:
                        continue
                raise HTTPException(status_code=500, detail=f"Erro ao vincular worker: {e}")

        if last_exc and not created:
            raise HTTPException(status_code=500, detail=f"Erro ao vincular worker: {last_exc}")

        rd = row_to_dict(created)
        rd["user"] = {
            "id": user.get("id"),
            "nome": user.get("nome"),
            "username": user.get("username"),
            "email": user.get("email"),
            "avatar_url": user.get("avatar_url"),
            "role_id": user.get("role_id"),
        }

        try:
            return EventWorkerOut(**rd)
        except Exception:
            return rd

    except HTTPException:
        raise
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erro ao processar requisição: {e}")


@router.patch("/{event_id}/workers/{worker_id}", response_model=EventWorkerOut)
def update_event_worker(event_id: int, worker_id: int, payload: EventWorkerUpdate, db: Session = Depends(get_tenant_db_session), current_user = Depends(get_current_user)):
    rec = db.execute(text("SELECT * FROM event_workers WHERE id = :id AND event_id = :event_id"), {"id": worker_id, "event_id": event_id}).fetchone()
    if not rec:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")
    try:
        upd = text("""
            UPDATE event_workers
            SET role_id = COALESCE(:role_id, role_id),
                role_name = COALESCE(:role_name, role_name),
                days_assigned = COALESCE(:days_assigned, days_assigned)
            WHERE id = :id
            RETURNING *
        """)
        r = db.execute(upd, {
            "role_id": payload.role_id,
            "role_name": payload.role_name,
            "days_assigned": payload.days_assigned,
            "id": worker_id
        })
        updated = r.fetchone()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar vínculo: {e}")

    rd = row_to_dict(updated)
    # try to attach user info
    try:
        u = db.execute(text("SELECT id, nome, username, email, avatar_url, role_id FROM user_tenant WHERE id = :id"), {"id": rd.get("user_id")}).fetchone()
        if u:
            urd = row_to_dict(u)
            rd["user"] = {"id": urd.get("id"), "nome": urd.get("nome"), "username": urd.get("username"), "email": urd.get("email"), "avatar_url": urd.get("avatar_url"), "role_id": urd.get("role_id")}
    except Exception:
        pass

    # if role_name missing but role_id present, try resolve label
    if (not rd.get("role_name")) and rd.get("role_id"):
        labels = fetch_role_labels_for_ids(db, [int(rd.get("role_id"))])
        if labels.get(int(rd.get("role_id"))):
            rd["role_name"] = labels.get(int(rd.get("role_id")))

    try:
        return EventWorkerOut(**rd)
    except Exception:
        return rd


@router.delete("/{event_id}/workers/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_worker(event_id: int, worker_id: int, db: Session = Depends(get_tenant_db_session), current_user = Depends(get_current_user)):
    rec = db.execute(text("SELECT id FROM event_workers WHERE id = :id AND event_id = :event_id"), {"id": worker_id, "event_id": event_id}).fetchone()
    if not rec:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")
    try:
        db.execute(text("DELETE FROM event_workers WHERE id = :id"), {"id": worker_id})
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao remover vínculo: {e}")
    return
