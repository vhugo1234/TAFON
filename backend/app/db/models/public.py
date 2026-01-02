# backend/app/db/models/public.py
# Modelos do schema 'public' (central). Usa Base separado dos modelos TenantBase.

from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    schema_name = Column(String(64), unique=True, nullable=False)
    nome_empresa = Column(String(255), nullable=True)
    logo_url = Column(String(255), nullable=True)

    users = relationship("UserCentral", back_populates="tenant")

class UserCentral(Base):
    __tablename__ = "users_central"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    nome = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)

    tenant_id = Column(Integer, nullable=True)
    # relacionamento opcional - depende de como você gerencia FK em migrations
    tenant = relationship("Tenant", back_populates="users", primaryjoin="Tenant.id==foreign(UserCentral.tenant_id)")

    # campo usado pelo auth.py para mapear usuário central ao id do usuário no tenant, se houver
    tenant_user_id = Column(Integer, nullable=True)

    is_superuser = Column(Boolean, default=False)