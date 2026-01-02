# backend/app/db/startup.py
"""
Utilities de startup / provisionamento de schemas multi-tenant.
Fornece:
- initialize_tenant_schema(engine, schema_name)
- sync_sequences()  (sincroniza sequences públicas conhecidas, usado no startup)
"""

import re
import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from typing import Optional

logger = logging.getLogger("app.db.startup")

_schema_name_re = re.compile(r"^[a-z0-9_]+$")


def _validate_schema_name(name: str) -> bool:
    return bool(name and _schema_name_re.match(name))


def initialize_tenant_schema(engine: Engine, schema_name: str) -> None:
    """
    Cria o schema do tenant (se não existir) e cria as tabelas definidas no metadata
    TenantBase (app.db.models.tenant.TenantBase).

    Parâmetros:
    - engine: SQLAlchemy Engine (p.ex. importado de app.db.connection)
    - schema_name: nome do schema a criar (somente lowercase, números e underscore)
    """
    if not _validate_schema_name(schema_name):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    try:
        # Import local para evitar import circular em startup do app
        from app.db.models.tenant import TenantBase
    except Exception as e:
        logger.exception("Não foi possível importar TenantBase (app.db.models.tenant).")
        raise

    try:
        # Use begin() para transações DDL seguras no Postgres
        with engine.begin() as conn:
            # Criar schema se não existir
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            # Ajustar search_path temporariamente e criar tabelas do tenant metadata
            conn.execute(text(f'SET search_path TO "{schema_name}", public'))
            TenantBase.metadata.create_all(bind=conn)
            logger.info("Schema '%s' criado/atualizado com sucesso.", schema_name)
    except SQLAlchemyError:
        logger.exception("Erro ao inicializar schema '%s'.", schema_name)
        raise


def sync_sequences(engine: Optional[Engine] = None) -> None:
    """
    Sincroniza sequences públicas conhecidas (por exemplo: tenants_id_seq) com o MAX(id)
    para evitar conflitos após import/restore. Se engine não for fornecido, tenta usar
    app.db.connection.engine (se disponível).
    """
    try:
        if engine is None:
            # Import local para evitar import issues no momento do startup
            try:
                from app.db.connection import engine as default_engine
            except Exception:
                default_engine = None
            engine = engine or default_engine

        if engine is None:
            logger.warning("sync_sequences: nenhum engine disponível; pulando sincronização.")
            return

        sequences = [
            # Lista de pares (sequence_name, table_name, id_column)
            ("tenants_id_seq", "tenants", "id"),
            # Adicione outras sequences públicas aqui, se existirem:
            # ("users_central_id_seq", "users_central", "id"),
        ]

        with engine.begin() as conn:
            for seq_name, table, col in sequences:
                try:
                    # Verifica se a tabela existe e, se existir, calcula max(id)
                    r = conn.execute(
                        text(
                            "SELECT to_regclass(:seq) IS NOT NULL AS seq_exists"
                        ),
                        {"seq": seq_name},
                    ).scalar()
                    if not r:
                        # sequence não existe — pular
                        logger.debug("Sequência %s não existe; pulando.", seq_name)
                        continue

                    max_id = conn.execute(
                        text(f"SELECT COALESCE(MAX({col}), 0) FROM {table}")
                    ).scalar() or 0
                    # setval to max(id) (next will be max+1)
                    conn.execute(text(f"SELECT setval(:seq, :val, true)"), {"seq": seq_name, "val": int(max_id)})
                    logger.info("Sincronizada sequence %s com valor %s", seq_name, max_id)
                except Exception:
                    logger.exception("Falha ao sincronizar sequence %s (tabela %s).", seq_name, table)
                    # Não interrompe todas as sequences — tenta continuar
                    continue
    except Exception:
        logger.exception("Erro geral durante sync_sequences.")
        raise