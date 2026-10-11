import re

from app.services.brief_facts import BriefFacts


def _n(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


_BANNED_CLAIMS = [
    (r"\b(admitted|hospitali[sz]ed)\b", "hospital admission"),
    (r"\b(improved|responded|recovered|resolved)\b", "treatment response"),
    (
        r"\b(results?\s+(showed|revealed|indicated)|"
        r"test\w*\s+(confirmed|demonstrated))\b",
        "invented investigation result",
    ),
    (r"\bno known (drug )?allerg", "invented 'no known allergy'"),
    (
        r"\b(performed|completed|conducted|underwent|undergone|planned|"
        r"scheduled|done)\b",
        "invented procedure/test status",
    ),
]


def validate_brief_summary(facts: BriefFacts, summary: str) -> list[str]:
    """Return a list of problems; an empty list means the summary passed."""
    if not summary or not summary.strip():
        return ["Empty summary."]

    reasons: list[str] = []
    s = _n(summary)
    source = _n(facts.to_prompt())

    if len(re.findall(r"[.!?](?:\s|$)", summary)) > 7 or len(summary) > 900:
        reasons.append("Summary too long.")

    # Diagnoses must be copied exactly (catches invented glosses).
    for name in facts.diagnoses:
        if _n(name) not in s:
            reasons.append(f"Missing diagnosis: {name}")

    # Complaints: loose check on the first word stem ("Vomit pH" ~ "vomiting").
    for complaint in facts.complaints:
        first_word = _n(complaint.split(" for ")[0]).split()[0]
        if first_word[:5] not in s:
            reasons.append(f"Missing complaint: {complaint}")

    # Medications: the drug's first word must appear.
    for med in facts.medications:
        if _n(med).split()[0] not in s:
            reasons.append(f"Missing medication: {med}")

    # Every number in the summary must exist in the source facts.
    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", source))
    for number in set(re.findall(r"\d+(?:\.\d+)?", s)):
        if number not in source_numbers:
            reasons.append(f"Number not in source: {number}")

    for pattern, label in _BANNED_CLAIMS:
        if re.search(pattern, s) and not re.search(pattern, source):
            reasons.append(f"Unsupported claim: {label}")

    return reasons
