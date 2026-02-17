# backend/app/db/models/role_tenant.py
"""
TEMPORARY SHIM: Re-export RoleTenant from tenant models.
"""
try:
    from app.db.models.tenant import UserRole as RoleTenant
    __all__ = ["RoleTenant"]
except ImportError:
    # Fallback: Create minimal placeholder to avoid startup errors
    print("[WARNING] Could not import RoleTenant from tenant models, using placeholder")
    from sqlalchemy import Column, Integer, String
    from sqlalchemy.ext.declarative import declarative_base
    
    Base = declarative_base()
    
    class RoleTenant(Base):
        """TEMPORARY PLACEHOLDER for RoleTenant model"""
        __tablename__ = "roles_tenant"
        
        id = Column(Integer, primary_key=True, index=True)
        nome = Column(String(100), nullable=False, unique=True)
        descricao = Column(String(255), nullable=True)
    
    __all__ = ["RoleTenant"]
