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
    "scripts/freeze_swebench_full_stage1_e7.py",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze selected E7-A and a new repository-disjoint holdout before one-time evaluation."
    )
    parser.add_argument("--selection", required=True)
    parser.add_argument("--baseline-development-run", required=True)
    parser.add_argument("--candidate-development-run", required=True)
    parser.add_argument("--paired-analysis", required=True)
    parser.add_argument("--final-holdout-manifest", required=True)
    parser.add_argument("--authorized-output-dir", required=True)
    parser.add_argument("--final-record", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen protocol: {portable_path(output)}")
    freeze = build_freeze_manifest(
        selection_path=Path(args.selection),
        baseline_run_path=Path(args.baseline_development_run),
        candidate_run_path=Path(args.candidate_development_run),
        paired_path=Path(args.paired_analysis),
        holdout_path=Path(args.final_holdout_manifest),
        authorized_output_dir=Path(args.authorized_output_dir),
        final_record=Path(args.final_record),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": freeze["status"],
        "freeze_id": freeze["freeze_id"],
        "selected_method_label": freeze["selected_method_label"],
        "final_holdout_rows": freeze["final_holdout_rows"],
        "final_holdout_repositories": freeze["final_holdout_repositories"],
        "output": portable_path(output),
    }, ensure_ascii=False, indent=2))


def build_freeze_manifest(
    *,
    selection_path: Path,
    baseline_run_path: Path,
    candidate_run_path: Path,
    paired_path: Path,
    holdout_path: Path,
    authorized_output_dir: Path,
    final_record: Path,
) -> dict[str, Any]:
    paths = (selection_path, baseline_run_path, candidate_run_path, paired_path, holdout_path)
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    selection = read_object(selection_path)
    baseline = read_object(baseline_run_path)
    candidate = read_object(candidate_run_path)
    paired = read_object(paired_path)
    holdout = read_object(holdout_path)
    validate_e7_selection(selection, baseline, candidate, paired)
    validate_holdout_manifest(holdout)

    method = baseline.get("method")
    if not isinstance(method, dict) or not method:
        raise ValueError("E7-A run is missing its complete method specification.")
    if method.get("semantic_candidate_k") != 50 or method.get("call_graph_mode") != "outgoing-top3":
        raise ValueError("E7-A no longer matches the fixed semantic-k=50, outgoing-top3 method.")

    artifacts = holdout["artifacts"]
    tickets_artifact = validate_manifest_artifact(artifacts["tickets"])
    gold_artifact = validate_manifest_artifact(artifacts["sealed_gold"])
    freeze: dict[str, Any] = {
        "protocol": "swebench-full-stage1-protocol-v1",
        "evaluation_protocol": "swebench-full-stage1-e7-unseen-holdout-v1",
        "status": "frozen_before_holdout",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_stage": "E7-A post-selection unseen repository holdout",
        "selection_policy": (
            "E7-A is retained because E7-B failed the prespecified overall Recall@20 and paired-CI gates. "
            "The holdout contains every remaining repository-disjoint train row and is evaluated once."
        ),
        "selected_method_label": baseline["method_label"],
        "selected_method_id": baseline["method_id"],
        "selected_method": method,
        "selected_development_evidence": {
            "rows": baseline["tickets"],
            "candidate_hit_at_20": baseline["metrics"]["candidate_hit_at_20"],
            "candidate_recall_at_20": baseline["metrics"]["candidate_recall_at_20"],
            "file_top_1_accuracy": baseline["metrics"]["file_top_1_accuracy"],
            "file_mrr_runner_scope": baseline["metrics"]["file_mrr"],
            "decision": selection["decision"],
            "selected_method": selection["selected_method"],
        },
        "selection_artifacts": {
            "selection": artifact(selection_path),
            "baseline_development_run": artifact(baseline_run_path),
            "candidate_development_run": artifact(candidate_run_path),
            "paired_analysis": artifact(paired_path),
        },
        "final_holdout_rows": holdout["selected_rows"],
        "final_holdout_repositories": holdout["selected_repositories"],
        "final_holdout_manifest": artifact(holdout_path),
        "frozen_holdout_artifacts": {"tickets": tickets_artifact, "gold": gold_artifact},
        "implementation": {relative: artifact(ROOT / relative) for relative in IMPLEMENTATION_FILES},
        "authorized_output_dir": portable_path(authorized_output_dir),
        "final_record_path": portable_path(final_record),
        "holdout_policy": (
            "Run this exact E7-A method once. Do not inspect sealed gold before predictions complete; "
            "do not tune or rerun after metrics are observed."
        ),
        "holdout_evaluated": False,
    }
    freeze["freeze_id"] = "stage1-e7-" + canonical_sha256(freeze)[:16]
    return freeze


