import os
import shutil
import uuid
from typing import Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

# Defensive imports from your project
try:
    from app.db.models.public import Tenant, UserCentral
except Exception:
    Tenant = None
    UserCentral = None

try:
    from app.db.models.tenant import TenantBase, UserTenant
except Exception:
    TenantBase = None
    UserTenant = None

try:
    from app.db.startup import initialize_tenant_schema
except Exception:
    initialize_tenant_schema = None

from app.db.connection import engine

# password hashing fallback
try:
    from app.core.security import get_password_hash  # project helper
except Exception:
    get_password_hash = None

try:
    from passlib.hash import pbkdf2_sha256 as _pbkdf2
except Exception:
    _pbkdf2 = None


def _truncate_password_to_72_bytes(s: str) -> str:
    if s is None:
        return ""
    b = s.encode("utf-8")
    if len(b) <= 72:
        return s
    truncated = b[:72]
    for end in range(len(truncated), 0, -1):
        try:
            return truncated[:end].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return ""


def _hash_password(pwd: str) -> str:
    if get_password_hash:
        try:
            return get_password_hash(pwd)
        except Exception:
            pass
    if _pbkdf2:
        return _pbkdf2.hash(pwd)
    raise RuntimeError("No password hash function available")


def list_tenants(db: Session):
    """
    Returns list of tenants from public.tenants with basic aggregates.
    Defensive: if Tenant model missing, returns empty list.
    """
    results = []
    if Tenant is None:
        return results

    tenants = db.query(Tenant).all()
    for t in tenants:
        # basic aggregates: user count in tenant (best-effort)
        users_total = 0
        try:
            # try to query tenant schema if exists
            db.execute(text('SET search_path TO public'))
            schema = getattr(t, "schema_name", None)
            if schema:
                db.execute(text(f'SET search_path TO "{schema}"'))
                if UserTenant is not None:
                    q = db.query(UserTenant).count()
                    users_total = q
        except Exception:
            users_total = 0
        finally:
            db.execute(text('SET search_path TO public'))

        results.append({
            "id": getattr(t, "id", None),
            "nome_empresa": getattr(t, "nome_empresa", None),
            "schema_name": getattr(t, "schema_name", None),
            "logo_url": getattr(t, "logo_url", None),
            "users_total": users_total,
            "plan_type": getattr(t, "plan_type", None) if hasattr(t, "plan_type") else None,
            "status": getattr(t, "status", None) if hasattr(t, "status") else "active",
        })
    return results


def _save_logo_file(upload_dir: str, file_obj) -> str:
    """
    Save UploadFile-like object to upload_dir and return relative path.
    upload_dir should be absolute path writable by process.
    """
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(getattr(file_obj, "filename", "") or "")[1] or ""
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(upload_dir, fname)

    # file_obj may be starlette UploadFile; it has .file or .read()
    try:
        with open(dest, "wb") as out_f:
            # If file_obj has .read, stream it
            chunk = file_obj.file.read(65536) if hasattr(file_obj, "file") else file_obj.read(65536)
            while chunk:
                out_f.write(chunk)
                chunk = file_obj.file.read(65536) if hasattr(file_obj, "file") else file_obj.read(65536)
    except Exception:
        # fallback using shutil (works if UploadFile.file is a SpooledTemporaryFile)
        try:
            file_obj.file.seek(0)
            with open(dest, "wb") as out_f:
                shutil.copyfileobj(file_obj.file, out_f)
        except Exception:
            raise

    # store path relative to /app (as your app serves uploads from /uploads)
    rel = os.path.join("/uploads", fname)
    return rel


