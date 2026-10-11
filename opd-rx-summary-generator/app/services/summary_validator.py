import re

from app.services.brief_facts import BriefFacts


def _n(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _np(text: str) -> str:
    """Like _n, but punctuation counts as a space: 'chest pain (under evaluation)'
    matches 'Chest pain under evaluation', while an inserted word ('malt (malaria)
    fever') still does not match 'Malt fever'."""
    return re.sub(r"[^0-9a-z]+", " ", text.casefold()).strip()


# A leading "?" on a diagnosis means "suspected". The summary must keep that doubt.
_HEDGES = ("?", "suspect", "possible", "probable", "likely", "query", "rule out", "r/o")

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
        r"\b(performed|completed|conducted|underwent|undergone|done)\b",
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
        uncertain = name.lstrip().startswith("?")
        core = _np(name.lstrip(" ?"))
        if f" {core} " not in f" {_np(summary)} ":
            reasons.append(f"Missing diagnosis: {name}")
        elif uncertain and not any(h in s for h in _HEDGES):
            reasons.append(f"Suspected diagnosis stated as certain: {name}")

    # Complaints: loose check on the first word stem ("Vomit pH" ~ "vomiting").
    for complaint in facts.complaints:
        first_word = _n(complaint.split(" for ")[0]).split()[0]
        if first_word[:5] not in s:
            reasons.append(f"Missing complaint: {complaint}")

    # Durations: each must appear, and must not slide onto a neighbouring complaint
    # ("fever, headache for 1 day" when only the headache had a duration).
    with_duration, without_duration = [], []
    for complaint in facts.complaints:
        if " for " in complaint:
            cname, cdur = complaint.split(" for ", 1)
            with_duration.append((_n(cname), _n(cdur)))
        else:
            without_duration.append(_n(complaint))

    for cname, cdur in with_duration:
        if cdur not in s:
            reasons.append(f"Missing duration: {cname} for {cdur}")
        for other in without_duration:
            glued = (
                re.escape(other)
                + r"\s*(?:,|;|and|&)?\s*(?:and\s+)?"
                + re.escape(f"{cname} for {cdur}")
            )
            if re.search(glued, s):
                reasons.append(
                    f"Duration may belong to the wrong complaint: {other} / {cname}"
                )

    # Medications: the drug's first word must appear.
    for med in facts.medications:
        if _n(med).split()[0] not in s:
            reasons.append(f"Missing medication: {med}")

    # Abbreviations from the source (TDS, OD, CBC...) must not be glued to other
    # text, e.g. "TDSprescribed".
    for token in set(re.findall(r"\b[A-Z]{2,}\b", facts.to_prompt())):
        if token in summary and not re.search(
            rf"(?<![A-Za-z]){token}(?![A-Za-z])", summary
        ):
            reasons.append(f"Malformed text around '{token}'")

    # Every number in the summary must exist in the source facts.
    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", source))
    for number in set(re.findall(r"\d+(?:\.\d+)?", s)):
        if number not in source_numbers:
            reasons.append(f"Number not in source: {number}")

    for pattern, label in _BANNED_CLAIMS:
        if re.search(pattern, s) and not re.search(pattern, source):
            reasons.append(f"Unsupported claim: {label}")

    # "planned"/"scheduled"/"pending" is fine for a follow-up, but not for a procedure.
    status = r"\b(planned|scheduled|pending)\b"
    procedure_names = [_n(p) for p in facts.procedures]
    if procedure_names and not re.search(status, source):
        for sentence in re.split(r"(?<=[.!?])\s+", s):
            if re.search(status, sentence) and any(p in sentence for p in procedure_names):
                reasons.append("Unsupported status (planned/scheduled) for a procedure")
                break

    return reasons
