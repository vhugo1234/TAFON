# -*- coding: utf-8 -*-
# backend/app/db/models/tenant.py
# Modelos do schema 'tenant' (por cliente). Usa TenantBase separado.

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey, Float, Numeric, func, Enum as SQLEnum, Index
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey, Float, Numeric, func, Enum as SQLEnum, Index
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
    name = Column(String, index=True)
    date_start = Column(Date)
    date_end = Column(Date)
    location = Column(String)
    is_active = Column(Boolean, default=True)

    # Cascata ORM + passive_deletes para confiar no DB quando FK tem ON DELETE CASCADE
    exercises = relationship(
        "Exercise",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    candidates = relationship(
        "Candidate",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    # NOVO: datas explícitas do evento (opcional)
    dates = relationship(
        "EventDate",
        cascade="all, delete-orphan",
        back_populates="event",
        passive_deletes=True
    )

    # === ADICIONAR AQUI: vínculo opcional com o usuário coordenador ===
    coordinator_id = Column(Integer, ForeignKey("user_tenant.id", ondelete="SET NULL"), nullable=True, index=True)
    coordinator = relationship("UserTenant", foreign_keys=[coordinator_id], lazy="joined")
    # =============================================================

# NOVA TABELA: datas do evento (cada linha = um dia em que o evento ocorre)
class EventDate(TenantBase):
    __tablename__ = "event_dates"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="dates", passive_deletes=True)


class EventWorker(TenantBase):
    __tablename__ = "event_workers"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user_tenant.id", ondelete="SET NULL"), nullable=True, index=True)
    role_id = Column(Integer, nullable=True)           # referência para role id quando aplicável
    role_name = Column(String(128), nullable=True)     # texto quando não houver role_id
    days_assigned = Column(Integer, nullable=True)     # opcional: dias atribuídos para esse worker
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # relacionamentos de conveniência
    user = relationship("UserTenant", foreign_keys=[user_id], passive_deletes=True)
    event = relationship("Event", foreign_keys=[event_id], passive_deletes=True)


class EventWorkerAttendance(TenantBase):
    __tablename__ = "event_worker_attendance"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    event_worker_id = Column(Integer, ForeignKey("event_workers.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("user_tenant.id", ondelete="SET NULL"), nullable=True, index=True)

    attendance_date = Column(Date, nullable=False, index=True)
    check_in_at = Column(DateTime(timezone=True), nullable=True)
    check_out_at = Column(DateTime(timezone=True), nullable=True)

    check_in_signature_path = Column(Text, nullable=True)
    check_in_signature_hash = Column(String(64), nullable=True)
    check_in_photo_path = Column(Text, nullable=True)

    check_in_lat = Column(Numeric, nullable=True)
    check_in_lng = Column(Numeric, nullable=True)

    status = Column(String(32), nullable=True, default="checked_in")
    verified_by = Column(Integer, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # relationships convenience
    event = relationship("Event", foreign_keys=[event_id], passive_deletes=True)
    event_worker = relationship("EventWorker", foreign_keys=[event_worker_id], passive_deletes=True)
    user = relationship("UserTenant", foreign_keys=[user_id], passive_deletes=True)

# ----------------------------------------------------
# MÓDULO 2: EXERCÍCIOS E REGRAS
# ----------------------------------------------------
class Exercise(TenantBase):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"))
    name = Column(String)
    unit_of_measure = Column(String)
    max_attempts = Column(Integer, default=1)
    execution_mode = Column(String(20), nullable=False)
    measurement_type = Column(String(20), nullable=False)

    event = relationship("Event", back_populates="exercises", passive_deletes=True)
    criteria = relationship(
        "PassCriteria",
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    evaluators = relationship(
        "ExerciseEvaluator",
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class PassCriteria(TenantBase):
    __tablename__ = "pass_criteria"
    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"))
    gender = Column(String(1), index=True)
    min_value = Column(Float)
    max_time_s = Column(Integer, nullable=True)

    exercise = relationship("Exercise", back_populates="criteria", passive_deletes=True)


# ✅ NOVO: Vinculação de Avaliadores aos Exercícios
class ExerciseEvaluator(TenantBase):
    __tablename__ = "exercise_evaluators"
    
    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"))
    evaluator_user_id = Column(Integer, ForeignKey("user_tenant.id"))
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    exercise = relationship("Exercise", back_populates="evaluators", passive_deletes=True)
    evaluator = relationship("UserTenant")


# ----------------------------------------------------
# MÓDULO 3 & 4: CANDIDATOS E RESULTADOS DA EXECUÇÃO
# ----------------------------------------------------
class Candidate(TenantBase):
    __tablename__ = "candidates"
    
    __table_args__ = (
        # Constraint composta: CPF único POR EVENTO (permite mesmo CPF em eventos diferentes)
        Index('ix_candidates_cpf_event', 'cpf', 'event_id', unique=True),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"))
    full_name = Column(String)
    cpf = Column(String(11), index=True)  # ✅ Removido unique=True global
    registration_number = Column(String, index=True)
    gender = Column(String(1))
    batch_name = Column(String, nullable=True)
    batch_number = Column(Integer, nullable=True)  # ✅ NOVO: Número dentro da turma (001, 002, 003...)
    start_time = Column(String(5), nullable=True)  # ✅ NOVO: Horário da turma (HH:MM)
    start_date = Column(Date, nullable=True)

    event = relationship("Event", back_populates="candidates", passive_deletes=True)
    results = relationship(
        "ExecutionResult",
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class ExecutionResult(TenantBase):
    __tablename__ = "execution_results"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"))
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"))
    evaluator_user_id = Column(Integer, nullable=True)

    measured_value = Column(Float)
    attempt_number = Column(Integer)
    is_valid = Column(Boolean, default=True)
    is_approved_in_exercise = Column(Boolean, nullable=True)

    candidate = relationship("Candidate", back_populates="results", passive_deletes=True)
    exercise = relationship("Exercise", passive_deletes=True)


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
    custom_role = Column(String(128), nullable=True)
    accepted_terms = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    cref = Column(String(128), nullable=True)

    # Banking fields (new)
    bank_name = Column(String(128), nullable=True)
    pix = Column(String(128), nullable=True)
    bank_account = Column(String(64), nullable=True)
    agency = Column(String(64), nullable=True)

    # Signature metadata (new)
    signature_path = Column(String(512), nullable=True)
    signature_hash = Column(String(64), nullable=True)
    signature_uploaded_at = Column(DateTime(timezone=True), nullable=True)
    signature_verified = Column(Boolean, default=False)
    
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
