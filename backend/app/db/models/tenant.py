# backend/app/db/models/tenant.py (Exemplo)

from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Float, func, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
import enum

# Base para todos os modelos que pertencerão ao schema do Tenant
TenantBase = declarative_base() 

class UserRoleEnum(str, enum.Enum):
    """Enum for user roles in tenant schema"""
    ADMIN = "admin"
    USER = "user"
    
# Keep old name for compatibility
UserRole = UserRoleEnum
    
# ----------------------------------------------------
# MÓDULO 1: EVENTOS (O TAF)
# ----------------------------------------------------

class Event(TenantBase):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)           # Nome do Concurso/Seleção
    date_start = Column(Date)
    date_end = Column(Date)
    location = Column(String)
    is_active = Column(Boolean, default=True)

    exercises = relationship("Exercise", back_populates="event")
    candidates = relationship("Candidate", back_populates="event")

# ----------------------------------------------------
# MÓDULO 2: EXERCÍCIOS E REGRAS
# ----------------------------------------------------

class Exercise(TenantBase):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String)                       # Ex: "Corrida 2400m", "Flexão na Barra Fixa"
    unit_of_measure = Column(String)            # Ex: "Tempo (Segundos)", "Distância (Metros)", "Repetições"
    max_attempts = Column(Integer, default=1)   # Tentativas permitidas

    event = relationship("Event", back_populates="exercises")
    criteria = relationship("PassCriteria", back_populates="exercise")


class PassCriteria(TenantBase):
    __tablename__ = "pass_criteria"
    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    gender = Column(String(1), index=True)      # 'M' ou 'F'
    min_value = Column(Float)                   # Valor MÍNIMO para aprovação
    max_time_s = Column(Integer, nullable=True) # Tempo MÁXIMO (para corridas)

    exercise = relationship("Exercise", back_populates="criteria")

# ----------------------------------------------------
# MÓDULO 3 & 4: CANDIDATOS E RESULTADOS DA EXECUÇÃO
# ----------------------------------------------------

class Candidate(TenantBase):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    full_name = Column(String)
    cpf = Column(String(11), unique=True, index=True)
    registration_number = Column(String, index=True) # Número de Inscrição no Concurso
    gender = Column(String(1)) # M/F
    
    batch_name = Column(String, nullable=True) # Turma/Bateria (para organização do dia)

    event = relationship("Event", back_populates="candidates")
    results = relationship("ExecutionResult", back_populates="candidate")


class ExecutionResult(TenantBase):
    __tablename__ = "execution_results"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    evaluator_user_id = Column(Integer, nullable=True) # ID do Avaliador (UserTenant)
    
    measured_value = Column(Float)              # O valor lançado (Ex: 11.5 repetições, 7:55 minutos, 2400 metros)
    attempt_number = Column(Integer)            # 1, 2, 3...
    is_valid = Column(Boolean, default=True)    # Se foi validado pelo avaliador
    
    # ----------------------------------------------------
    # MÓDULO 5: RESULTADO CONSOLIDADO (Pode ser uma view ou calculado na API)
    # ----------------------------------------------------
    
    # Exemplo: O resultado final para aquela prova é calculado em tempo real ou
    # armazenado em outra coluna/tabela após a última tentativa.
    is_approved_in_exercise = Column(Boolean, nullable=True)

    candidate = relationship("Candidate", back_populates="results")
    exercise = relationship("Exercise") 

# Requerido pelo módulo de usuários (users.py e role_tenant.py)
class UserTenant(TenantBase):
    __tablename__ = "user_tenant"
    

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    cpf = Column(String(20), nullable=True)
    phone = Column(String(30), nullable=True)
    department = Column(String(128), nullable=True)
    institution = Column(String(128), nullable=True)
    birth_date = Column(String(12), nullable=True)                           
    notes = Column(String(512), nullable=True)
    address = Column(String(255), nullable=True)
    specialty = Column(String(128), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    role = Column(SQLEnum(UserRoleEnum), nullable=False, default=UserRoleEnum.USER)
    role_id = Column(Integer, ForeignKey("roles_tenant.id"))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    accepted_terms = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    role_obj = relationship("RoleTenant")
    itens = relationship("ItemTenant", back_populates="usuario", cascade="all, delete-orphan")
    pass

# Role/Permission model for tenants
class RoleTenant(TenantBase):
    """
    Roles and permissions for tenant users.
    """
    __tablename__ = "roles_tenant"
   
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False, unique=True)
    descricao = Column(String(255), nullable=True)
    pass

# TEMPORARY PLACEHOLDER: ItemTenant to avoid relationship errors
class ItemTenant(TenantBase):
    """
    TEMPORARY PLACEHOLDER for ItemTenant model.
    TODO: Implement actual ItemTenant model.
    """
    __tablename__ = "itens_tenant"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("user_tenant.id"), nullable=True)
    nome = Column(String(255), nullable=True)
    
    usuario = relationship("UserTenant", back_populates="itens")

# TEMPORARY FIX: Add compatibility exports for models that may be imported from public
try:
    from app.db.models.public import Tenant, UserCentral
    # Add to globals so they can be imported from this module
    globals()['Tenant'] = Tenant
    globals()['UserCentral'] = UserCentral
except ImportError:
    # If public models don't exist yet, set to None
    Tenant = None
    UserCentral = None