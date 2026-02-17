from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

class AttendanceCreate(BaseModel):
    signature_data: str            # data URI (data:image/png;base64,...) - obrigatório no MVP
    photo_data: Optional[str] = None  # opcional, data URI
    lat: Optional[float] = None
    lng: Optional[float] = None
    date: Optional[date] = None    # YYYY-MM-DD (se omisso usa hoje)

class AttendanceOut(BaseModel):
    id: int
    event_id: int
    event_worker_id: Optional[int]
    user_id: Optional[int]
    attendance_date: date
    check_in_at: Optional[datetime]
    check_out_at: Optional[datetime]
    check_in_signature_path: Optional[str]
    check_in_signature_hash: Optional[str]
    status: Optional[str]

    class Config:
        orm_mode = True
