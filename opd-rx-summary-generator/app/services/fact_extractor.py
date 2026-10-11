from typing import Any

from app.schemas.request import OPDPrescriptionRequest


def _clean(value: Any) -> str | None:
    """Return a clean string, preserving meaningful zero values."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Common placeholders that do not represent clinical facts.
    if text.lower() in {"null", "none", "n/a", "na"}:
        return None

    return text


def _add(lines: list[str], label: str, value: Any) -> None:
    """Append a labelled fact only when it contains a value."""
    cleaned = _clean(value)
    if cleaned:
        lines.append(f"{label}: {cleaned}")


def extract_clinical_facts(
    request: OPDPrescriptionRequest,
) -> str:
    """Build a deterministic, source-grounded representation of an OPD visit."""
    lines: list[str] = []

    # Patient and visit details
    patient_parts = []

    age = _clean(request.patient_age)
    gender = _clean(request.patient_gender)

    if age:
        patient_parts.append(f"Age: {age}")
    if gender:
        patient_parts.append(f"Gender: {gender}")

    if patient_parts:
        lines.extend(patient_parts)

    _add(lines, "Visit date", request.current_visit_date)

    # Chief complaints and durations
    complaints = request.chief_complaints or []
    for complaint in complaints:
        name = _clean(complaint.name)
        duration = _clean(complaint.duration)

        if name and duration:
            lines.append(f"Chief complaint: {name}; duration: {duration}")
        elif name:
            lines.append(f"Chief complaint: {name}")
        elif duration:
            lines.append(f"Complaint duration recorded: {duration}")

    _add(
        lines,
        "History of present illness",
        request.history_of_present_illness,
    )

    # Diagnoses
    diagnosis = request.diagnosis
    if diagnosis:
        for item in diagnosis.items or []:
            name = _clean(item.name)
            diagnosis_type = _clean(item.diagnosis_type)

            if name and diagnosis_type:
                lines.append(
                    f"Recorded diagnosis: {name} "
                    f"(type: {diagnosis_type})"
                )
            elif name:
                lines.append(f"Recorded diagnosis: {name}")

        _add(lines, "Diagnosis note", diagnosis.note)
        _add(lines, "Diagnosis remarks", diagnosis.remarks)

    _add(lines, "Additional diagnosis note", request.diagnosis_note)

    # Investigations: presence in the prescription does not prove completion.
    for investigation in request.investigations or []:
        name = _clean(investigation.name)
        remarks = _clean(investigation.remarks)

        if name and remarks:
            lines.append(
                f"Investigation listed: {name}; remarks: {remarks}"
            )
        elif name:
            lines.append(f"Investigation listed: {name}")

    _add(
        lines,
        "Investigation note",
        request.investigation_note,
    )

    # Medications: preserve every supplied prescribing detail.
    for medication in request.medications or []:
        name = _clean(medication.name)
        if not name:
            continue

        lines.append(f"Medication: {name}")

        _add(lines, "  Dose", medication.dose)
        _add(lines, "  Frequency", medication.frequency)
        _add(lines, "  Duration", medication.duration_days)
        _add(lines, "  Quantity", medication.quantity)
        _add(lines, "  Instructions", medication.instructions)
        _add(lines, "  Additional medication text", medication.additional_text)

    # Follow-up: include only recorded details.
    for follow_up in request.follow_ups or []:
        _add(lines, "Follow-up note", follow_up.note)
        _add(lines, "Follow-up date", follow_up.date)

    # Procedures and referrals
    for procedure in request.clinical_procedures or []:
        _add(lines, "Clinical procedure recorded", procedure.name)

    for referral in request.referrals or []:
        parts = [
            _clean(referral.department),
            _clean(referral.referral_type),
            _clean(referral.reason),
        ]
        parts = [part for part in parts if part]

        if parts:
            lines.append("Referral recorded: " + "; ".join(parts))

    # Relevant medical history
    history = request.patient_history
    if history:
        _add(lines, "Past history", history.past_history)
        _add(lines, "Personal history", history.personal_history)
        _add(lines, "Family history", history.family_history)
        _add(lines, "Treatment history", history.treatment_history)
        _add(lines, "Surgical history", history.surgical_history)

    for disease in request.chronic_diseases or []:
        name = _clean(disease.name)
        if not name:
            continue

        details = [name]
        duration = _clean(disease.duration)
        remarks = _clean(disease.remarks)

        if duration:
            details.append(f"duration: {duration}")
        if remarks:
            details.append(f"remarks: {remarks}")

        lines.append("Recorded chronic disease: " + "; ".join(details))

    # Examination findings: only explicitly supplied values are included.
    examination = request.systematic_examination
    if examination:
        _add(lines, "Cardiovascular examination", examination.cardiovascular)
        _add(lines, "Respiratory examination", examination.respiratory)
        _add(lines, "CNS examination", examination.central_nervous_system)
        _add(lines, "Abdominal examination", examination.abdomen)
        _add(lines, "Other examination", examination.other_examination)
        _add(lines, "Musculoskeletal examination", examination.musculoskeletal)
        _add(lines, "Local examination", examination.local_examination)

    signs = request.clinical_signs
    if signs:
        _add(lines, "Pallor", signs.pallor)
        _add(lines, "Icterus", signs.icterus)
        _add(lines, "Cyanosis", signs.cyanosis)
        _add(lines, "Clubbing", signs.clubbing)
        _add(lines, "Lymphadenopathy", signs.lymphadenopathy)
        _add(lines, "Edema", signs.edema)

    # Allergies
    for allergy in request.drug_allergies or []:
        parts = [
            _clean(allergy.sensitivity_type),
            _clean(allergy.allergy_name),
            _clean(allergy.site),
            _clean(allergy.symptoms),
            _clean(allergy.remarks),
            _clean(allergy.duration),
        ]
        parts = [part for part in parts if part]

        if parts:
            lines.append("Recorded drug allergy: " + "; ".join(parts))

    _add(lines, "Other allergies", request.other_allergies)

    # Advice and vitals
    _add(lines, "Treatment advice", request.treatment_advice)
    _add(lines, "Vitals as recorded", request.vitals)

    return "\n".join(lines)