def validate_e7_selection(
    selection: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any], paired: dict[str, Any]
) -> None:
    if selection.get("decision") != "not_retained" or selection.get("selected_method") != "E7-A":
        raise ValueError("Selection does not retain E7-A.")
    if selection.get("selected_runner_method") != "e7-a-e6-development-baseline":
        raise ValueError("Selection has an unexpected E7-A runner method.")
    expected = (("E7-A", baseline), ("E7-B", candidate))
    for label, run in expected:
        expected_method = "e7-a-e6-development-baseline" if label == "E7-A" else "e7-b-large-only-100"
        if run.get("protocol") != "swebench-full-stage1-protocol-v1" or run.get("method_label") != expected_method:
            raise ValueError(f"{label} development run uses the wrong protocol or method.")
        if run.get("tickets") != 1294 or run.get("predictions") != 1294 or run.get("failures") != 0:
            raise ValueError(f"{label} development run is incomplete.")
        metrics = run.get("metrics") or {}
        if metrics.get("rows_missing_stage1_output") != 0 or metrics.get("average_candidate_count_at_20") != 20.0:
            raise ValueError(f"{label} violates the Top-20 output contract.")
    if baseline.get("method_id") != selection.get("selected_method_id"):
        raise ValueError("Selected method ID differs from E7-A.")
    if paired.get("rows") != 1294 or paired.get("paired_baseline") != "E7-A":
        raise ValueError("E7 paired analysis has the wrong scope or baseline.")
    observed = selection.get("observed") or {}
    gates = selection.get("gates") or {}
    if gates.get("overall_recall_improvement") is not False or gates.get("paired_recall_ci_lower_bound") is not False:
        raise ValueError("E7 selection does not record the expected failed improvement gates.")
    if float(observed.get("overall_recall_at_20_difference_pp", 1.0)) >= 0.5:
        raise ValueError("Recorded E7-B improvement no longer supports retaining E7-A.")


def validate_holdout_manifest(holdout: dict[str, Any]) -> None:
    if holdout.get("protocol") != "swebench-full-stage1-final-holdout-v2":
        raise ValueError("Final Holdout uses the wrong protocol.")
    if holdout.get("status") != "prepared_not_evaluated":
        raise ValueError("Final Holdout has already been evaluated or is not ready.")
    if int(holdout.get("selected_rows") or 0) <= 0:
        raise ValueError("Final Holdout must contain at least one row.")
    checks = holdout.get("leakage_checks") or {}
    if checks.get("ticket_id_overlap_with_seen") != 0 or checks.get("repository_overlap_with_seen") != 0:
        raise ValueError("Final Holdout contains seen ticket or repository leakage.")
    if checks.get("unique_selected_ticket_ids") is not True:
        raise ValueError("Final Holdout ticket IDs are not unique.")


def validate_manifest_artifact(record: dict[str, Any]) -> dict[str, Any]:
    path = resolve_portable_path(str(record.get("path") or ""))
    current = artifact(path)
    if current["sha256"] != record.get("sha256") or current["bytes"] != record.get("bytes"):
        raise ValueError(f"Final Holdout artifact drifted: {portable_path(path)}")
    return current


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": portable_path(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def resolve_portable_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
