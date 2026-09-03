#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seal the one-time SWE-bench Full Stage-1 v2 Final Holdout result."
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
    record = finalize(
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
                "output": portable_path(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def finalize(
    *,
    freeze_manifest: Path,
    holdout_run_manifest: Path,
    expected_output: Path,
) -> dict[str, Any]:
    for path in (freeze_manifest, holdout_run_manifest):
        if not path.is_file():
            raise FileNotFoundError(path)
    freeze = read_object(freeze_manifest)
    run = read_object(holdout_run_manifest)
    if freeze.get("status") != "frozen_before_holdout":
        raise ValueError("Freeze manifest is not a valid pre-holdout seal.")
    if portable_path(expected_output) != freeze.get("final_record_path"):
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
        raise ValueError("Holdout run is incomplete or contains failures.")
    metrics = run.get("metrics") or {}
    if metrics.get("matched_prediction_rows") != freeze.get("final_holdout_rows"):
        raise ValueError("Holdout metrics do not cover every frozen row.")
    if metrics.get("rows_missing_stage1_output") != 0:
        raise ValueError("Holdout output is missing Stage-1 candidates.")
    if metrics.get("average_candidate_count_at_20") != 20.0:
        raise ValueError("Holdout output does not contain exactly 20 candidates per ticket.")
    verify_artifact_hash(Path(run["tickets_path"]), freeze["frozen_holdout_artifacts"]["tickets"])
    verify_artifact_hash(Path(run["gold_path"]), freeze["frozen_holdout_artifacts"]["gold"])
    for relative, expected in (freeze.get("implementation") or {}).items():
        verify_artifact_hash(ROOT / relative, expected)

    return {
        "protocol": freeze.get("evaluation_protocol"),
        "status": "holdout_evaluated_once",
        "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_id": freeze.get("freeze_id"),
        "method_label": freeze.get("selected_method_label"),
        "method_id": freeze.get("selected_method_id"),
        "method": freeze.get("selected_method"),
        "pre_holdout_freeze": artifact(freeze_manifest),
        "holdout_result": {
            "rows": freeze.get("final_holdout_rows"),
            "candidate_hit_at_20": metrics.get("candidate_hit_at_20"),
            "candidate_recall_at_20": metrics.get("candidate_recall_at_20"),
            "candidate_bootstrap_95_ci": metrics.get("candidate_bootstrap_95_ci"),
            "file_top_1_accuracy": metrics.get("file_top_1_accuracy"),
            "file_top_3_accuracy": metrics.get("file_top_3_accuracy"),
            "file_top_5_accuracy": metrics.get("file_top_5_accuracy"),
            "file_mrr": metrics.get("file_mrr"),
            "outcomes": metrics.get("candidate_outcomes_at_20"),
            "per_repository": metrics.get("per_repository"),
        },
        "holdout_artifacts": {
            "run_manifest": artifact(holdout_run_manifest),
            "predictions": artifact(Path(run["predictions_output"])),
            "metrics": artifact(Path(run["metrics_output"])),
            "tickets": artifact(Path(run["tickets_path"])),
            "gold": artifact(Path(run["gold_path"])),
        },
        "post_evaluation_policy": (
            "Do not tune or rerun v2 on this Final Holdout. Any later method requires a new "
            "experiment ID and a new unseen holdout."
        ),
    }


def verify_artifact_hash(path: Path, expected: dict[str, Any]) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256_file(path) != expected.get("sha256") or path.stat().st_size != expected.get("bytes"):
        raise ValueError(f"Frozen artifact changed: {portable_path(path)}")


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": portable_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
