import os
import subprocess
import tempfile
from pathlib import Path

MODEL_PATH = Path(
    os.getenv(
        "SUMMARIZER_MODEL_PATH",
        str(
            Path.home()
            / "Public"
            / "clinical-summariser"
            / "models"
            / "qwen25-05b-multiclinsum-distil-q4_0.gguf"
        ),
    )
)

LLAMA_CLI_PATH = os.getenv(
    "LLAMA_CLI_PATH",
    str(
        Path.home()
        / "Public"
        / "llama.cpp"
        / "build"
        / "bin"
        / "llama-cli"
    ),
)

THREADS = int(os.getenv("LLAMA_THREADS", "4"))
CONTEXT_SIZE = 2048


class ClinicalSummarizer:
    def __init__(self):
        self.model_path = Path(MODEL_PATH)
        self.llama_cli_path = Path(LLAMA_CLI_PATH)

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Summarizer model not found: {self.model_path}"
            )

        if not self.llama_cli_path.is_file():
            raise FileNotFoundError(
                f"llama.cpp executable not found: {self.llama_cli_path}"
            )

        print(f"Clinical summary model: {self.model_path}")
        print(f"llama.cpp executable: {self.llama_cli_path}")

    def summarize(
        self,
        clinical_facts: str,
        max_new_tokens: int = 150,
    ) -> str:
        if not clinical_facts or not clinical_facts.strip():
            return ""


        prompt = f"""You are a clinical documentation assistant.
        Write a concise, human-readable outpatient prescription summary using
        only the supplied source facts.

        RULES:
        - Write in natural, professional clinical English.
        - Preserve every relevant fact provided in the source.
        - Never invent symptoms, severity, examination findings, vital signs,
        allergies, medical history, investigation results, or follow-up plans.
        - Do not interpret missing information as a negative finding.
        - Preserve complaint durations when supplied.
        - Preserve each medication's exact name, dose, frequency, duration,
        quantity, and instructions when supplied.
        - Never change medication values or associate details with the wrong drug.
        - List investigations as recorded; do not imply results are available.
        - Omit categories for which no information is supplied.
        - Do not write phrases such as "no known allergies" unless explicitly
        supported by the source.
        - Do not add recommendations or information from general medical knowledge.

        FORMAT:
        Use short paragraphs with clear headings where appropriate:
        Chief Complaints, History, Diagnoses, Investigations, Medications,
        Examination, Allergies, Follow-up, and Treatment Advice.
        Keep the wording concise and avoid unnecessary repetition.
        Return only the summary.

        SOURCE FACTS:
        {clinical_facts}

        CLINICAL SUMMARY:
        """


        with tempfile.TemporaryDirectory(
            prefix="clinical-summary-"
        ) as temp_dir:
            output_path = Path(temp_dir) / "summary.txt"

            command = [
                str(self.llama_cli_path),
                "-m", str(self.model_path),
                "-c", str(CONTEXT_SIZE),
                "-t", str(THREADS),
                "-n", str(max_new_tokens),
                "--temp", "0",
                "--single-turn",
                "--no-display-prompt",
                "--simple-io",
                "--log-disable",
                "--no-show-timings",
                "--color", "off",
                "-o", str(output_path),
                "-p", prompt,
            ]

            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    "Clinical summary generation timed out."
                ) from exc

            if result.returncode != 0:
                raise RuntimeError(
                    "llama.cpp failed to generate a summary: "
                    f"{result.stderr[-2000:]}"
                )

            if not output_path.is_file():
                raise RuntimeError(
                    "llama.cpp did not create the summary output file."
                )

            raw_output = output_path.read_text(
                encoding="utf-8"
            ).strip()

        # The output file includes "User:" and "Assistant:" labels.
        if "Assistant:" in raw_output:
            summary = raw_output.rsplit(
                "Assistant:", 1
            )[-1].strip()
        else:
            summary = raw_output

        if not summary:
            raise RuntimeError(
                "The summarizer returned an empty response."
            )

        return summary
