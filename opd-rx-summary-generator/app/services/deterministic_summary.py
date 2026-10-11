from app.schemas.request import OPDPrescriptionRequest
from app.services.fact_extractor import _clean


def build_deterministic_summary(
    request: OPDPrescriptionRequest,
) -> str:
    """Build a source-grounded OPD summary without generative AI."""

    paragraphs: list[str] = []
    
    # Patient context
    age = _clean(request.patient_age)
    gender = _clean(request.patient_gender)

    if age and gender:
        paragraphs.append(
            f"A {age}-old {gender.lower()} patient was documented."
            if age.isdigit()
            else f"Patient details recorded: age {age}; gender {gender}."
        )
    elif age:
        paragraphs.append(f"Patient age recorded: {age}.")
    elif gender:
        paragraphs.append(f"Patient gender recorded: {gender}.")


    # Presenting complaints, preserving their recorded durations
    complaints = []

    for complaint in request.chief_complaints or []:
        name = _clean(complaint.name)
        duration = _clean(complaint.duration)

        if not name:
            continue

        if duration:
            complaints.append(f"{name} for {duration}")
        else:
            complaints.append(name)

    if complaints:
        paragraphs.append(
            "The patient presented with "
            + ", ".join(complaints)
            + "."
        )

    # History of present illness
    hopi = _clean(request.history_of_present_illness)
    if hopi:
        paragraphs.append(f"History of present illness: {hopi}")

    # Recorded diagnoses
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
            cleaned = _clean(note)
            if cleaned:
                diagnoses.append(cleaned)

    if diagnoses:
        paragraphs.append(
            "Recorded diagnosis: " + "; ".join(diagnoses) + "."
        )

    # Investigations: do not imply completion or results
    investigations = []

    for investigation in request.investigations or []:
        name = _clean(investigation.name)
        if name and name not in investigations:
            investigations.append(name)

    if investigations:
        paragraphs.append(
            "Investigations listed: "
            + ", ".join(investigations)
            + "."
        )

    if request.investigation_note:
        note = _clean(request.investigation_note)
        if note:
            paragraphs.append(f"Investigation note: {note}")

    # Medications: keep all prescribing details together
    medication_sentences = []

    for medication in request.medications or []:
        name = _clean(medication.name)
        if not name:
            continue

        details = []

        for label, value in (
            ("dose", medication.dose),
            ("frequency", medication.frequency),
            ("duration", medication.duration_days),
            ("quantity", medication.quantity),
            ("instructions", medication.instructions),
            ("additional details", medication.additional_text),
        ):
            cleaned = _clean(value)
            if cleaned:
                details.append(f"{label}: {cleaned}")

        if details:
            medication_sentences.append(
                f"{name} ({'; '.join(details)})"
            )
        else:
            medication_sentences.append(name)

    if medication_sentences:
        paragraphs.append(
            "Medications recorded: "
            + ". ".join(medication_sentences)
            + "."
        )

    # Follow-up: only report actual supplied details
    follow_up_details = []

    for follow_up in request.follow_ups or []:
        note = _clean(follow_up.note)
        date = _clean(follow_up.date)

        if note:
            follow_up_details.append(note)
        if date:
            follow_up_details.append(f"date: {date}")

    if follow_up_details:
        paragraphs.append(
            "Follow-up recorded: "
            + "; ".join(follow_up_details)
            + "."
        )

    # Procedures and referrals
    procedures = [
        name
        for procedure in request.clinical_procedures or []
        if (name := _clean(procedure.name))
    ]

    if procedures:
        paragraphs.append(
            "Clinical procedures recorded: "
            + ", ".join(procedures)
            + "."
        )

    for referral in request.referrals or []:
        details = [
            _clean(referral.department),
            _clean(referral.referral_type),
            _clean(referral.reason),
        ]
        details = [value for value in details if value]

        if details:
            paragraphs.append(
                "Referral recorded: " + "; ".join(details) + "."
            )

    # Relevant history
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
                paragraphs.append(f"{label}: {cleaned}")

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

        paragraphs.append(
            "Chronic disease recorded: " + "; ".join(details) + "."
        )

    # Examination: report only supplied values
    examination = request.systematic_examination

    if examination:
        for label, value in (
            ("Cardiovascular examination", examination.cardiovascular),
            ("Respiratory examination", examination.respiratory),
            ("CNS examination", examination.central_nervous_system),
            ("Abdominal examination", examination.abdomen),
            ("Other examination", examination.other_examination),
            ("Musculoskeletal examination", examination.musculoskeletal),
            ("Local examination", examination.local_examination),
        ):
            cleaned = _clean(value)
            if cleaned:
                paragraphs.append(f"{label}: {cleaned}")

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
                paragraphs.append(f"{label}: {cleaned}")

    # Allergies
    for allergy in request.drug_allergies or []:
        details = [
            _clean(allergy.sensitivity_type),
            _clean(allergy.allergy_name),
            _clean(allergy.site),
            _clean(allergy.symptoms),
            _clean(allergy.remarks),
            _clean(allergy.duration),
        ]
        details = [value for value in details if value]

        if details:
            paragraphs.append(
                "Drug allergy recorded: " + "; ".join(details) + "."
            )

    other_allergies = _clean(request.other_allergies)
    if other_allergies:
        paragraphs.append(f"Other allergies recorded: {other_allergies}.")

    # Vitals and treatment advice
    vitals = _clean(request.vitals)
    if vitals:
        paragraphs.append(f"Vitals as recorded: {vitals}")

    advice = _clean(request.treatment_advice)
    if advice:
        paragraphs.append(f"Treatment advice recorded: {advice}")

    return "\n\n".join(paragraphs)
