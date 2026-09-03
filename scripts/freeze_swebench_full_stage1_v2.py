#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_FILES = (
    "src/utils/fault_localization.py",
    "src/modules/bug_localizer.py",
    "scripts/run_swebench_lite_fault_localization.py",
    "scripts/run_swebench_full_stage1_experiment.py",
    "scripts/evaluate_fault_localization.py",
    "scripts/analyze_swebench_full_stage1_results.py",
    "scripts/create_swebench_full_final_holdout.py",
    "scripts/finalize_swebench_full_stage1_v2.py",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze the E6 Stage-1 v2 method, implementation, and repository-disjoint "
            "Final Holdout before its one-time evaluation."
        )
    )
    parser.add_argument("--baseline-validation-run", required=True)
    parser.add_argument("--selected-validation-run", required=True)
    parser.add_argument("--paired-analysis", required=True)
    parser.add_argument("--current-parity-run", required=True)
    parser.add_argument("--current-parity-predictions", required=True)
    parser.add_argument("--reference-validation-predictions", required=True)
    parser.add_argument("--final-holdout-manifest", required=True)
    parser.add_argument("--authorized-output-dir", required=True)
    parser.add_argument("--final-record", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    freeze = build_freeze_manifest(
        baseline_validation_run=Path(args.baseline_validation_run),
        selected_validation_run=Path(args.selected_validation_run),
        paired_analysis=Path(args.paired_analysis),
        current_parity_run=Path(args.current_parity_run),
        current_parity_predictions=Path(args.current_parity_predictions),
        reference_validation_predictions=Path(args.reference_validation_predictions),
        final_holdout_manifest=Path(args.final_holdout_manifest),
        authorized_output_dir=Path(args.authorized_output_dir),
        final_record=Path(args.final_record),
    )
    output_path = Path(args.output)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite frozen protocol: {portable_path(output_path)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": freeze["status"],
                "freeze_id": freeze["freeze_id"],
                "selected_method_label": freeze["selected_method_label"],
                "selected_method_id": freeze["selected_method_id"],
                "parity_rows": freeze["current_implementation_parity"]["rows"],
                "final_holdout_rows": freeze["final_holdout_rows"],
                "final_holdout_repositories": freeze["final_holdout_repositories"],
                "holdout_evaluated": False,
                "output": portable_path(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_freeze_manifest(
    *,
    baseline_validation_run: Path,
    selected_validation_run: Path,
    paired_analysis: Path,
    current_parity_run: Path,
    current_parity_predictions: Path,
    reference_validation_predictions: Path,
    final_holdout_manifest: Path,
    authorized_output_dir: Path,
    final_record: Path,
) -> dict[str, Any]:
    paths = (
        baseline_validation_run,
        selected_validation_run,
        paired_analysis,
        current_parity_run,
        current_parity_predictions,
        reference_validation_predictions,
        final_holdout_manifest,
    )
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    baseline = read_object(baseline_validation_run)
    selected = read_object(selected_validation_run)
    paired = read_object(paired_analysis)
    parity_run = read_object(current_parity_run)
    holdout = read_object(final_holdout_manifest)
    validate_validation_run(baseline, expected_label="e3-c-api-implementation")
    validate_validation_run(selected, expected_label="e4-c-call-outgoing-top3")
    validate_parity_run(parity_run, expected_label="e4-c-call-outgoing-top3")
    paired_result = validate_paired_selection(paired)
    parity = validate_prediction_parity(
        read_jsonl(current_parity_predictions),
        read_jsonl(reference_validation_predictions),
    )
    validate_holdout_manifest(holdout)

    holdout_artifacts = holdout["artifacts"]
    tickets_artifact = validate_manifest_artifact(holdout_artifacts["tickets"])
    gold_artifact = validate_manifest_artifact(holdout_artifacts["sealed_gold"])
    method = parity_run.get("method")
    if not isinstance(method, dict) or not method:
        raise ValueError("Current parity run is missing its complete method specification.")
    if method.get("semantic_candidate_k") != 50:
        raise ValueError("E6 must retain E5-A fixed semantic candidate count 50.")
    if method.get("semantic_candidate_policy") not in (None, "fixed"):
        raise ValueError("E6 must use the fixed E5-A candidate policy.")
    if method.get("call_graph_mode") != "outgoing-top3":
        raise ValueError("E6 must retain the validated E4 Top-3 Call Graph mode.")

    freeze: dict[str, Any] = {
        "protocol": "swebench-full-stage1-protocol-v1",
        "evaluation_protocol": "swebench-full-stage1-final-holdout-v2",
        "status": "frozen_before_holdout",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_stage": "E6 final combination and pre-holdout freeze",
        "selection_policy": (
            "Recall@20 is primary. E4 Top-3 is retained because its paired 95% CI "
            "against E3-C is above zero; E5-A fixed-50 candidate sizing is retained "
            "because E5-B/E5-C did not show a reliable improvement."
        ),
        "selected_method_label": parity_run["method_label"],
        "selected_method_id": parity_run["method_id"],
        "selected_method": method,
        "selected_validation_evidence": {
            "rows": selected["tickets"],
            "candidate_hit_at_20": selected["metrics"]["candidate_hit_at_20"],
            "candidate_recall_at_20": selected["metrics"]["candidate_recall_at_20"],
            "file_top_1_accuracy": selected["metrics"]["file_top_1_accuracy"],
            "file_mrr_runner_scope": selected["metrics"]["file_mrr"],
            "paired_vs_e3c": paired_result,
            "tradeoff": (
                "Recall@20 improves while Top-1 and MRR@20 decline; the final report must "
                "show all metrics and may not describe this as a universal ranking improvement."
            ),
        },
        "current_implementation_parity": parity,
        "validation_artifacts": {
            "baseline_run": artifact(baseline_validation_run),
            "selected_run": artifact(selected_validation_run),
            "paired_analysis": artifact(paired_analysis),
            "current_parity_run": artifact(current_parity_run),
            "current_parity_predictions": artifact(current_parity_predictions),
        },
        "final_holdout_rows": holdout["selected_rows"],
        "final_holdout_repositories": holdout["selected_repositories"],
        "final_holdout_manifest": artifact(final_holdout_manifest),
        "frozen_holdout_artifacts": {
            "tickets": tickets_artifact,
            "gold": gold_artifact,
        },
        "implementation": {
            relative: artifact(ROOT / relative)
            for relative in IMPLEMENTATION_FILES
        },
        "authorized_output_dir": portable_path(authorized_output_dir),
        "final_record_path": portable_path(final_record),
        "holdout_policy": (
            "Run this exact method once on the sealed Final Holdout. Do not inspect gold "
            "before predictions complete, and do not tune or rerun after observing metrics."
        ),
        "holdout_evaluated": False,
    }
    freeze["freeze_id"] = "stage1-v2-" + canonical_sha256(freeze)[:16]
    return freeze


def validate_validation_run(run: dict[str, Any], *, expected_label: str) -> None:
    if run.get("protocol") != "swebench-full-stage1-protocol-v1":
        raise ValueError(f"Validation run uses the wrong protocol: {expected_label}")
    if run.get("method_label") != expected_label:
        raise ValueError(f"Unexpected validation method label: {run.get('method_label')}")
    if run.get("tickets") != 500 or run.get("predictions") != 500 or run.get("failures") != 0:
        raise ValueError(f"Validation run is incomplete: {expected_label}")
    metrics = run.get("metrics") or {}
    if metrics.get("rows_missing_stage1_output") != 0:
        raise ValueError(f"Validation output is missing Stage-1 candidates: {expected_label}")
    if metrics.get("average_candidate_count_at_20") != 20.0:
        raise ValueError(f"Validation output is not fixed Top-20: {expected_label}")


def validate_parity_run(run: dict[str, Any], *, expected_label: str) -> None:
    if run.get("method_label") != expected_label:
        raise ValueError("Current parity run uses the wrong method.")
    if run.get("tickets") != 30 or run.get("predictions") != 30 or run.get("failures") != 0:
        raise ValueError("Current implementation parity run must contain 30 successful rows.")


def validate_paired_selection(paired: dict[str, Any]) -> dict[str, Any]:
    if paired.get("rows") != 500 or paired.get("paired_baseline") != "original_e3c":
        raise ValueError("E4 paired analysis does not use the expected 500-row E3-C baseline.")
    result = (paired.get("paired_differences") or {}).get("e4_top3")
    if not isinstance(result, dict):
        raise ValueError("E4 paired analysis is missing e4_top3.")
    recall = result.get("recall_at_20") or {}
    lower = float((recall.get("bootstrap_95_ci") or {}).get("lower", 0.0))
    if float(recall.get("mean_difference", 0.0)) <= 0.0 or lower <= 0.0:
        raise ValueError("E4 Top-3 does not have a positive paired Recall@20 confidence interval.")
    return result


def validate_prediction_parity(
    current: list[dict[str, Any]],
    reference: list[dict[str, Any]],
) -> dict[str, Any]:
    reference_by_id = {ticket_id(row): row for row in reference}
    if len(current) != 30:
        raise ValueError("Current parity predictions must contain 30 rows.")
    mismatches: list[str] = []
    for row in current:
        current_id = ticket_id(row)
        previous = reference_by_id.get(current_id)
        if previous is None or candidate_projection(row) != candidate_projection(previous):
            mismatches.append(current_id)
    if mismatches:
        raise ValueError(
            "Current implementation changed E4 Top-20 output for parity tickets: "
            + ", ".join(mismatches[:5])
        )
    return {
        "rows": len(current),
        "exact_top20_file_order_matches": len(current),
        "exact_retrieval_scores_match": len(current),
        "reference_method_version": "fault-localization-method-v18",
        "frozen_method_version": str(
            ((current[0].get("benchmark_run") or {}).get("method") or {}).get("method_version")
            if current
            else ""
        ),
    }


def candidate_projection(row: dict[str, Any]) -> list[tuple[str, Any]]:
    return [
        (str(candidate.get("file_path") or ""), candidate.get("retrieval_score"))
        for candidate in (row.get("stage1_candidate_files") or [])[:20]
    ]


def validate_holdout_manifest(holdout: dict[str, Any]) -> None:
    if holdout.get("protocol") != "swebench-full-stage1-final-holdout-v2":
        raise ValueError("Final Holdout uses the wrong protocol.")
    if holdout.get("status") != "prepared_not_evaluated":
        raise ValueError("Final Holdout has already been evaluated or is not ready.")
    if holdout.get("selected_rows") != 500:
        raise ValueError("Final Holdout must contain exactly 500 rows.")
    checks = holdout.get("leakage_checks") or {}
    if checks.get("ticket_id_overlap_with_seen") != 0:
        raise ValueError("Final Holdout has seen Ticket leakage.")
    if checks.get("repository_overlap_with_seen") != 0:
        raise ValueError("Final Holdout has seen Repository leakage.")
    if checks.get("unique_selected_ticket_ids") is not True:
        raise ValueError("Final Holdout ticket IDs are not unique.")


def validate_manifest_artifact(record: dict[str, Any]) -> dict[str, Any]:
    path = resolve_portable_path(str(record.get("path") or ""))
    current = artifact(path)
    if current["sha256"] != record.get("sha256") or current["bytes"] != record.get("bytes"):
        raise ValueError(f"Final Holdout artifact drifted: {portable_path(path)}")
    return current


def ticket_id(row: dict[str, Any]) -> str:
    return str(row.get("ticket_id") or row.get("instance_id") or "")


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def artifact(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": portable_path(resolved),
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def resolve_portable_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: dict[str, Any]) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
