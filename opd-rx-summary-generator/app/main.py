import logging
import os

from fastapi import FastAPI

from app.schemas.request import OPDPrescriptionRequest
from app.schemas.response import (
    ClinicalSections,
    MedicationSummary,
    OPDPrescriptionResponse,
)
from app.services.deterministic_summary import (
    build_deterministic_summary,
)
from app.services.fact_extractor import (
    _clean,
    extract_clinical_facts,
)
from app.services.summarizer import ClinicalSummarizer
# from app.services.summary_validator import validate_summary


logger = logging.getLogger(__name__)

ENABLE_QWEN_SUMMARIZER = (
    os.getenv("ENABLE_QWEN_SUMMARIZER", "true")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

_summarizer: ClinicalSummarizer | None = None


app = FastAPI(
    title="OPD Prescription Summary Generator",
    description=(
        "Generates source-grounded clinical summaries "
        "from outpatient prescription data."
    ),
    version="0.1.0",
)


def get_summarizer() -> ClinicalSummarizer:
    """Load the summarizer lazily so the API can start without the model."""
    global _summarizer

    if _summarizer is None:
        _summarizer = ClinicalSummarizer()

    return _summarizer


def generate_summary(
    request: OPDPrescriptionRequest,
) -> str:
    """Generate a Qwen summary, falling back on failure."""
    fallback_summary = build_deterministic_summary(request)

    if not ENABLE_QWEN_SUMMARIZER:
        return fallback_summary

    try:
        clinical_facts = extract_clinical_facts(request)

        if not clinical_facts or not clinical_facts.strip():
            logger.warning("No clinical facts available; using deterministic summary.")
            return fallback_summary

        candidate_summary = get_summarizer().summarize(clinical_facts)

        if candidate_summary and candidate_summary.strip():
            logger.info("Qwen summary generated successfully.")
            return candidate_summary.strip()

        logger.warning("Qwen returned an empty summary; using deterministic fallback.")

    except Exception as exc:
        logger.warning(
            "Qwen generation failed (%s); using deterministic fallback.",
            type(exc).__name__,
        )

    return fallback_summary


def build_sections(
    request: OPDPrescriptionRequest,
) -> ClinicalSections:
    """Build structured sections directly from the input request."""

    # Chief complaints and durations
    chief_complaints = []

    for complaint in request.chief_complaints or []:
        name = _clean(complaint.name)
        duration = _clean(complaint.duration)

        if not name:
            continue

        if duration:
            chief_complaints.append(f"{name} for {duration}")
        else:
            chief_complaints.append(name)

    # Diagnoses
    diagnoses = []

    if request.diagnosis:
        for item in request.diagnosis.items or []:
            name = _clean(item.name)
            if name and name not in diagnoses:
                diagnoses.append(name)

        for note in (
            request.diagnosis.note,
            request.diagnosis.remarks,
            request.diagnosis_note,
        ):
            value = _clean(note)
            if value:
                diagnoses.append(value)

    # Investigations: listed investigations are not assumed results.
    investigations = []

    for item in request.investigations or []:
        name = _clean(item.name)
        remarks = _clean(item.remarks)

        if name:
            value = f"{name} — {remarks}" if remarks else name
            investigations.append(value)

    if request.investigation_note:
        note = _clean(request.investigation_note)
        if note:
            investigations.append(note)

    # Medication details are mapped field by field from the input.
    medications = []

    for item in request.medications or []:
        name = _clean(item.name)
        if not name:
            continue

        medications.append(
            MedicationSummary(
                name=name,
                dose=_clean(item.dose),
                frequency=_clean(item.frequency),
                duration=_clean(item.duration_days),
                quantity=_clean(item.quantity),
                instructions=_clean(item.instructions),
            )
        )

    # Procedures
    procedures = [
        name
        for item in request.clinical_procedures or []
        if (name := _clean(item.name))
    ]

    # Referrals
    referrals = []

    for item in request.referrals or []:
        details = [
            _clean(item.department),
            _clean(item.referral_type),
            _clean(item.reason),
        ]
        details = [value for value in details if value]

        if details:
            referrals.append("; ".join(details))

    # Follow-up
    follow_up_items = []

    for item in request.follow_ups or []:
        note = _clean(item.note)
        date = _clean(item.date)

        if note:
            follow_up_items.append(note)
        if date:
            follow_up_items.append(f"Date: {date}")

    follow_up = "; ".join(follow_up_items) or None

    # Relevant history
    relevant_history = []
    history = request.patient_history

    if history:
        for label, value in (
            ("Past history", history.past_history),
            ("Personal history", history.personal_history),
            ("Family history", history.family_history),
            ("Treatment history", history.treatment_history),
            ("Surgical history", history.surgical_history),
        ):
            cleaned = _clean(value)
            if cleaned:
                relevant_history.append(f"{label}: {cleaned}")

    for item in request.chronic_diseases or []:
        name = _clean(item.name)
        if not name:
            continue

        details = [name]
        duration = _clean(item.duration)
        remarks = _clean(item.remarks)

        if duration:
            details.append(f"Duration: {duration}")
        if remarks:
            details.append(f"Remarks: {remarks}")

        relevant_history.append("; ".join(details))

    # Examination findings: retain supplied values without interpretation.
    examination_findings = []
    examination = request.systematic_examination

    if examination:
        for label, value in (
            ("Cardiovascular", examination.cardiovascular),
            ("Respiratory", examination.respiratory),
            ("Central nervous system", examination.central_nervous_system),
            ("Abdomen", examination.abdomen),
            ("Other examination", examination.other_examination),
            ("Musculoskeletal", examination.musculoskeletal),
            ("Local examination", examination.local_examination),
        ):
            cleaned = _clean(value)
            if cleaned:
                examination_findings.append(f"{label}: {cleaned}")

    signs = request.clinical_signs

    if signs:
        for label, value in (
            ("Pallor", signs.pallor),
            ("Icterus", signs.icterus),
            ("Cyanosis", signs.cyanosis),
            ("Clubbing", signs.clubbing),
            ("Lymphadenopathy", signs.lymphadenopathy),
            ("Edema", signs.edema),
        ):
            cleaned = _clean(value)
            if cleaned:
                examination_findings.append(f"{label}: {cleaned}")

    # Allergies
    allergies = []

    for item in request.drug_allergies or []:
        details = [
            _clean(item.sensitivity_type),
            _clean(item.allergy_name),
            _clean(item.site),
            _clean(item.symptoms),
            _clean(item.remarks),
            _clean(item.duration),
        ]
        details = [value for value in details if value]

        if details:
            allergies.append("; ".join(details))

    other_allergies = _clean(request.other_allergies)
    if other_allergies:
        allergies.append(other_allergies)

    # History of present illness and treatment advice
    hopi = _clean(request.history_of_present_illness)
    treatment_advice = _clean(request.treatment_advice)

    return ClinicalSections(
        chief_complaints=chief_complaints,
        history_of_present_illness=hopi,
        diagnoses=diagnoses,
        investigations=investigations,
        medications=medications,
        procedures=procedures,
        referrals=referrals,
        follow_up=follow_up,
        relevant_history=relevant_history,
        examination_findings=examination_findings,
        allergies=allergies,
        treatment_advice=treatment_advice,
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post(
    "/summarize",
    response_model=OPDPrescriptionResponse,
)
def summarize_prescription(
    request: OPDPrescriptionRequest,
) -> OPDPrescriptionResponse:
    summary = generate_summary(request)
    sections = build_sections(request)

    return OPDPrescriptionResponse(
        patient_name=_clean(request.patient_name),
        summary=summary,
        sections=sections,
    )
