#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for import_path in (str(ROOT), str(SRC)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from scripts.analyze_swebench_full_stage1_results import (  # noqa: E402
    mean,
    paired_differences,
    parse_prediction_args,
    ticket_metric_rows,
)
from scripts.evaluate_fault_localization import (  # noqa: E402
    _repository_name,
    _ticket_id,
    read_records,
)


GROUP_LABELS = ("small", "medium", "large")
METRIC_NAMES = ("hit_at_20", "recall_at_20", "top_1_accuracy", "mrr_at_20")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize E5 methods by frozen repository-size group."
    )
    parser.add_argument("--gold", required=True)
    parser.add_argument("--repository-size-groups", required=True)
    parser.add_argument(
        "--prediction",
        action="append",
        required=True,
        help="LABEL=predictions.jsonl; the first method is the paired baseline.",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260823)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.bootstrap_samples <= 0:
        raise ValueError("bootstrap-samples must be positive.")
    group_by_repository = load_repository_size_groups(
        Path(args.repository_size_groups)
    )
    prediction_paths = parse_prediction_args(args.prediction)
    result = analyze_size_aware_results(
        read_records(args.gold),
        {
            label: read_records(path)
            for label, path in prediction_paths.items()
        },
        group_by_repository,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    result["sources"] = {
        "gold": str(Path(args.gold)),
        "repository_size_groups": str(Path(args.repository_size_groups)),
        "predictions": {
            label: str(path) for label, path in prediction_paths.items()
        },
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def load_repository_size_groups(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    groups = payload.get("groups") if isinstance(payload, dict) else None
    if not isinstance(groups, dict):
        raise ValueError("Repository-size config must contain a groups object.")
    mapping: dict[str, str] = {}
    for label in GROUP_LABELS:
        repositories = groups.get(label)
        if not isinstance(repositories, list) or not repositories:
            raise ValueError(f"Repository-size group is missing or empty: {label}")
        for repository in repositories:
            normalized = str(repository).strip()
            if not normalized:
                raise ValueError(f"Repository-size group contains an empty entry: {label}")
            if normalized in mapping:
                raise ValueError(
                    f"Repository appears in multiple size groups: {normalized}"
                )
            mapping[normalized] = label
    return mapping


def analyze_size_aware_results(
    gold_rows: list[dict[str, Any]],
    predictions_by_method: dict[str, list[dict[str, Any]]],
    group_by_repository: dict[str, str],
    *,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    if not predictions_by_method:
        raise ValueError("At least one prediction method is required.")
    method_rows: dict[str, list[dict[str, Any]]] = {}
    method_runtime: dict[str, dict[str, float | int]] = {}
    expected_ticket_ids = {
        _ticket_id(row) for row in gold_rows if _ticket_id(row)
    }
    for position, (label, predictions) in enumerate(predictions_by_method.items()):
        prediction_ids = {_ticket_id(row) for row in predictions if _ticket_id(row)}
        if prediction_ids != expected_ticket_ids:
            raise ValueError(f"Prediction IDs do not exactly match gold: {label}")
        rows = ticket_metric_rows(gold_rows, predictions)
        for row in rows:
            repository = str(row["repo"])
            if repository not in group_by_repository:
                raise ValueError(f"Repository has no frozen size group: {repository}")
            row["size_group"] = group_by_repository[repository]
        method_rows[label] = rows
        method_runtime[label] = summarize_runtime(predictions, group_by_repository)

    baseline_label = next(iter(predictions_by_method))
    methods: dict[str, Any] = {}
    for method_position, label in enumerate(predictions_by_method):
        rows = method_rows[label]
        groups: dict[str, Any] = {}
        for group_position, group in enumerate(GROUP_LABELS):
            subset = [row for row in rows if row["size_group"] == group]
            groups[group] = summarize_metric_rows(subset)
            if label != baseline_label:
                baseline_subset = [
                    row
                    for row in method_rows[baseline_label]
                    if row["size_group"] == group
                ]
                groups[group]["paired_vs_baseline"] = paired_differences(
                    baseline_subset,
                    subset,
                    bootstrap_samples=bootstrap_samples,
                    seed=seed + method_position * 1000 + group_position * 100,
                )
        methods[label] = {
            "overall": summarize_metric_rows(rows),
            "groups": groups,
            "runtime": method_runtime[label],
        }

    return {
        "analysis_scope": "E5 Stage-1 Top-20 by frozen repository-size group",
        "rows": len(gold_rows),
        "paired_baseline": baseline_label,
        "group_labels": list(GROUP_LABELS),
        "methods": methods,
        "bootstrap_samples": bootstrap_samples,
        "seed": seed,
        "holdout_used": False,
    }


def summarize_metric_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        **{
            metric: mean([float(row[metric]) for row in rows])
            for metric in METRIC_NAMES
        },
        "full_recall_rows": sum(row["outcome"] == "full_recall" for row in rows),
        "partial_recall_rows": sum(row["outcome"] == "partial_recall" for row in rows),
        "miss_rows": sum(row["outcome"] == "miss" for row in rows),
    }


def summarize_runtime(
    predictions: list[dict[str, Any]],
    group_by_repository: dict[str, str],
) -> dict[str, Any]:
    values: list[tuple[str, float]] = []
    for prediction in predictions:
        repository = _repository_name(prediction) or "unknown"
        if repository not in group_by_repository:
            raise ValueError(f"Repository has no frozen size group: {repository}")
        raw_runtime = (prediction.get("benchmark_run") or {}).get("runtime_seconds", 0.0)
        try:
            runtime = float(raw_runtime)
        except (TypeError, ValueError):
            runtime = 0.0
        values.append((group_by_repository[repository], runtime))
    by_group = {}
    for group in GROUP_LABELS:
        group_values = [runtime for label, runtime in values if label == group]
        by_group[group] = {
            "rows": len(group_values),
            "sum_seconds": sum(group_values),
            "mean_seconds": mean(group_values),
        }
    all_values = [runtime for _, runtime in values]
    return {
        "rows": len(all_values),
        "sum_seconds": sum(all_values),
        "mean_seconds": mean(all_values),
        "by_group": by_group,
    }


if __name__ == "__main__":
    main()
