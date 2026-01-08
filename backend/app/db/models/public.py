# backend/app/db/models/public.py
# Modelos do schema 'public' (central). Usa Base separado dos modelos TenantBase.

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    
    # Campos básicos
    id = Column(Integer, primary_key=True, index=True)
    schema_name = Column(String(64), unique=True, nullable=False, index=True)
    nome_empresa = Column(String(255), nullable=True)
    logo_url = Column(String(255), nullable=True)
    
    # Informações do responsável
    responsible_name = Column(String(255), nullable=True)
    responsible_email = Column(String(255), nullable=True)
    responsible_phone = Column(String(50), nullable=True)
    
    # Status e plano
    status = Column(String(20), default="active")  # 'active', 'inactive', 'pending', 'suspended'
    plan_type = Column(String(20), default="starter")  # 'free', 'starter', 'professional', 'enterprise'
    plan_expires_at = Column(Date, nullable=True)
    
    # Domínio personalizado
    dominio_url = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("UserCentral", back_populates="tenant")

class UserCentral(Base):
    __tablename__ = "users_central"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    nome = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)

    # ForeignKey explícito para relacionamento com Tenant
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)

    # Relacionamento com Tenant
    tenant = relationship("Tenant", back_populates="users")

    # ID do usuário no schema do tenant (se houver)
    tenant_user_id = Column(Integer, nullable=True)

    # Status e permissões
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())