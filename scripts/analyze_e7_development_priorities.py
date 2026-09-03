#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable


RETRIEVAL_STAGES = {"initial_retrieval_miss", "mixed_retrieval_and_rerank"}
PRIORITY_LABELS = {
    "P0_large_multimodule_retrieval": "大型多模組專案的初步檢索遺漏",
    "P1_other_retrieval": "其他初步檢索遺漏",
    "P2_large_multimodule_other": "大型多模組專案的其他遺漏",
    "P3_other_failure": "其他失敗案例",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create E7 Development-only priority strata from Stage-1 failure "
            "analysis without reading Final Holdout artifacts."
        )
    )
    parser.add_argument("--failure-analysis", required=True)
    parser.add_argument("--tfidf-top50-cache", required=True)
    parser.add_argument("--repository-size-groups", required=True)
    parser.add_argument("--experiment-config", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_paths = [
        Path(args.failure_analysis),
        Path(args.tfidf_top50_cache),
        Path(args.repository_size_groups),
        Path(args.experiment_config),
    ]
    for path in input_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    _guard_development_only_inputs(input_paths)

    analysis = json.loads(input_paths[0].read_text(encoding="utf-8"))
    cache_rows = read_jsonl(input_paths[1])
    size_groups = load_repository_size_groups(input_paths[2])
    experiment_config = json.loads(input_paths[3].read_text(encoding="utf-8"))
    validate_experiment_config(experiment_config)
    result = analyze_e7_priorities(analysis, cache_rows, size_groups)
    result["artifacts"] = {
        "failure_analysis": artifact(input_paths[0]),
        "tfidf_top50_cache": artifact(input_paths[1]),
        "repository_size_groups": artifact(input_paths[2]),
        "experiment_config": artifact(input_paths[3]),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "e7_development_strata.json", result)
    write_jsonl(output_dir / "e7_priority_cases.jsonl", result["cases"])
    write_cases_csv(output_dir / "e7_priority_cases.csv", result["cases"])
    (output_dir / "E7_DEVELOPMENT_STRATA_AND_EXPERIMENT_SETUP_ZH.md").write_text(
        render_markdown(result), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "failure_cases": result["summary"]["failure_cases"],
                "retrieval_failure_cases": result["summary"][
                    "retrieval_failure_cases"
                ],
                "p0_cases": result["priority_counts"].get(
                    "P0_large_multimodule_retrieval", 0
                ),
                "output_dir": str(output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def analyze_e7_priorities(
    failure_analysis: dict[str, Any],
    cache_rows: list[dict[str, Any]],
    size_groups: dict[str, str],
) -> dict[str, Any]:
    sources = failure_analysis.get("sources") or {}
    if set(sources) != {"development"}:
        raise ValueError("E7 priority analysis requires exactly one development source.")
    if str(sources["development"].get("role") or "") != "development_only":
        raise ValueError("E7 source role must be development_only.")

    cache_by_id = {
        ticket_id(row): row for row in cache_rows if ticket_id(row)
    }
    cases = list(failure_analysis.get("cases") or [])
    if any(str(case.get("split") or "") != "development" for case in cases):
        raise ValueError("E7 failure cases must all belong to development.")

    large_module_counts = []
    for case in cases:
        if size_groups.get(str(case.get("repo") or "")) != "large":
            continue
        cache = cache_by_id.get(ticket_id(case), {})
        large_module_counts.append(top_level_module_count(cache.get("indexed_files") or []))
    module_threshold = max(1, int(median(large_module_counts))) if large_module_counts else 1

    enriched: list[dict[str, Any]] = []
    for case in cases:
        current_id = ticket_id(case)
        repository = str(case.get("repo") or "unknown")
        cache = cache_by_id.get(current_id, {})
        size_group = size_groups.get(repository)
        if size_group is None:
            raise ValueError(f"Repository is missing from size groups: {repository}")
        module_count = top_level_module_count(cache.get("indexed_files") or [])
        large_multimodule = size_group == "large" and module_count >= module_threshold
        failure_stage = str(case.get("failure_stage") or "analysis_unavailable")
        retrieval_failure = failure_stage in RETRIEVAL_STAGES
        priority = choose_priority(
            retrieval_failure=retrieval_failure,
            large_multimodule=large_multimodule,
        )
        enriched.append(
            {
                "priority": priority,
                "priority_zh": PRIORITY_LABELS[priority],
                "ticket_id": current_id,
                "repo": repository,
                "repository_size_group": size_group,
                "indexed_file_count": int(case.get("indexed_file_count") or 0),
                "top_level_module_count": module_count,
                "large_multimodule": large_multimodule,
                "outcome": str(case.get("outcome") or ""),
                "failure_stage": failure_stage,
                "failure_stage_zh": str(case.get("failure_stage_zh") or ""),
                "gold_file_count": int(case.get("gold_file_count") or 0),
                "recovered_gold_count": int(case.get("recovered_gold_count") or 0),
                "missing_gold_files": list(case.get("missing_gold_files") or []),
            }
        )

    enriched.sort(
        key=lambda row: (
            row["priority"],
            -row["indexed_file_count"],
            row["repo"],
            row["ticket_id"],
        )
    )
    priority_counts = dict(sorted(Counter(row["priority"] for row in enriched).items()))
    repository_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        repository_rows[row["repo"]].append(row)
    repository_summary = []
    for repository, rows in sorted(repository_rows.items()):
        repository_summary.append(
            {
                "repository": repository,
                "size_group": size_groups[repository],
                "failure_cases": len(rows),
                "retrieval_failure_cases": sum(
                    row["failure_stage"] in RETRIEVAL_STAGES for row in rows
                ),
                "large_multimodule_failure_cases": sum(
                    bool(row["large_multimodule"]) for row in rows
                ),
            }
        )

    return {
        "protocol": "stage1-e7-development-v1",
        "data_policy": {
            "allowed": "Development diagnostics and parameter design only",
            "forbidden": "Existing Final Holdout prediction, gold, failure, or repository-specific tuning",
        },
        "module_threshold_policy": (
            "Median top-level indexed module count among failed large-Repository "
            "Development cases"
        ),
        "large_multimodule_module_threshold": module_threshold,
        "summary": {
            "failure_cases": len(enriched),
            "retrieval_failure_cases": sum(
                row["failure_stage"] in RETRIEVAL_STAGES for row in enriched
            ),
            "large_multimodule_failure_cases": sum(
                bool(row["large_multimodule"]) for row in enriched
            ),
        },
        "priority_counts": priority_counts,
        "repository_summary": repository_summary,
        "experiment_matrix": {
            "E7-A": {
                "runner_method": "e7-a-e6-development-baseline",
                "description": "E6 fixed TF-IDF/SBERT 50 plus Symbol/API and Call Graph Top-3",
            },
            "E7-B": {
                "runner_method": "e7-b-large-only-100",
                "description": (
                    "Keep small and medium repositories at 50; expand only large "
                    "repositories to 100 before SBERT, while retaining E6 Call Graph"
                ),
            },
        },
        "selection_rules": {
            "primary_metric": "Overall Development Recall@20 paired E7-B minus E7-A",
            "targeted_metrics": [
                "Initial-retrieval stratum Recall@20",
                "P0 large-multimodule retrieval Recall@20",
                "Top-1 and MRR@20",
                "Runtime seconds",
            ],
            "minimum_conditions": {
                "overall_recall_at_20_difference_pp": 0.5,
                "paired_95_ci_lower_bound_pp": 0.0,
                "hit_at_20_maximum_drop_pp": 0.5,
                "all_rows_exactly_20_unique_files": True,
            },
        },
        "priority_labels": PRIORITY_LABELS,
        "cases": enriched,
    }


def choose_priority(*, retrieval_failure: bool, large_multimodule: bool) -> str:
    if retrieval_failure and large_multimodule:
        return "P0_large_multimodule_retrieval"
    if retrieval_failure:
        return "P1_other_retrieval"
    if large_multimodule:
        return "P2_large_multimodule_other"
    return "P3_other_failure"


def validate_experiment_config(payload: dict[str, Any]) -> None:
    if payload.get("version") != "stage1-e7-development-v1":
        raise ValueError("Unexpected E7 experiment config version.")
    if int((payload.get("data_policy") or {}).get("rows") or 0) != 1294:
        raise ValueError("E7 experiment config must target 1,294 Development rows.")
    expected_methods = {
        "E7-A": "e7-a-e6-development-baseline",
        "E7-B": "e7-b-large-only-100",
    }
    if payload.get("methods") != expected_methods:
        raise ValueError("E7 experiment config method labels do not match the runner.")


def top_level_module_count(indexed_files: Iterable[str]) -> int:
    modules = set()
    for raw_path in indexed_files:
        parts = [part for part in str(raw_path).replace("\\", "/").split("/") if part]
        if len(parts) > 1:
            modules.add(parts[0])
        elif parts:
            modules.add("<root>")
    return len(modules)


def load_repository_size_groups(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for size_group, repositories in (payload.get("groups") or {}).items():
        if size_group not in {"small", "medium", "large"}:
            raise ValueError(f"Unsupported repository size group: {size_group}")
        for repository in repositories or []:
            if repository in mapping:
                raise ValueError(f"Repository appears in multiple groups: {repository}")
            mapping[str(repository)] = str(size_group)
    if not mapping:
        raise ValueError("Repository size groups are empty.")
    return mapping


def _guard_development_only_inputs(paths: Iterable[Path]) -> None:
    forbidden = {"final_holdout", "frozen_holdout", "sealed"}
    for path in paths:
        normalized = str(path).lower()
        if any(token in normalized for token in forbidden):
            raise ValueError(f"E7 Development analysis refuses Holdout input: {path}")


def ticket_id(row: dict[str, Any]) -> str:
    return str(row.get("ticket_id") or row.get("instance_id") or row.get("id") or "")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_cases_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "priority",
        "priority_zh",
        "ticket_id",
        "repo",
        "repository_size_group",
        "indexed_file_count",
        "top_level_module_count",
        "large_multimodule",
        "outcome",
        "failure_stage",
        "failure_stage_zh",
        "gold_file_count",
        "recovered_gold_count",
        "missing_gold_files",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for source in rows:
            row = {key: source.get(key, "") for key in fieldnames}
            row["missing_gold_files"] = " | ".join(source["missing_gold_files"])
            writer.writerow(row)


def artifact(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest}


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# E7 Development錯誤分層與實驗設定",
        "",
        "> 本報告只使用Development。現有Final Holdout未被讀取，也不得用於E7調參。",
        "",
        "## 一、分層結果",
        "",
        f"- 失敗案例：{summary['failure_cases']}筆。",
        f"- 初步檢索相關失敗：{summary['retrieval_failure_cases']}筆。",
        f"- 大型多模組失敗：{summary['large_multimodule_failure_cases']}筆。",
        f"- 大型多模組門檻：Top-level模組數至少{result['large_multimodule_module_threshold']}個。",
        "",
        "| 優先層級 | 說明 | Ticket數 |",
        "|---|---|---:|",
    ]
    for priority, label in PRIORITY_LABELS.items():
        lines.append(f"| {priority} | {label} | {result['priority_counts'].get(priority, 0)} |")
    lines.extend(
        [
            "",
            "## 二、E7固定比較",
            "",
            "| 實驗 | 設定 |",
            "|---|---|",
            "| E7-A | E6固定50候選＋Symbol/API＋Call Graph Top-3 |",
            "| E7-B | 小型50、中型50、大型100；其餘與E7-A相同 |",
            "",
            "## 三、方法選擇規則",
            "",
            "1. 整體Recall@20至少提高0.50個百分點。",
            "2. 成對95%信賴區間下限不得小於0。",
            "3. Hit@20下降不得超過0.50個百分點。",
            "4. 所有Ticket都必須輸出20個不重複檔案。",
            "5. 同時報告P0與全部初步檢索失敗案例的Recall@20。",
            "",
            "## 四、下一步",
            "",
            "在相同1,294筆Development依序執行E7-A與E7-B，再進行成對比較。",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
