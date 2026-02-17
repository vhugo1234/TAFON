"""add exercise_evaluators table to tenant schemas

Revision ID: add_exercise_evaluators
Revises: 002_add_batch_number
Create Date: 2024-01-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'add_exercise_evaluators'
down_revision = '002_add_batch_number'
branch_labels = None
depends_on = None


def upgrade():
    """
    Adiciona a tabela exercise_evaluators em TODOS os schemas de tenant existentes.
    Esta tabela pertence ao tenant, nao ao schema publico.
    """
    
    # Conecta ao banco
    connection = op.get_bind()
    
    # Busca todos os schemas de tenant (excluindo schemas do sistema)
    result = connection.execute(text("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('public', 'information_schema', 'pg_catalog', 'pg_toast')
          AND schema_name NOT LIKE 'pg_%'
    """))
    
    tenant_schemas = [row[0] for row in result]
    
    print(f"Aplicando migracao em {len(tenant_schemas)} schemas de tenant...")
    
    # Para cada schema de tenant, cria a tabela
    for schema in tenant_schemas:
        print(f"  - Criando exercise_evaluators no schema '{schema}'")
        
        # Define o search_path para o schema do tenant
        connection.execute(text(f'SET search_path TO "{schema}", public'))
        
        # Cria a tabela exercise_evaluators
        op.create_table(
            'exercise_evaluators',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('exercise_id', sa.Integer(), nullable=False),
            sa.Column('evaluator_user_id', sa.Integer(), nullable=False),
            sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['evaluator_user_id'], ['user_tenant.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            schema=schema
        )
        
        # Cria indices
        op.create_index(
            'ix_exercise_evaluators_exercise_id', 
            'exercise_evaluators', 
            ['exercise_id'],
            schema=schema
        )
        op.create_index(
            'ix_exercise_evaluators_evaluator_user_id', 
            'exercise_evaluators', 
            ['evaluator_user_id'],
            schema=schema
        )
    
    # Restaura search_path
    connection.execute(text('SET search_path TO public'))
    
    print(f"Migracao aplicada com sucesso em {len(tenant_schemas)} schemas!")


def downgrade():
    """
    Remove a tabela exercise_evaluators de TODOS os schemas de tenant.
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
    
    print(f"Revertendo migracao em {len(tenant_schemas)} schemas de tenant...")
    
    # Para cada schema de tenant, remove a tabela
    for schema in tenant_schemas:
        print(f"  - Removendo exercise_evaluators do schema '{schema}'")
        
        connection.execute(text(f'SET search_path TO "{schema}", public'))
        
        # Remove indices
        op.drop_index(
            'ix_exercise_evaluators_evaluator_user_id', 
            table_name='exercise_evaluators',
            schema=schema
        )
        op.drop_index(
            'ix_exercise_evaluators_exercise_id', 
            table_name='exercise_evaluators',
            schema=schema
        )
        
        # Remove tabela
        op.drop_table('exercise_evaluators', schema=schema)
    
    connection.execute(text('SET search_path TO public'))
    
    print(f"Reversao aplicada com sucesso em {len(tenant_schemas)} schemas!")
