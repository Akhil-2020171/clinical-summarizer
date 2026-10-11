import re
from dataclasses import dataclass, field

from app.schemas.request import OPDPrescriptionRequest
from app.services.fact_extractor import _clean

_GENDER = {"m": "male", "male": "male", "f": "female", "female": "female"}


def _age(raw) -> str | None:
    """'26 Yr' -> '26-year-old', '4 Months' -> '4-month-old'."""
    text = _clean(raw)
    match = re.match(r"\s*(\d+)\s*([a-z]*)", text or "", re.I)
    if not match:
        return None
    unit = match.group(2).lower()
    if unit.startswith("m"):
        word = "month"
    elif unit.startswith("d"):
        word = "day"
    elif unit.startswith("w"):
        word = "week"
    else:
        word = "year"
    return f"{match.group(1)}-{word}-old"


def _tidy(raw) -> str | None:
    """Remove stray brackets such as 'Chest(X )' and extra whitespace."""
    text = _clean(raw)
    if not text:
        return None
    text = re.sub(r"\(\s*[A-Za-z]?\s*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ;,")
    return text or None


def _drug(raw) -> str | None:
    """'PARACETAMOL TAB 125MG [ 733 ] ' -> 'Paracetamol tab 125 mg'."""
    text = _clean(raw)
    if not text:
        return None
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(
        r"(\d)\s*(mg|mcg|g|ml|iu)\b",
        lambda m: f"{m.group(1)} {m.group(2).lower()}",
        text,
        flags=re.I,
    )
    text = re.sub(r"\s+", " ", text).strip(" ;,")
    return text.lower().capitalize() if text else None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


@dataclass
class BriefFacts:
    age_sex: str | None = None
    complaints: list[str] = field(default_factory=list)
    diagnoses: list[str] = field(default_factory=list)
    investigations: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    referrals: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    follow_up: str | None = None

    def is_empty(self) -> bool:
        return not (self.complaints or self.diagnoses or self.medications)

    def to_prompt(self) -> str:
        rows = [
            ("Age/Sex", self.age_sex),
            ("Complaints", "; ".join(self.complaints)),
            ("Diagnosis", "; ".join(self.diagnoses)),
            ("Investigations ordered", "; ".join(self.investigations)),
            ("Procedures", "; ".join(self.procedures)),
            ("Referral", "; ".join(self.referrals)),
            ("Medications", "; ".join(self.medications)),
            ("Drug allergy", "; ".join(self.allergies)),
            ("Follow-up", self.follow_up),
        ]
        return "\n".join(f"{key}: {value}" for key, value in rows if value)

    def to_template_summary(self) -> str:
        """Deterministic 3-4 sentence summary used when the LLM fails."""
        sentences: list[str] = []
        who = f"A {self.age_sex}" if self.age_sex else "The patient"

        if self.complaints:
            sentences.append(
                f"{who} presented with {', '.join(self.complaints)}."
            )
        elif self.age_sex:
            sentences.append(f"{who} patient was seen.")

        middle = []
        if self.diagnoses:
            middle.append(f"Diagnosis: {', '.join(self.diagnoses)}.")
        if self.investigations:
            middle.append(
                f"Investigations ordered: {', '.join(self.investigations)}."
            )
        if self.procedures:
            middle.append(f"Procedures: {', '.join(self.procedures)}.")
        if self.referrals:
            middle.append(f"Referral: {', '.join(self.referrals)}.")
        if middle:
            sentences.append(" ".join(middle))

        if self.medications:
            sentences.append(f"Prescribed: {', '.join(self.medications)}.")

        tail = []
        if self.allergies:
            tail.append(f"Drug allergy: {', '.join(self.allergies)}.")
        if self.follow_up:
            tail.append(f"Follow-up: {self.follow_up}.")
        if tail:
            sentences.append(" ".join(tail))

        return " ".join(sentences)


def build_brief_facts(request: OPDPrescriptionRequest) -> BriefFacts:
    facts = BriefFacts()

    age = _age(request.patient_age)
    sex = _GENDER.get((_clean(request.patient_gender) or "").lower())
    facts.age_sex = " ".join(part for part in (age, sex) if part) or None

    for complaint in request.chief_complaints or []:
        name = _tidy(complaint.name)
        duration = _clean(complaint.duration)
        if name:
            facts.complaints.append(
                f"{name} for {duration}" if duration else name
            )

    if request.diagnosis:
        facts.diagnoses = [
            name
            for item in request.diagnosis.items or []
            if (name := _tidy(item.name))
        ]

    facts.investigations = [
        name
        for item in request.investigations or []
        if (name := _tidy(item.name))
    ]
    facts.procedures = [
        name
        for item in request.clinical_procedures or []
        if (name := _tidy(item.name))
    ]
    facts.referrals = [
        name
        for item in request.referrals or []
        if (name := _tidy(item.department))
    ]

    for medication in request.medications or []:
        name = _drug(medication.name)
        if not name:
            continue
        parts = [name]
        dose = _clean(medication.dose)
        frequency = _clean(medication.frequency)
        days = _clean(medication.duration_days)
        if dose:
            parts.append(dose)
        if frequency:
            parts.append(frequency)
        if days:
            parts.append(f"for {days} days" if days.isdigit() else days)
        facts.medications.append(" ".join(parts))

    for allergy in request.drug_allergies or []:
        parts = [
            part.strip(" ;")
            for part in (_clean(allergy.allergy_name), _clean(allergy.symptoms))
            if part
        ]
        if parts:
            facts.allergies.append(" - ".join(parts))

    for follow_up in request.follow_ups or []:
        date = _clean(follow_up.date)
        note = _clean(follow_up.note)
        if date or note:
            joined = ", ".join(part for part in (date, note) if part)
            facts.follow_up = joined.rstrip(" .;")
            break

    for attr in (
        "complaints",
        "diagnoses",
        "investigations",
        "procedures",
        "referrals",
        "medications",
        "allergies",
    ):
        setattr(facts, attr, _dedupe(getattr(facts, attr)))

    return facts
