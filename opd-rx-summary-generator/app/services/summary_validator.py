
import re
from dataclasses import dataclass

from app.schemas.request import OPDPrescriptionRequest
from app.services.fact_extractor import _clean


@dataclass
class ValidationResult:
    valid: bool
    reasons: list[str]


def _normalise(text: str) -> str:
    """Normalise whitespace and case for phrase comparison."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def _contains_phrase(text: str, phrase: str) -> bool:
    """Check whether a source phrase occurs in the summary."""
    return _normalise(phrase) in _normalise(text)


def validate_summary(
    request: OPDPrescriptionRequest,
    candidate_summary: str,
) -> ValidationResult:
    """
    Conservative first-pass validation of model-generated text.

    This checks selected required facts and obvious unsupported claims.
    It does not prove that the summary is clinically correct.
    """
    reasons: list[str] = []

    if not candidate_summary or not candidate_summary.strip():
        return ValidationResult(
            valid=False,
            reasons=["The generated summary is empty."],
        )

    summary = candidate_summary.strip()

    # Required complaint names and recorded durations.
    for complaint in request.chief_complaints or []:
        name = _clean(complaint.name)
        duration = _clean(complaint.duration)

        if name and not _contains_phrase(summary, name):
            reasons.append(
                f"Missing recorded chief complaint: {name}"
            )


        if duration and name:
            # Require the duration to be associated with its complaint.
            expected_phrase = f"{name} for {duration}"

            if not _contains_phrase(summary, expected_phrase):
                reasons.append(
                    f"Missing or incorrectly associated duration "
                    f"for complaint: {name} ({duration})"
                )


    # Recorded diagnoses must not disappear from the summary.
    if request.diagnosis:
        for diagnosis in request.diagnosis.items or []:
            name = _clean(diagnosis.name)

            if name and not _contains_phrase(summary, name):
                reasons.append(
                    f"Missing recorded diagnosis: {name}"
                )

    # Preserve investigation names without assuming results.
    for investigation in request.investigations or []:
        name = _clean(investigation.name)

        if name and not _contains_phrase(summary, name):
            reasons.append(
                f"Missing listed investigation: {name}"
            )

    # Preserve all supplied medication details.
    for medication in request.medications or []:
        name = _clean(medication.name)

        if not name:
            continue

        if not _contains_phrase(summary, name):
            reasons.append(f"Missing medication: {name}")
            continue

        for label, raw_value in (
            ("dose", medication.dose),
            ("frequency", medication.frequency),
            ("duration", medication.duration_days),
            ("quantity", medication.quantity),
            ("instructions", medication.instructions),
        ):
            value = _clean(raw_value)

            if value and not _contains_phrase(summary, value):
                reasons.append(
                    f"Missing medication {label} for {name}: {value}"
                )

    # Detect common claims that require explicit source evidence.
    source_facts = _normalise(
        __import__(
            "app.services.fact_extractor",
            fromlist=["extract_clinical_facts"],
        ).extract_clinical_facts(request)
    )

    unsupported_claim_patterns = {
        "hospital admission": (
            r"\b(admitted|hospitali[sz]ed|hospital admission)\b"
        ),
        "treatment response": (
            r"\b(improved|responded well|recovered|resolved)\b"
        ),
    }

    for claim, pattern in unsupported_claim_patterns.items():
        if re.search(pattern, summary, flags=re.IGNORECASE):
            if not re.search(
                pattern, source_facts, flags=re.IGNORECASE
            ):
                reasons.append(
                    f"Possible unsupported claim: {claim}"
                )

    # If investigations are listed but no results are supplied,
    # reject common invented-result language.
    has_investigations = bool(request.investigations)
    has_explicit_result_text = bool(_clean(request.investigation_note))

    result_patterns = (
        r"\b(results?\s+(showed|revealed|indicated))\b",
        r"\b(test(?:ing)?\s+(confirmed|demonstrated))\b",
        r"\b(wbc|white blood cell count|platelet count)\s*(?:was|were|of|:)?\s*\d",
    )

    if has_investigations and not has_explicit_result_text:
        for pattern in result_patterns:
            if re.search(pattern, summary, flags=re.IGNORECASE):
                reasons.append(
                    "Possible investigation result without "
                    "documented result data."
                )
                break

    return ValidationResult(
        valid=not reasons,
        reasons=reasons,
    )
