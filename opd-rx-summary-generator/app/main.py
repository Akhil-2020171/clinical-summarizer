import logging
import os
import re

from fastapi import FastAPI

from app.schemas.request import OPDPrescriptionRequest
from app.schemas.response import (
    ClinicalSections,
    MedicationSummary,
    OPDPrescriptionResponse,
)
from app.services.brief_facts import build_brief_facts
from app.services.fact_extractor import _clean
from app.services.summarizer import ClinicalSummarizer
from app.services.summary_validator import validate_brief_summary


_YES_NO = {"1": "Yes", "0": "No"}


def _text(value):
    """Clean a value: placeholders removed, spaces collapsed, stray ; , trimmed."""
    cleaned = _clean(value)
    if not cleaned:
        return None
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ;,")
    return cleaned or None


def _name(value):
    """Clean a name: also drop codes like '[ 733 ]' and empty brackets like '(X )'."""
    cleaned = _clean(value)
    if not cleaned:
        return None
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\(\s*[A-Za-z]?\s*\)", "", cleaned)
    return _text(cleaned)


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
    """Create the llama-server client lazily."""
    global _summarizer

    if _summarizer is None:
        _summarizer = ClinicalSummarizer()

    return _summarizer


def generate_summary(
    request: OPDPrescriptionRequest,
) -> str:
    """LLM summary, validated; falls back to a template summary."""
    facts = build_brief_facts(request)
    fallback = facts.to_template_summary()

    if not ENABLE_QWEN_SUMMARIZER or facts.is_empty():
        return fallback

    try:
        candidate = get_summarizer().summarize(facts.to_prompt())
        problems = validate_brief_summary(facts, candidate)

        if not problems:
            logger.info("LLM summary accepted.")
            return candidate

        logger.warning("LLM summary rejected: %s", problems)

    except Exception as exc:
        logger.warning(
            "LLM generation failed (%s); using template summary.",
            type(exc).__name__,
        )

    return fallback


def build_sections(
    request: OPDPrescriptionRequest,
) -> ClinicalSections:
    """Build structured sections directly from the input request."""

    # Chief complaints and durations
    chief_complaints = []

    for complaint in request.chief_complaints or []:
        name = _name(complaint.name)
        duration = _text(complaint.duration)

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
            name = _name(item.name)
            if name and name not in diagnoses:
                diagnoses.append(name)

        for note in (
            request.diagnosis.note,
            request.diagnosis.remarks,
            request.diagnosis_note,
        ):
            value = _text(note)
            if value:
                diagnoses.append(value)

    # Investigations: listed investigations are not assumed results.
    investigations = []

    for item in request.investigations or []:
        name = _name(item.name)
        remarks = _text(item.remarks)

        if name:
            value = f"{name} — {remarks}" if remarks else name
            investigations.append(value)

    if request.investigation_note:
        note = _text(request.investigation_note)
        if note:
            investigations.append(note)

    # Medication details are mapped field by field from the input.
    medications = []

    for item in request.medications or []:
        name = _name(item.name)
        if not name:
            continue

        medications.append(
            MedicationSummary(
                name=name,
                dose=_text(item.dose),
                frequency=_text(item.frequency),
                duration=_text(item.duration_days),
                quantity=_text(item.quantity),
                instructions=_text(item.instructions),
            )
        )

    # Procedures
    procedures = [
        name
        for item in request.clinical_procedures or []
        if (name := _name(item.name))
    ]

    # Referrals
    referrals = []

    for item in request.referrals or []:
        details = [
            _name(item.department),
            _text(item.referral_type),
            _text(item.reason),
        ]
        details = [value for value in details if value]

        if details:
            referrals.append("; ".join(details))

    # Follow-up
    follow_up_items = []

    for item in request.follow_ups or []:
        note = _text(item.note)
        date = _text(item.date)

        if note:
            follow_up_items.append(note.rstrip("."))
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
            cleaned = _text(value)
            if cleaned:
                relevant_history.append(f"{label}: {cleaned}")

    for item in request.chronic_diseases or []:
        name = _name(item.name)
        if not name:
            continue

        details = [name]
        duration = _text(item.duration)
        remarks = _text(item.remarks)

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
            cleaned = _text(value)
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
            cleaned = _text(value)
            cleaned = _YES_NO.get(cleaned, cleaned)
            if cleaned:
                examination_findings.append(f"{label}: {cleaned}")

    # Allergies
    allergies = []

    for item in request.drug_allergies or []:
        details = [
            _text(item.sensitivity_type),
            _text(item.allergy_name),
            _text(item.site),
            _text(item.symptoms),
            _text(item.remarks),
            _text(item.duration),
        ]
        details = [value for value in details if value]

        if details:
            allergies.append("; ".join(details))

    other_allergies = _text(request.other_allergies)
    if other_allergies:
        allergies.append(other_allergies)

    # History of present illness and treatment advice
    hopi = _text(request.history_of_present_illness)
    treatment_advice = _text(request.treatment_advice)

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
