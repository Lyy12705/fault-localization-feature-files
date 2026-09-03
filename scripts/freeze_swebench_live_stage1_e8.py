#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_swebench_lite_fault_localization import RUNNER_INDEX_VERSION, RUNNER_METHOD_VERSION, _method_id


IMPLEMENTATION_FILES = (
    "src/utils/fault_localization.py",
    "src/modules/bug_localizer.py",
    "scripts/run_swebench_lite_fault_localization.py",
    "scripts/run_swebench_full_stage1_experiment.py",
    "scripts/evaluate_fault_localization.py",
    "scripts/create_swebench_full_final_holdout.py",
    "scripts/finalize_swebench_full_stage1_v2.py",
    "scripts/record_swebench_full_stage1_v2_protocol_failure.py",
    "scripts/freeze_swebench_live_stage1_e8.py",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze E8 source-extension repair and a new SWE-bench-Live holdout."
    )
    parser.add_argument("--prior-e7-record", required=True)
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
        prior_record_path=Path(args.prior_e7_record),
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
        "selected_method_id": freeze["selected_method_id"],
        "final_holdout_rows": freeze["final_holdout_rows"],
        "final_holdout_repositories": freeze["final_holdout_repositories"],
        "output": portable_path(output),
    }, ensure_ascii=False, indent=2))


def build_freeze_manifest(
    *,
    prior_record_path: Path,
    holdout_path: Path,
    authorized_output_dir: Path,
    final_record: Path,
) -> dict[str, Any]:
    for path in (prior_record_path, holdout_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    prior = read_object(prior_record_path)
    holdout = read_object(holdout_path)
    validate_prior_e7_record(prior)
    validate_holdout_manifest(holdout)

    method = dict(prior["method"])
    method["method_version"] = RUNNER_METHOD_VERSION
    method_id = _method_id(method)
    holdout_artifacts = holdout["artifacts"]
    tickets_artifact = validate_manifest_artifact(holdout_artifacts["tickets"])
    gold_artifact = validate_manifest_artifact(holdout_artifacts["sealed_gold"])
    freeze: dict[str, Any] = {
        "protocol": "swebench-full-stage1-protocol-v1",
        "evaluation_protocol": "swebench-live-stage1-e8-holdout-v1",
        "status": "frozen_before_holdout",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_stage": "E8 source-extension output-contract repair",
        "selection_policy": (
            "E8-A changes only source indexing coverage by adding Python stub (.pyi) and Scala (.scala) files. "
            "It retains E7-A ranking settings and is evaluated once on a new repository-disjoint SWE-bench-Live holdout."
        ),
        "repair_scope": {
            "prior_failure_status": prior["status"],
            "prior_exact_top20_rows": prior["output_contract"]["exact_top20_rows"],
            "prior_short_rows": prior["output_contract"]["short_rows"],
            "added_source_extensions": {".pyi": "python", ".scala": "scala"},
            "runner_index_version": RUNNER_INDEX_VERSION,
            "runner_method_version": RUNNER_METHOD_VERSION,
            "ranking_parameter_changes": False,
        },
        "selected_method_label": "e8-a-source-extension-contract",
        "selected_method_id": method_id,
        "selected_method": method,
        "prior_e7_record": artifact(prior_record_path),
        "final_holdout_rows": holdout["selected_rows"],
        "final_holdout_repositories": holdout["selected_repositories"],
        "final_holdout_manifest": artifact(holdout_path),
        "frozen_holdout_artifacts": {"tickets": tickets_artifact, "gold": gold_artifact},
        "implementation": {relative: artifact(ROOT / relative) for relative in IMPLEMENTATION_FILES},
        "authorized_output_dir": portable_path(authorized_output_dir),
        "final_record_path": portable_path(final_record),
        "holdout_policy": (
            "Run this exact E8-A method once. Complete and persist all predictions before opening sealed gold. "
            "Do not tune or rerun after observing metrics."
        ),
        "holdout_evaluated": False,
    }
    freeze["freeze_id"] = "stage1-e8-" + canonical_sha256(freeze)[:16]
    return freeze


def validate_prior_e7_record(record: dict[str, Any]) -> None:
    if record.get("status") != "holdout_evaluated_once_output_contract_failed":
        raise ValueError("Prior E7 record does not contain the required output-contract failure.")
    if record.get("method_label") != "e7-a-e6-development-baseline":
        raise ValueError("Prior record is not the fixed E7-A method.")
    contract = record.get("output_contract") or {}
    if contract.get("exact_top20_rows") != 20 or contract.get("short_rows") != 7:
        raise ValueError("Prior E7 output-contract evidence changed.")
    method = record.get("method")
    if not isinstance(method, dict) or method.get("semantic_candidate_k") != 50:
        raise ValueError("Prior E7-A method specification is incomplete.")
    if method.get("call_graph_mode") != "outgoing-top3":
        raise ValueError("Prior E7-A Call Graph mode changed.")


def validate_holdout_manifest(holdout: dict[str, Any]) -> None:
    if holdout.get("protocol") != "swebench-live-stage1-e8-holdout-v1":
        raise ValueError("E8 Holdout uses the wrong protocol.")
    if holdout.get("status") != "prepared_not_evaluated":
        raise ValueError("E8 Holdout has already been evaluated or is not ready.")
    if holdout.get("dataset") != "SWE-bench-Live/SWE-bench-Live":
        raise ValueError("E8 Holdout uses the wrong external dataset.")
    if holdout.get("selected_rows") != 100:
        raise ValueError("E8 Holdout must contain exactly 100 rows.")
    checks = holdout.get("leakage_checks") or {}
    if checks.get("ticket_id_overlap_with_seen") != 0 or checks.get("repository_overlap_with_seen") != 0:
        raise ValueError("E8 Holdout contains seen ticket or repository leakage.")
    if checks.get("unique_selected_ticket_ids") is not True:
        raise ValueError("E8 Holdout ticket IDs are not unique.")


def validate_manifest_artifact(record: dict[str, Any]) -> dict[str, Any]:
    path = resolve_portable_path(str(record.get("path") or ""))
    current = artifact(path)
    if current["sha256"] != record.get("sha256") or current["bytes"] != record.get("bytes"):
        raise ValueError(f"Holdout artifact drifted: {portable_path(path)}")
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
        return str(resolved.relative_to(ROOT))
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
