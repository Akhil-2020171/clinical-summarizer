import os

import requests

SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8081")
REQUEST_TIMEOUT = int(os.getenv("LLAMA_TIMEOUT", "120"))

SYSTEM = (
    "You write a 3-4 sentence outpatient visit summary for clinicians. "
    "Use ONLY the facts given. Copy complaint, diagnosis and test names exactly "
    "as written: never explain, translate, correct or add words in brackets. "
    "Procedures and referrals are separate from investigations. "
    "For a procedure write only 'Procedure: <name>' and never say it was "
    "performed, done, completed or planned. "
    "Never add symptoms, results, vitals, advice or numbers that are not listed. "
    "Investigations are ordered, not completed. Skip any item not listed. "
    "Plain text, no headings, no bullets."
)

EX1_IN = """Age/Sex: 40-year-old female
Complaints: cough for 5 days; fever for 3 days
Diagnosis: Acute bronchitis
Investigations ordered: Chest X-ray
Procedures: ECG
Referral: Cardiology
Medications: Azithromycin 500 mg; Paracetamol 650 mg
Drug allergy: Penicillin - rash
Follow-up: 20-10-2026, bring X-ray report"""

EX1_OUT = (
    "A 40-year-old female presented with cough for 5 days and fever for 3 days. "
    "Diagnosed with acute bronchitis; chest X-ray ordered. "
    "Procedure: ECG. Referred to cardiology. "
    "Prescribed azithromycin 500 mg and paracetamol 650 mg. "
    "Drug allergy: penicillin (rash). Follow-up on 20-10-2026 with the X-ray report."
)

EX2_IN = """Age/Sex: 62-year-old male
Complaints: knee pain
Diagnosis: Osteoarthritis
Medications: Diclofenac 50 mg"""

EX2_OUT = (
    "A 62-year-old male presented with knee pain. "
    "Diagnosed with osteoarthritis. Prescribed diclofenac 50 mg."
)


class ClinicalSummarizer:
    """Calls a running llama-server (OpenAI-compatible chat endpoint)."""

    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url.rstrip("/")

    def summarize(self, facts_text: str, max_tokens: int = 200) -> str:
        if not facts_text or not facts_text.strip():
            return ""

        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": EX1_IN},
            {"role": "assistant", "content": EX1_OUT},
            {"role": "user", "content": EX2_IN},
            {"role": "assistant", "content": EX2_OUT},
            {"role": "user", "content": facts_text},
        ]

        response = requests.post(
            f"{self.server_url}/v1/chat/completions",
            json={
                "messages": messages,
                "temperature": 0,
                "max_tokens": max_tokens,
                "repeat_penalty": 1.1,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        text = response.json()["choices"][0]["message"]["content"].strip()
        if not text:
            raise RuntimeError("The summarizer returned an empty response.")
        return text
