from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from app.db.base import Base
import datetime
import enum

# Enums for FHIR resources
class ObservationStatusEnum(str, enum.Enum):
    REGISTERED = "registered"
    PRELIMINARY = "preliminary"
    FINAL = "final"
    AMENDED = "amended"
    CORRECTED = "corrected"
    CANCELLED = "cancelled"
    ENTERED_IN_ERROR = "entered-in-error"
    UNKNOWN = "unknown"

class EncounterStatusEnum(str, enum.Enum):
    PLANNED = "planned"
    ARRIVED = "arrived"
    TRIAGED = "triaged"
    IN_PROGRESS = "in-progress"
    ONLEAVE = "onleave"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    ENTERED_IN_ERROR = "entered-in-error"
    UNKNOWN = "unknown"

class ConditionClinicalStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    RECURRENCE = "recurrence"
    RELAPSE = "relapse"
    INACTIVE = "inactive"
    RESOLVED = "resolved"

class MedicationRequestStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    ON_HOLD = "on-hold"
    COMPLETED = "completed"
    ENTERED_IN_ERROR = "entered-in-error"
    STOPPED = "stopped"
    DRAFT = "draft"
    UNKNOWN = "unknown"

class AllergyIntoleranceStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RESOLVED = "resolved"

class AllergyIntoleranceCriticalityEnum(str, enum.Enum):
    LOW = "low"
    HIGH = "high"
    UNABLE_TO_ASSESS = "unable-to-assess"

# FHIR Resource Models
class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    status = Column(Enum(ObservationStatusEnum), nullable=False)
    category = Column(String)  # e.g., vital-signs, laboratory
    code = Column(String)  # LOINC code
    code_display = Column(String)
    subject_reference = Column(String)  # Reference to Patient
    effective_date_time = Column(DateTime)
    issued = Column(DateTime)
    value_quantity = Column(JSON)  # {value: float, unit: string, system: string, code: string}
    value_string = Column(String)
    value_boolean = Column(Boolean)
    components = Column(JSON)  # Array of component observations
    interpretation = Column(JSON)  # Array of interpretations
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="observations")

class Encounter(Base):
    __tablename__ = "encounters"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    status = Column(Enum(EncounterStatusEnum), nullable=False)
    class_code = Column(String)  # e.g., inpatient, outpatient, ambulatory
    class_display = Column(String)
    type = Column(JSON)  # Array of types
    service_type = Column(JSON)
    subject_reference = Column(String)  # Reference to Patient
    participant = Column(JSON)  # Array of participants
    appointment_reference = Column(String)  # Reference to Appointment
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    length = Column(JSON)  # {value: float, unit: string}
    reason_code = Column(JSON)  # Array of reasons
    hospitalization = Column(JSON)  # Details about hospitalization
    location = Column(JSON)  # Array of locations
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="encounters")

class Condition(Base):
    __tablename__ = "conditions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    clinical_status = Column(Enum(ConditionClinicalStatusEnum))
    verification_status = Column(String)  # e.g., unconfirmed, provisional, confirmed
    category = Column(JSON)  # Array of categories
    severity = Column(JSON)  # CodeableConcept
    code = Column(JSON)  # CodeableConcept
    body_site = Column(JSON)  # CodeableConcept
    subject_reference = Column(String)  # Reference to Patient
    encounter_reference = Column(String)  # Reference to Encounter
    onset_date_time = Column(DateTime)
    onset_age = Column(JSON)
    onset_period = Column(JSON)
    onset_range = Column(JSON)
    onset_string = Column(String)
    abatement_date_time = Column(DateTime)
    abatement_age = Column(JSON)
    abatement_period = Column(JSON)
    abatement_range = Column(JSON)
    abatement_string = Column(String)
    recorded_date = Column(DateTime)
    recorder_reference = Column(String)  # Reference to Practitioner
    asserter_reference = Column(String)  # Reference to Practitioner
    stage = Column(JSON)  # Stage/grade
    evidence = Column(JSON)  # Supporting evidence
    note = Column(JSON)  # Array of annotations
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="conditions")

class MedicationRequest(Base):
    __tablename__ = "medication_requests"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    status = Column(Enum(MedicationRequestStatusEnum), nullable=False)
    intent = Column(String)  # e.g., proposal, plan, order
    category = Column(String)  # e.g., inpatient, outpatient
    priority = Column(String)  # routine, urgent, stat, asap
    medication_codeable_concept = Column(JSON)  # CodeableConcept
    medication_reference = Column(String)  # Reference to Medication
    subject_reference = Column(String)  # Reference to Patient
    encounter_reference = Column(String)  # Reference to Encounter
    authored_on = Column(DateTime)
    requester_reference = Column(String)  # Reference to Practitioner
    performer_reference = Column(String)  # Reference to Practitioner
    performer_type = Column(JSON)  # Array of codes
    recorder = Column(String)  # Reference to Practitioner
    reason_code = Column(JSON)  # Array of CodeableConcept
    reason_reference = Column(JSON)  # Array of References
    instantiates_canonical = Column(String)  # Canonical URL
    instantiates_uri = Column(String)  # URI
    based_on = Column(JSON)  # Array of References
    group_identifier = Column(JSON)  # Identifier
    course_of_therapy_type = Column(JSON)  # CodeableConcept
    insurance = Column(JSON)  # Array of References
    note = Column(JSON)  # Array of annotations
    dosage_instruction = Column(JSON)  # Array of Dosage
    dispense_request = Column(JSON)  # DispenseRequest
    substitution = Column(JSON)  # Substitution
    prior_prescription = Column(String)  # Reference to MedicationRequest
    detected_issue = Column(JSON)  # Array of References
    event_history = Column(JSON)  # Array of Events
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="medication_requests")

class AllergyIntolerance(Base):
    __tablename__ = "allergy_intolerances"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    status = Column(Enum(AllergyIntoleranceStatusEnum))
    criticality = Column(Enum(AllergyIntoleranceCriticalityEnum))
    type = Column(String)  # allergy or intolerance
    category = Column(JSON)  # Array of categories (food, medication, environment, biologic)
    code = Column(JSON)  # CodeableConcept
    patient_reference = Column(String)  # Reference to Patient
    encounter_reference = Column(String)  # Reference to Encounter
    onset_date_time = Column(DateTime)
    onset_age = Column(JSON)
    onset_period = Column(JSON)
    onset_range = Column(JSON)
    onset_string = Column(String)
    recorded_date = Column(DateTime)
    recorder_reference = Column(String)  # Reference to Practitioner
    asserter_reference = Column(String)  # Reference to Practitioner
    last_occurrence = Column(DateTime)
    note = Column(JSON)  # Array of annotations
    reaction = Column(JSON)  # Array of reactions
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="allergies")
