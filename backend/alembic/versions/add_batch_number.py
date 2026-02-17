# -*- coding: utf-8 -*-
"""add batch_number to candidates

Revision ID: 002_add_batch_number
Revises: 001_initial
Create Date: 2024-01-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_batch_number'
down_revision = '001_initial'  # ? CORRIGIDO: aponta para a migração anterior
branch_labels = None
depends_on = None


def upgrade():
    # Adiciona coluna batch_number na tabela candidates (será criada por schema nos tenants)
    # Esta migração é um placeholder - a coluna será adicionada via script SQL direto
    pass


def downgrade():
    # Remove coluna batch_number
    pass
