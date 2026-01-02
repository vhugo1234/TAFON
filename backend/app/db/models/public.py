# backend/app/db/models/public.py
"""
Models for the public schema (central/superadmin tables).
TEMPORARY FIX: Minimal models to support authentication.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

PublicBase = declarative_base()


class Tenant(PublicBase):
    """
    Tenant (client) in the public schema.
    """
    __tablename__ = "tenants"
    __table_args__ = {'schema': 'public'}
    
    id = Column(Integer, primary_key=True, index=True)
    nome_empresa = Column(String(255), nullable=False)
    schema_name = Column(String(63), unique=True, nullable=False, index=True)
    logo_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    users = relationship("UserCentral", back_populates="tenant")


class UserCentral(PublicBase):
    """
    Central/superadmin users in the public schema.
    """
    __tablename__ = "user_central"
    __table_args__ = {'schema': 'public'}
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nome = Column(String(255), nullable=True)
    username = Column(String(50), unique=True, nullable=True)
    is_superuser = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    tenant_id = Column(Integer, ForeignKey("public.tenants.id"), nullable=True)
    tenant_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    tenant = relationship("Tenant", back_populates="users")
