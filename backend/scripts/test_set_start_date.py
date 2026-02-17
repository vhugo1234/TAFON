# scripts/test_set_start_date.py
# Execute dentro do ambiente do projeto (container/venv) para testar mapeamento e commit.
from app.api.deps_tenant import get_tenant_db_session
from app.db.models.tenant import Candidate
from datetime import date

db = next(get_tenant_db_session())
try:
    # pegue um candidato do evento 6 que tenha start_time
    c = db.query(Candidate).filter(Candidate.event_id == 6, Candidate.start_time != None).first()
    if not c:
        print("Nenhum candidato com start_time encontrado no evento 6")
    else:
        print("Antes:", c.id, c.start_time, c.start_date)
        c.start_date = date(2026, 1, 17)
        db.add(c)
        db.commit()
        db.refresh(c)
        print("Depois:", c.id, c.start_time, c.start_date)
finally:
    db.close()