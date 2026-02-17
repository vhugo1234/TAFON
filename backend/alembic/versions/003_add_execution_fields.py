"""add execution mode and measurement type to exercises

Revision ID: 003_add_execution_fields
Revises: add_exercise_evaluators
Create Date: 2024-01-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '003_add_execution_fields'
down_revision = 'add_exercise_evaluators'
branch_labels = None
depends_on = None


def upgrade():
    """
    Adiciona campos execution_mode e measurement_type na tabela exercises
    de todos os schemas de tenant.
    """
    
    connection = op.get_bind()
    
    # Busca todos os schemas de tenant
    result = connection.execute(text("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('public', 'information_schema', 'pg_catalog', 'pg_toast')
          AND schema_name NOT LIKE 'pg_%'
    """))
    
    tenant_schemas = [row[0] for row in result]
    
    print(f"Aplicando migracao em {len(tenant_schemas)} schemas de tenant...")
    
    for schema in tenant_schemas:
        print(f"  - Adicionando campos no schema '{schema}'")
        
        connection.execute(text(f'SET search_path TO "{schema}", public'))
        
        # Adiciona execution_mode
        op.add_column(
            'exercises',
            sa.Column('execution_mode', sa.String(20), nullable=False, server_default='individual'),
            schema=schema
        )
        
        # Adiciona measurement_type
        op.add_column(
            'exercises',
            sa.Column('measurement_type', sa.String(20), nullable=False, server_default='repetitions'),
            schema=schema
        )
    
    connection.execute(text('SET search_path TO public'))
    
    print(f"Migracao aplicada com sucesso em {len(tenant_schemas)} schemas!")


def downgrade():
    """
    Remove os campos execution_mode e measurement_type.
    """
    
    connection = op.get_bind()
    
    result = connection.execute(text("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('public', 'information_schema', 'pg_catalog', 'pg_toast')
          AND schema_name NOT LIKE 'pg_%'
    """))
    
    tenant_schemas = [row[0] for row in result]
    
    print(f"Revertendo migracao em {len(tenant_schemas)} schemas de tenant...")
    
    for schema in tenant_schemas:
        print(f"  - Removendo campos do schema '{schema}'")
        
        connection.execute(text(f'SET search_path TO "{schema}", public'))
        
        op.drop_column('exercises', 'measurement_type', schema=schema)
        op.drop_column('exercises', 'execution_mode', schema=schema)
    
    connection.execute(text('SET search_path TO public'))
    
    print(f"Reversao aplicada com sucesso em {len(tenant_schemas)} schemas!")
