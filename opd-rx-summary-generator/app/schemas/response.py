from typing import Optional

from pydantic import BaseModel, Field


class MedicationSummary(BaseModel):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    quantity: Optional[str] = None
    instructions: Optional[str] = None


class ClinicalSections(BaseModel):
    chief_complaints: list[str] = Field(default_factory=list)
    history_of_present_illness: Optional[str] = None
    diagnoses: list[str] = Field(default_factory=list)
    investigations: list[str] = Field(default_factory=list)
    medications: list[MedicationSummary] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)
    referrals: list[str] = Field(default_factory=list)
    follow_up: Optional[str] = None
    relevant_history: list[str] = Field(default_factory=list)
    examination_findings: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    treatment_advice: Optional[str] = None


class OPDPrescriptionResponse(BaseModel):
    patient_name: Optional[str] = None
    summary: str
    sections: ClinicalSections
