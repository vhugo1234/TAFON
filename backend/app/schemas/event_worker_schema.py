from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EventWorkerCreate(BaseModel):
    user_id: int
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    days_assigned: Optional[int] = None

class EventWorkerUpdate(BaseModel):
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    days_assigned: Optional[int] = None

class EventWorkerOut(BaseModel):
    id: int
    event_id: int
    user_id: Optional[int]
    role_id: Optional[int]
    role_name: Optional[str]
    days_assigned: Optional[int]
    created_at: Optional[datetime]

    class Config:
        orm_mode = True