def create_tenant_and_admin(db: Session, schema_name: str, nome_empresa: Optional[str], admin_email: Optional[str],
                            admin_password: Optional[str], admin_name: Optional[str]) -> Tuple[Optional[object], Optional[str]]:
    """
    Create a tenant in public.tenants, create tenant schema and tables, then create admin in tenant and central user.
    Returns (Tenant instance, admin_password_generated_or_provided)
    """
    pwd = admin_password or os.getenv("INITIAL_ADMIN_PASSWORD") or "ChangeMe123!"
    pwd = _truncate_password_to_72_bytes(pwd)
    hashed = _hash_password(pwd)

    # create public tenant row
    tenant_obj = None
    try:
        if Tenant is None:
            raise RuntimeError("Tenant model unavailable")
        # check exists
        existing = db.query(Tenant).filter(Tenant.schema_name == schema_name).first()
        if existing:
            tenant_obj = existing
        else:
            tenant_obj = Tenant(schema_name=schema_name, nome_empresa=nome_empresa)
            # set extra attrs if present
            if hasattr(Tenant, "status"):
                try:
                    tenant_obj.status = "active"
                except Exception:
                    pass
            db.add(tenant_obj)
            db.commit()
            db.refresh(tenant_obj)
    except Exception:
        db.rollback()
        raise

    # create schema and tables
    try:
        if initialize_tenant_schema is not None:
            initialize_tenant_schema(engine, schema_name)
        else:
            # fallback: create schema and call TenantBase.metadata.create_all with search_path
            with engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
                # If we have TenantBase metadata, create tables via conn after setting search_path
                if TenantBase is not None:
                    conn.execute(text(f'SET search_path TO "{schema_name}", public'))
                    TenantBase.metadata.create_all(bind=conn)
    except Exception:
        # not fatal for now (tables may exist)
        pass

    # create user in tenant schema
    tenant_user_id = None
    try:
        if UserTenant is not None:
            # use db session but ensure search_path
            db.execute(text(f'SET search_path TO "{schema_name}"'))
            existing_u = db.query(UserTenant).filter(UserTenant.email == admin_email).first() if admin_email else None
            if existing_u:
                tenant_user_id = getattr(existing_u, "id", None)
            else:
                params = {"nome": admin_name or "Admin", "email": admin_email or f"admin@{schema_name}.local", "hashed_password": hashed}
                cols = []
                try:
                    cols = list(UserTenant.__table__.c.keys())
                except Exception:
                    pass
                if "is_admin" in cols:
                    params["is_admin"] = True
                if "is_active" in cols:
                    params["is_active"] = True
                obj = UserTenant(**{k: v for k, v in params.items() if v is not None})
                db.add(obj)
                db.commit()
                db.refresh(obj)
                tenant_user_id = getattr(obj, "id", None)
            db.execute(text('SET search_path TO public'))
    except Exception:
        db.rollback()
        tenant_user_id = None

    # create central superuser
    try:
        if UserCentral is not None:
            db.execute(text('SET search_path TO public'))
            if not db.query(UserCentral).filter(UserCentral.email == admin_email).first():
                params = {"email": admin_email or f"admin@{schema_name}.local", "hashed_password": hashed}
                # set fields present
                try:
                    cols = list(UserCentral.__table__.c.keys())
                except Exception:
                    cols = []
                if "is_superuser" in cols:
                    params["is_superuser"] = True
                if "tenant_id" in cols:
                    params["tenant_id"] = getattr(tenant_obj, "id", None)
                if "tenant_user_id" in cols:
                    params["tenant_user_id"] = tenant_user_id
                # instantiate defensively
                try:
                    central_user = UserCentral()
                    for k, v in params.items():
                        if hasattr(central_user, k) or k in cols:
                            try:
                                setattr(central_user, k, v)
                            except Exception:
                                pass
                    db.add(central_user)
                    db.commit()
                    db.refresh(central_user)
                except TypeError:
                    # fallback: try passing allowed kwargs
                    central_user = UserCentral(**{k: v for k, v in params.items() if k in cols})
                    db.add(central_user)
                    db.commit()
                    db.refresh(central_user)
    except Exception:
        db.rollback()

    return tenant_obj, pwd