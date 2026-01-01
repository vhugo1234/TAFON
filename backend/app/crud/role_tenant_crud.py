from sqlalchemy.orm import Session
from app.db.models.role_tenant import RoleTenant
from app.api.schemas.role_tenant import RoleTenantCreate, RoleTenantUpdate

def create_role(db: Session, obj_in: RoleTenantCreate):
    role = RoleTenant(**obj_in.dict())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

def get_role(db: Session, role_id: int):
    return db.query(RoleTenant).filter(RoleTenant.id == role_id).first()

def get_roles(db: Session):
    return db.query(RoleTenant).all()

def update_role(db: Session, role: RoleTenant, obj_in: RoleTenantUpdate):
    for field, value in obj_in.dict(exclude_unset=True).items():
        setattr(role, field, value)
    db.commit()
    db.refresh(role)
    return role

def delete_role(db: Session, role_id: int):
    role = get_role(db, role_id)
    if role:
        db.delete(role)
        db.commit()