from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate, PatientInDB, Patient

router = APIRouter()

@router.post("/", response_model=PatientInDB, status_code=status.HTTP_201_CREATED)
def create_patient(
    patient_in: PatientCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new patient.
    """
    patient = db.query(Patient).filter(Patient.mrn == patient_in.mrn).first()
    if patient:
        raise HTTPException(
            status_code=400,
            detail="The patient with this MRN already exists in the system.",
        )
    patient = Patient(
        mrn=patient_in.mrn,
        first_name=patient_in.first_name,
        last_name=patient_in.last_name,
        birth_date=patient_in.birth_date,
        gender=patient_in.gender
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient

@router.get("/", response_model=List[PatientInDB])
def read_patients(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    mrn: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
):
    """
    Retrieve patients with optional filtering.
    """
    query = db.query(Patient)
    if mrn:
        query = query.filter(Patient.mrn.ilike(f"%{mrn}%"))
    if first_name:
        query = query.filter(Patient.first_name.ilike(f"%{first_name}%"))
    if last_name:
        query = query.filter(Patient.last_name.ilike(f"%{last_name}%"))
    patients = query.offset(skip).limit(limit).all()
    return patients

@router.get("/{patient_id}", response_model=PatientInDB)
def read_patient(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific patient by ID.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )
    return patient

@router.put("/{patient_id}", response_model=PatientInDB)
def update_patient(
    patient_id: int,
    patient_in: PatientUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a patient.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )
    update_data = patient_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patient, field, value)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient

@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a patient.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )
    db.delete(patient)
    db.commit()
    return None
