from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from app.models.patient import GenderEnum

class PatientBase(BaseModel):
    mrn: str = Field(..., example="MRN123456")
    first_name: str = Field(..., example="John")
    last_name: str = Field(..., example="Doe")
    birth_date: datetime = Field(..., example="1970-01-01T00:00:00")
    gender: GenderEnum

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    mrn: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[datetime] = None
    gender: Optional[GenderEnum] = None

class PatientInDBBase(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PatientInDB(PatientInDBBase):
    pass

class Patient(PatientInDBBase):
    pass
