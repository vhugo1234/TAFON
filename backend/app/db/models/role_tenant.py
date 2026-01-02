# Compatibilidade: re-export para RoleTenant (expectativa de módulos antigos)
# Tenta importar a definição real em app.db.models.tenant; se falhar, fornece
# uma definição mínima para evitar ImportError durante o startup (útil em dev).

try:
    # Import real (o ideal é que RoleTenant esteja definido em tenant.py)
    from app.db.models.tenant import RoleTenant  # type: ignore
except Exception:
    # Fallback mínimo (só para evitar ImportError em tempo de import);
    # não é recomendado manter este fallback em produção — crie o RoleTenant real.
    from sqlalchemy import Column, Integer, String
    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()

    class RoleTenant(Base):
        __tablename__ = "roles_tenant"
        id = Column(Integer, primary_key=True, index=True)
        nome = Column(String(100), nullable=False, unique=True)
        descricao = Column(String(255), nullable=True)