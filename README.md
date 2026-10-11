# OPD Prescription Summary Generator

Turns an outpatient (OPD) prescription JSON into a short, source-grounded clinical
summary of 3-4 sentences, plus a structured, cleaned-up breakdown of every section.

Everything runs locally: a small LLM (Qwen2.5-3B-Instruct via llama.cpp) writes the
summary, a validator checks it against the source data, and a deterministic template
takes over whenever the model's output can't be trusted. No patient data leaves the
machine.

> **Not a medical device.** Summaries are an aid for reading a prescription, not a
> clinical record. A clinician must review them before anyone relies on them. See
> [Limitations](#limitations).

---

## How it works

```
 OPD JSON ──► build_brief_facts() ──► LLM (llama.cpp) ──► validate_brief_summary()
                 │  clean names,           │                     │
                 │  map age/sex,           │                     ├─ passes ──► LLM summary
                 │  drop noisy fields      │                     │
                 │                         │                     └─ fails / LLM down / timeout
                 └─────────────────────────┴──────────────────────────► template summary
                                                                          (always correct,
                                                                           no AI involved)
 OPD JSON ──► build_sections() ──────────────────────────────────────► cleaned sections
```

1. **Clean the input** (`brief_facts.py`). Drug codes like `[ 733 ]`, stray brackets like
   `Chest(X )`, `26 Yr`, and `M` become `Paracetamol tab 125 mg`, `Plain X RAY Chest`,
   `26-year-old` and `male`. Only high-value facts reach the model: age/sex, complaints,
   diagnoses, investigations, procedures, referrals, medications, drug allergies and
   follow-up. Vitals, free-text examination notes and the 0/1 sign flags are **not**
   sent to the model, because they are the main source of invented content.
2. **Generate** (`summarizer.py`). The facts are sent to a local `llama-server` with a
   strict system prompt and two worked examples, at temperature 0.
3. **Validate** (`summary_validator.py`). The summary is rejected if it:
   - drops or alters a diagnosis name (must be copied exactly),
   - drops a complaint or a medication,
   - contains a number that is not in the source,
   - claims admission, recovery, investigation results, "no known allergy", or says a
     test or procedure was performed/completed/planned when the source doesn't,
   - is too long.
4. **Fall back** (`BriefFacts.to_template_summary`). If validation fails, the model is
   unreachable, or it times out, a deterministic template summary is returned instead.
   The API always returns a summary.
5. **Sections** (`build_sections` in `main.py`). A structured breakdown built directly
   from the input, with codes and stray characters removed and the 0/1 clinical signs
   shown as `Yes`/`No`.

---

## Project layout

```
clinical-summariser/                 <- run everything from here
├── docker-compose.yml               llama.cpp server + API
├── Makefile                         shortcuts for every command below
├── README.md
├── models/                          GGUF model files (created by `make setup`)
├── samples/
│   ├── sample.json                  clean example (LLM summary expected)
│   └── sample_fallback.json         diagnosis the model alters (template expected)
└── opd-rx-summary-generator/        the API
    ├── Dockerfile
    ├── .dockerignore
    ├── requirements.txt
    └── app/
        ├── main.py                  FastAPI app, generate_summary(), build_sections()
        ├── schemas/
        │   ├── request.py           input model (OPDPrescriptionRequest)
        │   └── response.py          output models
        └── services/
            ├── brief_facts.py       cleaning + prompt facts + template summary
            ├── summarizer.py        client for the llama.cpp server
            ├── summary_validator.py checks the model's summary
            ├── fact_extractor.py    `_clean()` helper (shared)
            └── deterministic_summary.py   older long-form summary (no longer used by main.py)
```

---

## Requirements

- Docker with the Compose plugin (`docker compose version`)
- `make` and `curl` on the host
- About 4 GB of free RAM and 3 GB of disk for the default model
- Tested target: Raspberry Pi 5 (arm64, 8 GB). Any 64-bit Linux, macOS or Windows
  (WSL) machine with Docker also works; the llama.cpp server image is published for
  amd64 and arm64.

---

## Quick start

```bash
cd ~/Public/clinical-summariser

# If you were running things by hand, stop them first (ports 8000 and 8081):
#   Ctrl+C the native llama-server and uvicorn terminals.

make setup model start     # create models/, download the model, build and start
make health                # API: {"status":"ok"}   Model: {"status":"ok"}
make summary               # print the summary for samples/sample.json
```

The first `make start` pulls the llama.cpp image and builds the API image, so it takes a
few minutes. The first request after a start is the slowest, because the model has to
process the prompt's example text. The server caches that fixed prefix, so later
requests are faster. Expect roughly 15-30 seconds for the first call on a Pi 5.

Interactive API docs are at <http://localhost:8000/docs>.

---

## Using the API

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### `POST /summarize`

Send an OPD prescription JSON (field names such as `CC`, `DIAG`, `INV`, `DRUG`, `FUP`,
`patAge`, `patGender` are defined in `app/schemas/request.py`; unknown fields are
ignored).

```bash
curl -s -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d @samples/sample.json | python3 -m json.tool
```

Response shape:

```json
{
  "patient_name": "Kanhai",
  "summary": "A 26-year-old male presented with fever, headache, and vomiting. Diagnosed with malaria and typhoid fever; ...",
  "sections": {
    "chief_complaints": ["Fever", "Headache", "Vomit pH"],
    "diagnoses": ["Malaria", "Typhoid fever"],
    "investigations": ["Complete Blood Count", "..."],
    "medications": [{"name": "PARACETAMOL TAB 125MG", "dose": null, "...": null}],
    "procedures": ["Hydrogen Breath Test"],
    "referrals": ["Cardiology"],
    "follow_up": "...; Date: 12-10-2026",
    "relevant_history": ["..."],
    "examination_findings": ["Pallor: Yes", "Icterus: No", "..."],
    "allergies": ["..."],
    "treatment_advice": "..."
  }
}
```

The response does not say whether `summary` came from the model or the template. Check
the API log (`make logs-api`) for one of:

| Log line | Meaning |
|---|---|
| `LLM summary accepted.` | Model output passed validation and was returned |
| `LLM summary rejected: [...]` | Validation failed; the template summary was returned. The list says why |
| `LLM generation failed (...)` | Model server unreachable, timed out or errored; template returned |

A summary written like "Diagnosis: X. Investigations ordered: ..." (capitalised lists)
is the template; flowing prose is the model.

---

## Make targets

Run `make` or `make help` for the live list.

| Command | What it does |
|---|---|
| `make setup` | Create the `models/` folder |
| `make model` | Download the GGUF model into `models/` (resumable) |
| `make build` | Build the API image |
| `make up` | Start both containers (checks the model file exists) |
| `make start` | `build` then `up` |
| `make down` | Stop and remove the containers |
| `make restart` | Restart both containers |
| `make ps` | Container status |
| `make logs` / `logs-api` / `logs-llama` | Follow logs |
| `make health` | Check the API and the model server |
| `make test` | POST `samples/sample.json`, print the full response |
| `make summary` | Same, print only the summary and the request time |
| `make test-fallback` | POST a diagnosis the model will alter; expect the template |
| `make shell` | Shell inside the API container |
| `make clean` | Remove containers and the built API image (keeps `models/`) |

---

## Configuration

| Variable | Default | Used by | Purpose |
|---|---|---|---|
| `MODEL_FILE` | `qwen2.5-3b-instruct-q4_k_m.gguf` | Makefile, compose | GGUF file inside `models/` |
| `MODEL_REPO` | `Qwen/Qwen2.5-3B-Instruct-GGUF` | Makefile | Hugging Face repo for `make model` |
| `API_PORT` | `8000` | Makefile, compose | Host port for the API |
| `LLAMA_HOST_PORT` | `8081` | Makefile, compose | Host port (localhost only) for the model server |
| `LLAMA_THREADS` | `4` | compose | CPU threads for llama.cpp |
| `LLAMA_CTX` | `4096` | compose | Context size |
| `LLAMA_TIMEOUT` | `120` | API | Seconds to wait for the model before falling back |
| `ENABLE_QWEN_SUMMARIZER` | `true` | API | `false` = always return the template summary |
| `LLAMA_SERVER_URL` | `http://llama:8080` | API | Set by compose; change only when running outside Docker |

How to set them:

- `MODEL_FILE`, `MODEL_REPO`, `API_PORT`, `LLAMA_HOST_PORT`: pass them to make, e.g.
  `make up MODEL_FILE=qwen2.5-1.5b-instruct-q4_k_m.gguf`, or edit the defaults at the top
  of the `Makefile`. (The Makefile always exports them, so a value in `.env` for these
  four would be overridden.)
- `LLAMA_THREADS`, `LLAMA_CTX`, `LLAMA_TIMEOUT`, `ENABLE_QWEN_SUMMARIZER`: put them in a
  `.env` file next to `docker-compose.yml`, or export them in your shell, then
  `make down up`.

**Kill switch:** `ENABLE_QWEN_SUMMARIZER=false` in `.env`, then `make down up`. The API
keeps working and returns the template summary with no model involved.

---

## Choosing a model

| Model | Size | Notes |
|---|---|---|
| Qwen2.5-1.5B-Instruct (Q4_K_M) | ~1 GB | Fastest; needs the validator and fallback most |
| **Qwen2.5-3B-Instruct (Q4_K_M)** | ~2 GB | **Default.** Good balance on a Raspberry Pi 5 |
| Qwen2.5-7B-Instruct (Q4_K_M) | ~4.7 GB | Best quality, but only 1-2 tokens/s on a Pi 5, which is too slow |

To switch:

```bash
make model MODEL_FILE=qwen2.5-1.5b-instruct-q4_k_m.gguf MODEL_REPO=Qwen/Qwen2.5-1.5B-Instruct-GGUF
make down up MODEL_FILE=qwen2.5-1.5b-instruct-q4_k_m.gguf
```

The model must be an **instruct/chat** model; the server applies the model's own chat
template. Do not use the old 0.5B "multiclinsum-distil" model: it invents content.

---

## Running without Docker

```bash
cd opd-rx-summary-generator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# terminal 1: model server (llama.cpp built from source)
llama-server -m ../models/qwen2.5-3b-instruct-q4_k_m.gguf -c 4096 -t 4 --port 8081

# terminal 2: API
export LLAMA_SERVER_URL=http://127.0.0.1:8081
uvicorn app.main:app --reload
```

---

## Troubleshooting

**`make up` says the model is not found.** Run `make model`. If the download fails,
check the connection and re-run; it resumes. The file must end up at
`models/qwen2.5-3b-instruct-q4_k_m.gguf` (or whatever `MODEL_FILE` says).

**`port is already allocated` / address in use.** A native `llama-server` (8081) or
`uvicorn` (8000) is still running. Stop it, or change `API_PORT` / `LLAMA_HOST_PORT`.

**`permission denied` talking to Docker.** Add yourself to the docker group
(`sudo usermod -aG docker $USER`), then log out and back in.

**`opd-llama` keeps restarting.** `make logs-llama`. The usual causes are a wrong model
filename, a corrupt or incomplete download (compare the size against the Hugging Face
page), or not enough RAM.

**Every response is the template summary.** `make logs-api`.
- `generation failed (ConnectionError...)`: the model container isn't up yet or has
  crashed. Check `make ps` and `make logs-llama`.
- `rejected: [...]`: the validator blocked the model's text; the reasons are listed.
  This is expected for odd source data, for example a misspelled diagnosis the model
  "corrects".
- `generation failed (ReadTimeout...)`: raise `LLAMA_TIMEOUT` or use a smaller model.

**Requests are slow.** The first request after startup processes the prompt examples
and is the slowest; repeat it and compare. If it's still above about 20 seconds, use the
1.5B model, or lower `max_tokens` in `summarizer.py`.

**Diagnosis names keep getting rejected.** By design, diagnoses must appear in the
summary exactly as written in the source. Fix typos at the source ("Malt fever" vs
"Malta fever") rather than loosening the check.

---

## Limitations

- The validator catches renamed diagnoses, missing items, invented numbers and common
  invented claims. It cannot prove a summary is clinically correct. Have a clinician
  review a batch of outputs before real use.
- Small models can still add subtle wording, for example describing a listed procedure
  as "ordered". The structured `sections` are always built straight from the source and
  are the reference for exact values.
- Vitals, free-text examination notes and the 0/1 clinical signs are returned in
  `sections` but are deliberately kept out of the summary.
- The summary is generated from what was entered, in English. Data-entry errors in the
  source pass straight through.
- Drug codes (such as `[ 733 ]`) are stripped from the output.

---

## Development notes

- Edit prompts and examples in `app/services/summarizer.py`. Edit cleaning rules and the
  template summary in `app/services/brief_facts.py`. Edit rejection rules in
  `app/services/summary_validator.py`.
- After changing code: `make build up`.
- To test a change without the model, set `ENABLE_QWEN_SUMMARIZER=false`. To test the
  validator, call `validate_brief_summary(facts, text)` directly with a hand-written
  summary.
- Add a regression case to `samples/` whenever a bad summary slips through.
