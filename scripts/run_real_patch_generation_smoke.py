#!/usr/bin/env python3
"""Run one real Ollama patch through the integrated localization/test boundary."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = Path("D:/bug-llm-project/bug_tracking_llm_system/bug_tracking_llm_system")
sys.path.insert(0, str(SYSTEM / "src"))

from config import PipelineConfig
from pipeline.orchestrator import build_default_orchestrator


class RecordingClient:
    def __init__(self, client):
        self.client = client
        self.raw_response = ""
        self.elapsed_seconds = 0.0

    def generate(self, prompt: str) -> str:
        started = time.perf_counter()
        self.raw_response = self.client.generate(prompt)
        self.elapsed_seconds = time.perf_counter() - started
        return self.raw_response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/fault_localization/real_patch_smoke_20260910.json")
    args = parser.parse_args()
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="real_patch_smoke_") as tmp:
        repo = Path(tmp) / "repo"
        source = repo / "src"
        tests = repo / "tests"
        source.mkdir(parents=True)
        tests.mkdir()
        (source / "username.py").write_text(
            "def normalize_username(value):\n"
            "    return value.strip().lower()\n",
            encoding="utf-8",
        )
        (tests / "test_username.py").write_text(
            "import unittest\n"
            "from src.username import normalize_username\n\n"
            "class UsernameTests(unittest.TestCase):\n"
            "    def test_none_is_empty(self):\n"
            "        self.assertEqual(normalize_username(None), '')\n\n"
            "    def test_normalization(self):\n"
            "        self.assertEqual(normalize_username(' Alice '), 'alice')\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Smoke", "-c",
             "user.email=smoke@example.com", "commit", "-m", "base"],
            check=True, capture_output=True,
        )
        base_commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        ticket = {
            "ticket_id": "REAL-PATCH-SMOKE-1",
            "title": "normalize_username crashes when username is missing",
            "description": (
                "Calling normalize_username(None) raises AttributeError. "
                "A missing username should normalize to an empty string while existing strings "
                "must still be stripped and lowercased."
            ),
            "actual_behavior": "normalize_username(None) raises AttributeError.",
            "expected_behavior": (
                "normalize_username(None) returns an empty string; non-None strings are still "
                "stripped and lowercased."
            ),
            "logs": (
                'Traceback: File "src/username.py", line 2, in normalize_username\n'
                "AttributeError: 'NoneType' object has no attribute 'strip'"
            ),
            "repo": "local/real-patch-smoke",
            "base_commit": base_commit,
            "source_dataset": "synthetic_integration_smoke",
        }
        config = PipelineConfig(
            project_root=SYSTEM,
            save_checkpoints=False,
            patch_generation_enabled=True,
            patch_generation_ollama_timeout=300,
            run_regression_tests=True,
            test_command=[sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            allow_ticket_test_commands=True,
            test_timeout_seconds=60,
        )
        orchestrator = build_default_orchestrator(config)
        recorder = RecordingClient(orchestrator.patch_generator.llm_client)
        orchestrator.patch_generator.llm_client = recorder
        localization = orchestrator.bug_localizer.localize(ticket, str(repo))
        reproduction = {
            "test_commands": [[sys.executable, "-m", "unittest", "tests.test_username.UsernameTests.test_none_is_empty"]],
            "test_patch": "",
        }
        attempts = []
        current_ticket = dict(ticket)
        patch = {}
        regression = {}
        success = False
        for attempt_number in range(1, 4):
            recorder.raw_response = ""
            recorder.elapsed_seconds = 0.0
            patch = orchestrator.patch_generator.generate(current_ticket, localization, str(repo))
            if patch.get("patch_status") == "generated":
                regression = orchestrator.regression_tester.run(patch, str(repo), reproduction)
            else:
                regression = {
                    "patch_apply": "not_run", "reproduction_result": "not_run",
                    "regression_result": "not_run", "stderr": patch.get("explanation", ""),
                }
            success = (
                patch.get("patch_status") == "generated"
                and regression.get("patch_apply") == "passed"
                and regression.get("reproduction_result") == "passed"
                and regression.get("regression_result") == "passed"
            )
            attempts.append({
                "attempt": attempt_number,
                "model_elapsed_seconds": round(recorder.elapsed_seconds, 3),
                "raw_model_response": recorder.raw_response,
                "patch": patch,
                "verification": regression,
                "success": success,
            })
            if success:
                break
            failure = str(regression.get("stderr") or "")[-1500:]
            current_ticket["description"] = (
                ticket["description"]
                + "\nA previous candidate patch failed validation or tests. Produce a different corrected patch."
                + "\nPrevious patch:\n" + str(patch.get("patch") or "<invalid output>")
                + "\nFailure output:\n" + failure
            )
        result = {
            "schema_version": "real-patch-smoke-v1",
            "model": config.patch_generation_ollama_model,
            "base_commit": base_commit,
            "localization": {
                "confidence_level": localization.get("confidence_level"),
                "recommend_patch_generation": localization.get("recommend_patch_generation"),
                "stage3_symbols": localization.get("stage3_ranked_symbols"),
            },
            "model_elapsed_seconds": round(recorder.elapsed_seconds, 3),
            "raw_model_response": recorder.raw_response,
            "attempts": attempts,
            "patch": patch,
            "verification": regression,
            "success": success,
        }
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "output": str(output), "success": success,
            "patch_status": patch.get("patch_status"),
            "confidence": localization.get("confidence_level"),
            "model_elapsed_seconds": result["model_elapsed_seconds"],
            "patch_apply": regression.get("patch_apply"),
            "reproduction_result": regression.get("reproduction_result"),
            "regression_result": regression.get("regression_result"),
        }, ensure_ascii=False, indent=2))
        raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
