from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RequestBaseModel(BaseModel):
    """Common configuration for incoming OPD prescription sections."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )


# ---------------------------------------------------------------------
# Chief complaints
# ---------------------------------------------------------------------

class ChiefComplaint(RequestBaseModel):
    name: Optional[str] = Field(default=None, alias="RN")
    duration: Optional[str] = Field(default=None, alias="DU")


# ---------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------

class DiagnosisItem(RequestBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    diagnosis_type: Optional[str] = Field(default=None, alias="TypeName")


class Diagnosis(RequestBaseModel):
    items: Optional[list[DiagnosisItem]] = Field(
        default=None, alias="DG"
    )
    note: Optional[str] = Field(default=None, alias="DGNOTE")
    remarks: Optional[str] = Field(default=None, alias="rem")


# ---------------------------------------------------------------------
# Investigations
# ---------------------------------------------------------------------

class Investigation(RequestBaseModel):
    name: Optional[str] = Field(default=None, alias="TN")
    remarks: Optional[str] = Field(default=None, alias="REM")


# ---------------------------------------------------------------------
# Medications
# ---------------------------------------------------------------------

class Medication(RequestBaseModel):
    name: Optional[str] = Field(default=None, alias="DRN")
    dose: Optional[str] = Field(default=None, alias="DSN")
    frequency: Optional[str] = Field(default=None, alias="FRQ")
    duration_days: Optional[str | int] = Field(default=None, alias="DYS")
    quantity: Optional[int | float | str] = Field(default=None, alias="QTY")
    instructions: Optional[str] = Field(default=None, alias="IST")
    additional_text: Optional[str] = Field(default=None, alias="DRTN")


# ---------------------------------------------------------------------
# Follow-up
# ---------------------------------------------------------------------

class FollowUp(RequestBaseModel):
    is_end: Optional[str] = Field(default=None, alias="IsEnd")
    note: Optional[str] = Field(default=None, alias="NOTE")
    date: Optional[str] = Field(default=None, alias="DATE")


# ---------------------------------------------------------------------
# Clinical procedures
# ---------------------------------------------------------------------

class ClinicalProcedure(RequestBaseModel):
    name: Optional[str] = Field(default=None, alias="procname")


# ---------------------------------------------------------------------
# Referrals
# ---------------------------------------------------------------------

class Referral(RequestBaseModel):
    department: Optional[str] = Field(
        default=None, alias="referdeptname"
    )
    referral_type: Optional[str] = Field(
        default=None, alias="refertypename"
    )
    reason: Optional[str] = Field(
        default=None, alias="referreason"
    )


# ---------------------------------------------------------------------
# Patient history
# ---------------------------------------------------------------------

class PatientHistory(RequestBaseModel):
    past_history: Optional[str] = Field(
        default=None, alias="strpastHistory"
    )
    personal_history: Optional[str] = Field(
        default=None, alias="strpersonalHistory"
    )
    family_history: Optional[str] = Field(
        default=None, alias="strfamilyHistory"
    )
    treatment_history: Optional[str] = Field(
        default=None, alias="strtreatmentHistory"
    )
    surgical_history: Optional[str] = Field(
        default=None, alias="strsurgicalHistory"
    )


# ---------------------------------------------------------------------
# Systematic examination
# ---------------------------------------------------------------------

class SystematicExamination(RequestBaseModel):
    cardiovascular: Optional[str] = Field(
        default=None, alias="strcvs"
    )
    respiratory: Optional[str] = Field(
        default=None, alias="strrs"
    )
    central_nervous_system: Optional[str] = Field(
        default=None, alias="strcns"
    )
    abdomen: Optional[str] = Field(default=None, alias="strpA")
    other_examination: Optional[str] = Field(
        default=None, alias="strotherExamn"
    )
    musculoskeletal: Optional[str] = Field(
        default=None, alias="strmuscularExamn"
    )
    local_examination: Optional[str] = Field(
        default=None, alias="strLocalExamn"
    )


# ---------------------------------------------------------------------
# Chronic diseases
# ---------------------------------------------------------------------

class ChronicDisease(RequestBaseModel):
    name: Optional[str] = Field(
        default=None, alias="CronicDiseaseName"
    )
    duration: Optional[str] = Field(
        default=None, alias="CronicDiseaseDuration"
    )
    remarks: Optional[str] = Field(
        default=None, alias="CronicDiseaseRemarks"
    )


# ---------------------------------------------------------------------
# Drug allergies
# ---------------------------------------------------------------------

class DrugAllergy(RequestBaseModel):
    sensitivity_type: Optional[str] = Field(
        default=None, alias="strSensivityName"
    )
    allergy_name: Optional[str] = Field(
        default=None, alias="strAllergyName"
    )
    site: Optional[str] = Field(
        default=None, alias="strAllergysiteName"
    )
    symptoms: Optional[str] = Field(
        default=None, alias="strAllergySytmptomsName"
    )
    remarks: Optional[str] = Field(
        default=None, alias="strAllergyRemarks"
    )
    duration: Optional[str] = Field(
        default=None, alias="stDurationTime"
    )


# ---------------------------------------------------------------------
# Clinical signs
# ---------------------------------------------------------------------

class ClinicalSigns(RequestBaseModel):
    pallor: Optional[str] = Field(default=None, alias="strpallor")
    icterus: Optional[str] = Field(default=None, alias="stricterus")
    cyanosis: Optional[str] = Field(default=None, alias="strcyanosis")
    clubbing: Optional[str] = Field(default=None, alias="strclubbing")
    lymphadenopathy: Optional[str] = Field(
        default=None, alias="striymphadenopathyId"
    )
    edema: Optional[str] = Field(default=None, alias="stredema")


# ---------------------------------------------------------------------
# Main OPD prescription request
# ---------------------------------------------------------------------

class OPDPrescriptionRequest(RequestBaseModel):
    # Presenting complaints and current illness
    chief_complaints: Optional[list[ChiefComplaint]] = Field(
        default=None, alias="CC"
    )
    history_of_present_illness: Optional[str] = Field(
        default=None, alias="HOPI"
    )

    # Diagnosis, investigations, and treatment
    diagnosis: Optional[Diagnosis] = Field(
        default=None, alias="DIAG"
    )
    investigations: Optional[list[Investigation]] = Field(
        default=None, alias="INV"
    )
    medications: Optional[list[Medication]] = Field(
        default=None, alias="DRUG"
    )
    follow_ups: Optional[list[FollowUp]] = Field(
        default=None, alias="FUP"
    )
    clinical_procedures: Optional[list[ClinicalProcedure]] = Field(
        default=None, alias="clinicalproc"
    )
    referrals: Optional[list[Referral]] = Field(
        default=None, alias="strReferal"
    )

    # Patient and visit details
    patient_name: Optional[str] = Field(
        default=None, alias="pat_Name"
    )
    patient_age: Optional[str] = Field(default=None, alias="patAge")
    patient_gender: Optional[str] = Field(
        default=None, alias="patGender"
    )
    patient_category: Optional[str] = Field(
        default=None, alias="patCat"
    )
    current_visit_date: Optional[str] = Field(
        default=None, alias="currentVisitDate"
    )
    last_visit_date: Optional[str] = Field(
        default=None, alias="lastVisitDate"
    )
    consultant_name: Optional[str] = Field(
        default=None, alias="patConsultantName"
    )
    department: Optional[str] = Field(default=None, alias="patDept")

    # Medical history
    patient_history: Optional[PatientHistory] = Field(
        default=None, alias="strCompleteHistory"
    )
    chronic_diseases: Optional[list[ChronicDisease]] = Field(
        default=None, alias="strChronicDisease"
    )

    # Examination and allergies
    systematic_examination: Optional[SystematicExamination] = Field(
        default=None, alias="strSystematicExamniation"
    )
    clinical_signs: Optional[ClinicalSigns] = Field(
        default=None, alias="strpiccle"
    )
    drug_allergies: Optional[list[DrugAllergy]] = Field(
        default=None, alias="strDrugAllergy"
    )
    other_allergies: Optional[str] = Field(
        default=None, alias="strotherAllergies"
    )

    # Additional clinical notes
    diagnosis_note: Optional[str] = Field(
        default=None, alias="strDiagnosisNote"
    )
    investigation_note: Optional[str] = Field(
        default=None, alias="strInvestgationNote"
    )
    treatment_advice: Optional[str] = Field(
        default=None, alias="strtreatmentAdvice"
    )
    vitals: Optional[str] = Field(
        default=None, alias="strVitalsChart"
    )
