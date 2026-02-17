"""Initial migration - create central tables (idempotent)

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def table_exists(table_name: str, schema: str = 'public') -> bool:
    """Check if table exists in the database."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names(schema=schema)


def column_exists(table_name: str, column_name: str, schema: str = 'public') -> bool:
    """Check if column exists in table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name, schema=schema)]
    return column_name in columns


def upgrade() -> None:
    # Create tenants table if it doesn't exist
    if not table_exists('tenants'):
        op.create_table(
            'tenants',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('schema_name', sa.String(length=64), nullable=False),
            sa.Column('nome_empresa', sa.String(length=255), nullable=True),
            sa.Column('logo_url', sa.String(length=255), nullable=True),
            sa.Column('responsible_name', sa.String(length=255), nullable=True),
            sa.Column('responsible_email', sa.String(length=255), nullable=True),
            sa.Column('responsible_phone', sa.String(length=50), nullable=True),
            sa.Column('status', sa.String(length=20), server_default='active', nullable=True),
            sa.Column('plan_type', sa.String(length=20), server_default='starter', nullable=True),
            sa.Column('plan_expires_at', sa.Date(), nullable=True),
            sa.Column('dominio_url', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_tenants_id'), 'tenants', ['id'], unique=False)
        op.create_index(op.f('ix_tenants_schema_name'), 'tenants', ['schema_name'], unique=True)
    else:
        # Table exists, add missing columns
        bind = op.get_bind()
        
        # Add columns if they don't exist
        if not column_exists('tenants', 'responsible_name'):
            bind.execute(text('ALTER TABLE tenants ADD COLUMN responsible_name VARCHAR(255)'))
        
        if not column_exists('tenants', 'responsible_email'):
            bind.execute(text('ALTER TABLE tenants ADD COLUMN responsible_email VARCHAR(255)'))
        
        if not column_exists('tenants', 'responsible_phone'):
            bind.execute(text('ALTER TABLE tenants ADD COLUMN responsible_phone VARCHAR(50)'))
        
        if not column_exists('tenants', 'status'):
            bind.execute(text("ALTER TABLE tenants ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
        
        if not column_exists('tenants', 'plan_type'):
            bind.execute(text("ALTER TABLE tenants ADD COLUMN plan_type VARCHAR(20) DEFAULT 'starter'"))
        
        if not column_exists('tenants', 'plan_expires_at'):
            bind.execute(text('ALTER TABLE tenants ADD COLUMN plan_expires_at DATE'))
        
        if not column_exists('tenants', 'dominio_url'):
            bind.execute(text('ALTER TABLE tenants ADD COLUMN dominio_url VARCHAR(255)'))
        
        if not column_exists('tenants', 'created_at'):
            bind.execute(text('ALTER TABLE tenants ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT now()'))
        
        if not column_exists('tenants', 'updated_at'):
            bind.execute(text('ALTER TABLE tenants ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE'))

    # Create users_central table if it doesn't exist
    if not table_exists('users_central'):
        op.create_table(
            'users_central',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('nome', sa.String(length=255), nullable=True),
            sa.Column('hashed_password', sa.String(length=255), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=True),
            sa.Column('tenant_user_id', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
            sa.Column('is_superuser', sa.Boolean(), server_default='false', nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_users_central_email'), 'users_central', ['email'], unique=True)
        op.create_index(op.f('ix_users_central_id'), 'users_central', ['id'], unique=False)
    else:
        # Table exists, add missing columns
        bind = op.get_bind()
        
        if not column_exists('users_central', 'created_at'):
            bind.execute(text('ALTER TABLE users_central ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT now()'))


def downgrade() -> None:
    # Only drop if tables exist
    if table_exists('users_central'):
        op.drop_index(op.f('ix_users_central_id'), table_name='users_central')
        op.drop_index(op.f('ix_users_central_email'), table_name='users_central')
        op.drop_table('users_central')
    
    if table_exists('tenants'):
        op.drop_index(op.f('ix_tenants_schema_name'), table_name='tenants')
        op.drop_index(op.f('ix_tenants_id'), table_name='tenants')
        op.drop_table('tenants')
