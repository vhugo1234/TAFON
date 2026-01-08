# backend/app/db/startup.py
"""
Utilities de startup / provisionamento de schemas multi-tenant.
Fornece:
- initialize_tenant_schema(engine, schema_name)
- insert_default_roles_tenant(engine, schema_name)
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


def insert_default_roles_tenant(engine: Engine, schema_name: str) -> None:
    """
    Insere roles padrão na tabela roles_tenant do schema do tenant.
    
    Parâmetros:
    - engine: SQLAlchemy Engine
    - schema_name: nome do schema do tenant
    """
    if not _validate_schema_name(schema_name):
        raise ValueError(f"Nome de schema inválido: {schema_name}")
    
    default_roles = [
        {"nome": "Administrador", "descricao": "Acesso completo ao sistema"},
        {"nome": "Coordenador", "descricao": "Coordenador de eventos TAF"},
        {"nome": "Avaliador", "descricao": "Avaliador de provas físicas"},
        {"nome": "Usuário", "descricao": "Usuário padrão com acesso limitado"},
    ]
    
    try:
        with engine.begin() as conn:
            conn.execute(text(f'SET search_path TO "{schema_name}", public'))
            
            # Verificar se já existem roles
            result = conn.execute(text("SELECT COUNT(*) FROM roles_tenant")).scalar()
            
            if result > 0:
                logger.info("Roles já existem no schema '%s'. Pulando inserção.", schema_name)
                return
            
            # Inserir roles padrão
            for role in default_roles:
                conn.execute(
                    text("""
                        INSERT INTO roles_tenant (nome, descricao)
                        VALUES (:nome, :descricao)
                        ON CONFLICT (nome) DO NOTHING
                    """),
                    role
                )
            
            logger.info("Roles padrão inseridos no schema '%s'.", schema_name)
    
    except SQLAlchemyError:
        logger.exception("Erro ao inserir roles padrão no schema '%s'.", schema_name)
        # Não levanta exceção para não quebrar o provisionamento completo
        logger.warning("Continuando sem roles padrão (podem ser inseridos manualmente)")


def sync_sequences(engine: Optional[Engine] = None) -> None:
    """
    Sincroniza sequences públicas conhecidas (por exemplo: tenants_id_seq) com o MAX(id)
    para evitar conflitos após import/restore. Se engine não for fornecido, tenta usar
    app.db.connection.engine (se disponível).
    
    Esta função é tolerante a falhas - não levanta exceção se uma sequence não existir.
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
            ("users_central_id_seq", "users_central", "id"),
            # Adicione outras sequences públicas aqui, se existirem
        ]

        for seq_name, table, col in sequences:
            # Criar nova conexão/transação para cada sequence (evita transações abortadas)
            try:
                with engine.begin() as conn:
                    # Verificar se a sequence existe
                    try:
                        r = conn.execute(
                            text("SELECT to_regclass(:seq) IS NOT NULL AS seq_exists"),
                            {"seq": seq_name}
                        ).scalar()
                        
                        if not r:
                            logger.debug("Sequência %s não existe; pulando.", seq_name)
                            continue
                    except Exception as e:
                        logger.debug("Não foi possível verificar sequence %s: %s. Pulando.", seq_name, e)
                        continue

                    # Verificar se a tabela existe
                    try:
                        table_exists = conn.execute(
                            text("SELECT to_regclass(:tbl) IS NOT NULL AS tbl_exists"),
                            {"tbl": table}
                        ).scalar()
                        
                        if not table_exists:
                            logger.debug("Tabela %s não existe; pulando sequence %s.", table, seq_name)
                            continue
                    except Exception as e:
                        logger.debug("Não foi possível verificar tabela %s: %s. Pulando.", table, e)
                        continue

                    # Calcular MAX(id) da tabela
                    try:
                        max_id = conn.execute(
                            text(f"SELECT COALESCE(MAX({col}), 0) FROM {table}")
                        ).scalar() or 0
                    except Exception as e:
                        logger.warning("Não foi possível calcular MAX(id) para %s: %s. Pulando.", table, e)
                        continue
                    
                    # CORREÇÃO: Se max_id for 0, usar 1 (mínimo para sequences)
                    # Se houver registros, usar max_id
                    sync_value = max(1, max_id)
                    
                    # Atualizar sequence
                    try:
                        conn.execute(
                            text(f"SELECT setval(:seq, :val, true)"), 
                            {"seq": seq_name, "val": int(sync_value)}
                        )
                        logger.info("Sincronizada sequence %s com valor %s", seq_name, sync_value)
                    except Exception as e:
                        logger.warning("Falha ao atualizar sequence %s: %s", seq_name, e)
                        continue
                        
            except Exception as e:
                logger.debug("Erro ao processar sequence %s: %s. Continuando com próxima.", seq_name, e)
                # Não interrompe as outras sequences - continua
                continue
                
    except Exception as e:
        # Erro geral - apenas log, não quebra o startup
        logger.warning("Aviso durante sync_sequences: %s", e)
        # Não levanta exceção - sync_sequences é não-crítico