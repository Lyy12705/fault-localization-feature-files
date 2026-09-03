#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.finalize_swebench_full_stage1_v2 import (
    artifact,
    portable_path,
    read_object,
    verify_artifact_hash,
)


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seal a one-time Final Holdout result that completed evaluation but "
            "failed the frozen Top-20 output contract."
        )
    )
    parser.add_argument("--freeze-manifest", required=True)
    parser.add_argument("--holdout-run-manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite final evaluation record: {output}")
    record = build_protocol_failure_record(
        freeze_manifest=Path(args.freeze_manifest),
        holdout_run_manifest=Path(args.holdout_run_manifest),
        expected_output=output,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": record["status"],
                "freeze_id": record["freeze_id"],
                "rows": record["holdout_result"]["rows"],
                "exact_top20_rows": record["output_contract"]["exact_top20_rows"],
                "short_rows": record["output_contract"]["short_rows"],
                "output": portable_path(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_protocol_failure_record(
    *,
    freeze_manifest: Path,
    holdout_run_manifest: Path,
    expected_output: Path,
) -> dict[str, Any]:
    freeze = read_object(freeze_manifest)
    run = read_object(holdout_run_manifest)
    if freeze.get("status") != "frozen_before_holdout":
        raise ValueError("Freeze manifest is not a valid pre-holdout seal.")
    frozen_output = Path(str(freeze.get("final_record_path") or ""))
    if not frozen_output.is_absolute():
        frozen_output = ROOT / frozen_output
    if expected_output.resolve() != frozen_output.resolve():
        raise ValueError("Final record path differs from the frozen authorization.")
    if run.get("protocol") != freeze.get("protocol"):
        raise ValueError("Holdout run protocol differs from the freeze.")
    if run.get("method_label") != freeze.get("selected_method_label"):
        raise ValueError("Holdout method label differs from the freeze.")
    if run.get("method_id") != freeze.get("selected_method_id"):
        raise ValueError("Holdout method ID differs from the freeze.")
    if run.get("method") != freeze.get("selected_method"):
        raise ValueError("Holdout method settings differ from the freeze.")
    if run.get("tickets") != freeze.get("final_holdout_rows"):
        raise ValueError("Holdout row count differs from the freeze.")
    if run.get("predictions") != run.get("tickets") or run.get("failures") != 0:
        raise ValueError("Holdout run is incomplete or contains execution failures.")
    order = run.get("evaluation_order") or {}
    if not (
        order.get("prediction_only_shards")
        and order.get("predictions_completed_before_gold_access")
        and order.get("sealed_gold_accessed_during_ranking") is False
    ):
        raise ValueError("Holdout run does not prove prediction-before-gold ordering.")

    predictions_path = resolve_run_path(run["predictions_output"])
    predictions = read_jsonl(predictions_path)
    candidate_counts = Counter(
        len(row.get("stage1_candidate_files") or []) for row in predictions
    )
    exact_rows = candidate_counts.get(20, 0)
    short_rows = sum(count for size, count in candidate_counts.items() if size < 20)
    long_rows = sum(count for size, count in candidate_counts.items() if size > 20)
    if exact_rows == len(predictions):
        raise ValueError("Output contract did not fail; use the standard finalizer.")

    tickets_path = resolve_run_path(run["tickets_path"])
    gold_path = resolve_run_path(run["gold_path"])
    verify_artifact_hash(tickets_path, freeze["frozen_holdout_artifacts"]["tickets"])
    verify_artifact_hash(gold_path, freeze["frozen_holdout_artifacts"]["gold"])
    for relative, expected in (freeze.get("implementation") or {}).items():
        verify_artifact_hash(ROOT / relative, expected)

    metrics = run.get("metrics") or {}
    return {
        "protocol": freeze.get("evaluation_protocol"),
        "status": "holdout_evaluated_once_output_contract_failed",
        "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_id": freeze.get("freeze_id"),
        "method_label": freeze.get("selected_method_label"),
        "method_id": freeze.get("selected_method_id"),
        "method": freeze.get("selected_method"),
        "pre_holdout_freeze": artifact(freeze_manifest),
        "holdout_result": {
            "rows": freeze.get("final_holdout_rows"),
            "rows_with_file_ground_truth": metrics.get("rows_with_file_ground_truth"),
            "candidate_hit_at_20": metrics.get("candidate_hit_at_20"),
            "candidate_recall_at_20": metrics.get("candidate_recall_at_20"),
            "candidate_bootstrap_95_ci": metrics.get("candidate_bootstrap_95_ci"),
            "file_top_1_accuracy": metrics.get("file_top_1_accuracy"),
            "file_top_3_accuracy": metrics.get("file_top_3_accuracy"),
            "file_top_5_accuracy": metrics.get("file_top_5_accuracy"),
            "file_mrr": metrics.get("file_mrr"),
            "outcomes": metrics.get("candidate_outcomes_at_20"),
            "base_commit_reachable_evaluation": metrics.get(
                "base_commit_reachable_evaluation"
            ),
            "per_repository": metrics.get("per_repository"),
        },
        "output_contract": {
            "required_candidates_per_ticket": 20,
            "exact_top20_rows": exact_rows,
            "short_rows": short_rows,
            "long_rows": long_rows,
            "candidate_count_distribution": {
                str(size): count for size, count in sorted(candidate_counts.items())
            },
            "standard_finalizer_result": "rejected",
            "standard_finalizer_error": (
                "Holdout output does not contain exactly 20 candidates per ticket."
            ),
        },
        "evaluation_order": order,
        "holdout_artifacts": {
            "run_manifest": artifact(holdout_run_manifest),
            "predictions": artifact(predictions_path),
            "metrics": artifact(resolve_run_path(run["metrics_output"])),
            "tickets": artifact(tickets_path),
            "gold": artifact(gold_path),
        },
        "post_evaluation_policy": (
            "This Final Holdout was evaluated exactly once. Do not modify or rerun the selected method on it. "
            "Any output-contract fix requires a new experiment ID and a new unseen holdout."
        ),
    }


def resolve_run_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"Expected JSON object in {path}.")
                rows.append(value)
    return rows


if __name__ == "__main__":
    main()
