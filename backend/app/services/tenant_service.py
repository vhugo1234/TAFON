import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, insert, select
from app.models.tenant import Tenant
from app.schemas.tenant_schema import TenantCreate, TenantRead

logger = logging.getLogger(__name__)


class TenantService:
    @staticmethod
    async def create_tenant(db: AsyncSession, tenant_data: TenantCreate) -> TenantRead:
        """
        Cria um novo tenant (schema) no banco e registra na tabela de tenants.
        """
        schema_name = tenant_data.schema_name or tenant_data.name.lower().replace(" ", "_")

        try:
            # 1️⃣ Cria o schema no banco de dados, se não existir
            create_schema_query = text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";')
            await db.execute(create_schema_query)
            logger.info(f"✅ Schema '{schema_name}' criado com sucesso.")

            # 2️⃣ Registra o tenant na tabela principal
            stmt = insert(Tenant).values(
                name=tenant_data.name,
                domain=tenant_data.domain,
                schema_name=schema_name,
                is_active=True
            ).returning(Tenant)

            result = await db.execute(stmt)
            await db.commit()
            tenant = result.scalar_one()

            # 3️⃣ (Opcional) Executar migrações iniciais no schema do tenant
            # await TenantService._init_schema(db, schema_name)

            logger.info(f"✅ Tenant '{tenant.name}' registrado com sucesso.")
            return TenantRead.from_orm(tenant)

        except Exception as e:
            await db.rollback()
            logger.exception(f"❌ Erro ao criar tenant '{schema_name}': {e}")
            raise RuntimeError(f"Erro ao criar tenant: {e}")

    @staticmethod
    async def list_tenants(db: AsyncSession) -> list[TenantRead]:
        """
        Retorna a lista de tenants cadastrados.
        """
        result = await db.execute(select(Tenant))
        tenants = result.scalars().all()
        return [TenantRead.from_orm(t) for t in tenants]

    @staticmethod
    async def _init_schema(db: AsyncSession, schema_name: str):
        """
        Cria as tabelas iniciais dentro do schema do tenant.
        (Pode ser expandido para rodar alembic migrations específicas)
        """
        try:
            await db.execute(text(f'SET search_path TO "{schema_name}";'))
            # Exemplo: criar tabela inicial
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) NOT NULL,
                    password VARCHAR(255) NOT NULL
                );
            """))
            await db.commit()
            logger.info(f"📦 Estrutura inicial criada no schema '{schema_name}'.")
        except Exception as e:
            await db.rollback()
            logger.exception(f"Erro ao inicializar schema '{schema_name}': {e}")
            raise
