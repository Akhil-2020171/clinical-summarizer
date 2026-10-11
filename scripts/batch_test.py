#!/usr/bin/env python3
"""Post every JSON in a folder to /summarize and report who wrote each summary.

Usage:
    python3 scripts/batch_test.py samples/cases
    python3 scripts/batch_test.py samples/cases --url http://localhost:8000 --no-warmup

Uses only the standard library. Source comes from the X-Summary-Source response
header: "llm" or "template:<reason>" (disabled, no-facts, rejected, error).
For the exact rejection reasons, run `make logs-api | grep rejected`.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def post(url: str, body: bytes, timeout: int):
    req = urllib.request.Request(
        f"{url.rstrip('/')}/summarize",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)
        source = resp.headers.get("X-Summary-Source", "unknown")
    return payload["summary"], source, time.perf_counter() - start


def last_reason(project_dir: Path):
    """Best effort: newest rejection reason (and rejected text, if logged) from the API log."""
    try:
        out = subprocess.run(
            ["docker", "compose", "logs", "--no-log-prefix", "--tail=15", "api"],
            capture_output=True, text=True, timeout=20, cwd=project_dir,
        ).stdout
    except Exception:  # noqa: BLE001  (docker missing, not running, etc.)
        return None, None
    lines = [l.strip() for l in out.splitlines()]
    reasons = [l for l in lines if "LLM summary rejected" in l or "LLM generation failed" in l]
    texts = [l for l in lines if l.startswith("Rejected text:")]
    return (reasons[-1] if reasons else None), (texts[-1] if texts else None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder", help="folder containing *.json test prescriptions")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=int, default=300, help="seconds per request")
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="skip the unmeasured warm-up request (first request is slow)",
    )
    parser.add_argument(
        "--no-reasons",
        action="store_true",
        help="do not read rejection reasons from `docker compose logs`",
    )
    args = parser.parse_args()

    files = sorted(Path(args.folder).glob("*.json"))
    if not files:
        print(f"No .json files in {args.folder}")
        return 1

    if not args.no_warmup:
        print("Warm-up request (not counted; primes the model's prompt cache)...")
        try:
            post(args.url, files[0].read_bytes(), args.timeout)
        except Exception as exc:  # noqa: BLE001
            print(f"  warm-up failed: {type(exc).__name__}: {exc}")

    results = []
    for path in files:
        try:
            summary, source, seconds = post(args.url, path.read_bytes(), args.timeout)
            error = None
        except urllib.error.HTTPError as exc:
            summary, source, seconds, error = "", "http-error", 0.0, f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            summary, source, seconds, error = "", "no-response", 0.0, type(exc).__name__
        results.append((path.name, source, seconds, summary, error))

        print(f"\n[{path.name}]  source={source}  time={seconds:.1f}s")
        print("  " + (summary if summary else f"(no summary: {error})"))
        if source in ("template:rejected", "template:error") and not args.no_reasons:
            reason, said = last_reason(Path(__file__).resolve().parent.parent)
            if reason:
                print(f"  reason: {reason}")
            if said:
                print(f"  model wrote -> {said[len('Rejected text:'):].strip()}")

    llm = [r for r in results if r[1] == "llm"]
    template = [r for r in results if r[1].startswith("template")]
    failed = [r for r in results if r[4]]

    print("\n" + "=" * 70)
    print(f"{len(results)} requests: {len(llm)} from the model, "
          f"{len(template)} from the template, {len(failed)} failed")
    if llm:
        times = [r[2] for r in llm]
        print(f"Model requests: avg {sum(times) / len(times):.1f}s, "
              f"min {min(times):.1f}s, max {max(times):.1f}s")
    rejected = [r[0] for r in results if r[1] == "template:rejected"]
    errored = [r[0] for r in results if r[1] == "template:error"]
    if rejected:
        print("Rejected by validator: " + ", ".join(rejected))
        print("  -> reasons: make logs-api | grep rejected")
    if errored:
        print("Model call failed for: " + ", ".join(errored))
        print("  -> check: make ps ; make logs-llama")
    if results:
        rate = 100 * len(llm) / len(results)
        print(f"Model acceptance rate: {rate:.0f}%  "
              "(expect case 04 'empty' and case 10 'typo' to use the template)")
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
