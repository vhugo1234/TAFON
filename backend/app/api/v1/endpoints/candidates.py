# backend/app/api/v1/endpoints/candidates.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, NoResultFound # <-- ADICIONE AQUI
import csv
import io

from app.api.deps_tenant import get_tenant_db_session 
from app.db.models.tenant import Candidate, Event
from app.schemas.candidate_schema import CandidateCreate, CandidateOut, ImportResult

router = APIRouter(tags=["TAF - Módulo 3: Candidatos e Turmas"])

# -----------------------------------------------------------
# Rota de Importação (CSV)
# -----------------------------------------------------------

@router.post("/import", response_model=ImportResult)
async def import_candidates_from_csv(
    event_id: int = Form(..., description="ID do evento para associar os candidatos"),
    file: UploadFile = File(..., description="Arquivo CSV com a lista de candidatos"),
    db: Session = Depends(get_tenant_db_session)
):
    """Importa candidatos de um arquivo CSV para um Evento específico."""
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Apenas arquivos CSV são suportados.")
    
    # Verifica se o evento existe no schema do tenant
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado no seu ambiente.")

    content = await file.read()
    decoded_content = content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(decoded_content))

    results = ImportResult(total_rows=0, rows_imported=0, rows_failed=0, errors=[])
    
    # Mapeamento de colunas do CSV para o modelo
    COL_MAP = {
        'nome_completo': 'full_name',
        'cpf': 'cpf',
        'inscricao': 'registration_number',
        'genero': 'gender',
        'turma': 'batch_name', # Opcional
    }

    for row in csv_reader:
        results.total_rows += 1
        try:
            candidate_data = {
                "event_id": event_id,
                "full_name": row.get(COL_MAP['nome_completo']),
                "cpf": row.get(COL_MAP['cpf']).replace('.', '').replace('-', ''), # Limpar CPF
                "registration_number": row.get(COL_MAP['inscricao']),
                "gender": row.get(COL_MAP['genero']).upper(),
                "batch_name": row.get(COL_MAP['turma']) or None,
            }
            
            # Validação Pydantic (opcional, mas recomendado)
            CandidateCreate(**candidate_data) 
            
            # Cria a instância do modelo
            db_candidate = Candidate(**candidate_data)
            db.add(db_candidate)
            db.flush() # Tenta inserir antes do commit final

            results.rows_imported += 1

        except IntegrityError:
            db.rollback()
            results.rows_failed += 1
            results.errors.append(f"Linha {results.total_rows}: CPF ou Número de Inscrição já existe.")
        except Exception as e:
            db.rollback()
            results.rows_failed += 1
            results.errors.append(f"Linha {results.total_rows}: Erro de validação/parsing - {e}")

    db.commit() # Commit das inserções bem-sucedidas
    
    # ⚠️ TODO: Adicionar um limite de erros antes de abortar a importação
    
    return results

# -----------------------------------------------------------
# Rotas CRUD Básicas (para Candidates)
# -----------------------------------------------------------

@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Busca um candidato pelo ID."""
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).one()
        return candidate
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Candidato não encontrado.")

@router.get("/", response_model=List[CandidateOut])
def list_candidates(
    event_id: int,
    db: Session = Depends(get_tenant_db_session)
):
    """Lista todos os candidatos de um evento específico."""
    candidates = db.query(Candidate).filter(Candidate.event_id == event_id).all()
    return candidates

# ... Adicione rotas para create, update e delete