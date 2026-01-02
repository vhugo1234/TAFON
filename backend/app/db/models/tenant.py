# backend/app/db/models/tenant.py
# Modelos do schema 'tenant' (por cliente). Usa TenantBase separado.

from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, Float, func, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from enum import Enum as PyEnum

# Base para todos os modelos que pertencerão ao schema do Tenant
TenantBase = declarative_base()

class UserRoleEnum(str, PyEnum):
    ADMIN = "admin"
    USER = "user"

# ----------------------------------------------------
# MÓDULO 1: EVENTOS (O TAF)
# ----------------------------------------------------
class Event(TenantBase):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
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
    name = Column(String)
    unit_of_measure = Column(String)
    max_attempts = Column(Integer, default=1)

    event = relationship("Event", back_populates="exercises")
    criteria = relationship("PassCriteria", back_populates="exercise")


class PassCriteria(TenantBase):
    __tablename__ = "pass_criteria"
    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    gender = Column(String(1), index=True)
    min_value = Column(Float)
    max_time_s = Column(Integer, nullable=True)

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
    registration_number = Column(String, index=True)
    gender = Column(String(1))

    batch_name = Column(String, nullable=True)

    event = relationship("Event", back_populates="candidates")
    results = relationship("ExecutionResult", back_populates="candidate")


class ExecutionResult(TenantBase):
    __tablename__ = "execution_results"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    exercise_id = Column(Integer, ForeignKey("exercises.id"))
    evaluator_user_id = Column(Integer, nullable=True)

    measured_value = Column(Float)
    attempt_number = Column(Integer)
    is_valid = Column(Boolean, default=True)
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

# Requerido pelo módulo de usuários
class RoleTenant(TenantBase):
    __tablename__ = "roles_tenant"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False, unique=True)
    descricao = Column(String(255), nullable=True)