from __future__ import annotations
from typing import Optional, Any, List
from pydantic import BaseModel, ConfigDict, field_validator, EmailStr
from decimal import Decimal
import re

class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _clean_cpf(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 11 else value


def _clean_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits


class EntryItem(BaseModel):
    participant_id: Optional[Any] = None
    participant_name: Optional[str] = None
    role: Optional[str] = None
    role_id: Optional[Any] = None
    email: Optional[EmailStr] = None
    cpf: Optional[str] = None
    phone: Optional[str] = None
    pix: Optional[str] = None
    bank: Optional[str] = None
    agency: Optional[str] = None
    account: Optional[str] = None
    unit_amount: Optional[float] = 0.0
    days: Optional[int] = 1
    total_per_person: Optional[float] = None
    total_line: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("cpf")
    @classmethod
    def _norm_cpf(cls, v):
        return _clean_cpf(v)

    @field_validator("phone")
    @classmethod
    def _norm_phone(cls, v):
        return _clean_phone(v)


class Options(BaseModel):
    grouped: bool = True
    include_bank_details: bool = True


class ExportPayload(BaseModel):
    event_id: Optional[int] = None
    event_name: Optional[str] = ""
    entries: List[EntryItem] = []
    options: Options = Options()

    # limit rows to avoid huge payload by accident (adjust as needed)
    @field_validator("entries")
    @classmethod
    def check_entries_length(cls, v):
        max_rows = 2000
        if len(v) > max_rows:
            raise ValueError(f"Máximo de {max_rows} entradas por exportação")
        return v
