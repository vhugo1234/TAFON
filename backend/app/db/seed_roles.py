```python
import logging
from typing import List, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Default roles to insert in every tenant schema (id, nome, descricao)
DEFAULT_ROLES: List[Tuple[int, str, str]] = [
    (1, "Administrador Geral", "Administrador com privilégios globais"),
    (2, "Coordenador Geral", "Coordenador geral"),
    (3, "Coordenador de Educação Física", "Coordenador de Educação Física"),
    (4, "Avaliador de Educação Física", "Avaliador de Educação Física"),
    (5, "Apoio", "Equipe de apoio"),
    (6, "Técnico de AudioVisual", "Técnico de AudioVisual"),
    (7, "Volantes", "Volantes"),
    (8, "Fiscais", "Fiscais"),
]


def seed_roles(db: Session, schema_name: str) -> None:
    """
    Garantir que a tabela <schema_name>.roles_tenant contenha os papéis DEFAULT_ROLES.
    - Executa INSERT ... ON CONFLICT (id) DO NOTHING para não sobrescrever se já existir.
    - Ajusta a sequência do id se necessário.
    - Restaura search_path para public no final.
    """
    if not schema_name:
        logger.warning("seed_roles chamado sem schema_name")
        return

    try:
        logger.debug("seed_roles: setting search_path to %s", schema_name)
        db.execute(text(f'SET search_path TO "{schema_name}", public'))
    except Exception as e:
        logger.exception("seed_roles: falha ao setar search_path: %s", e)
        return

    try:
        for _id, nome, descricao in DEFAULT_ROLES:
            try:
                db.execute(
                    text(
                        """
                        INSERT INTO roles_tenant (id, nome, descricao)
                        VALUES (:id, :nome, :descricao)
                        ON CONFLICT (id) DO UPDATE
                          SET nome = EXCLUDED.nome,
                              descricao = COALESCE(EXCLUDED.descricao, roles_tenant.descricao)
                        """
                    ),
                    {"id": _id, "nome": nome, "descricao": descricao},
                )
            except Exception:
                # Se a tabela não existir no schema atual, lançar undefined_table será capturado
                logger.debug("seed_roles: insert attempt failed for schema %s id %s (table may not exist)", schema_name, _id, exc_info=True)
                raise

        # Ajustar sequence (caso id seja serial)
        try:
            db.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:tbl, 'id'), COALESCE((SELECT MAX(id) FROM " + schema_name + ".roles_tenant), 1), true)"
                ),
                {"tbl": f"{schema_name}.roles_tenant"},
            )
        except Exception:
            # fallback: try without schema qualification (some setups may differ)
            try:
                db.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence('roles_tenant', 'id'), COALESCE((SELECT MAX(id) FROM roles_tenant), 1), true)"
                    )
                )
            except Exception:
                logger.debug("seed_roles: ajuste de sequence falhou para schema %s", schema_name, exc_info=True)

        db.commit()
        logger.info("seed_roles: papéis garantidos no schema %s", schema_name)
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("seed_roles: falha ao semear roles no schema %s: %s", schema_name, e)
    finally:
        try:
            db.execute(text("SET search_path TO public"))
        except Exception:
            pass