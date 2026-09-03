#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for import_path in (str(ROOT), str(SRC)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from scripts.evaluate_fault_localization import (  # noqa: E402
    _file_matches,
    _gold_files,
    _repository_name,
    _stage1_candidate_files,
    _ticket_id,
    read_records,
)


GROUP_LABELS = ("small", "medium", "large")
GROUP_LABELS_ZH = {
    "small": "小型",
    "medium": "中型",
    "large": "大型",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Group repositories by median Code Index file count and report "
            "the existing Stage-1 Top-20 baseline by size group."
        )
    )
    parser.add_argument("--gold", required=True)
    parser.add_argument("--baseline-predictions", required=True)
    parser.add_argument(
        "--size-diagnostics-predictions",
        required=True,
        help=(
            "Predictions containing stage1_diagnostics.call_graph.files. "
            "Only the Code Index file count is used; its ranking is ignored."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="reports/fault_localization/stage1_next_iteration/e5_repository_size",
    )
    parser.add_argument("--semantic-candidate-k", type=int, default=50)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.semantic_candidate_k <= 0:
        raise ValueError("semantic-candidate-k must be positive.")

    gold_path = Path(args.gold)
    baseline_path = Path(args.baseline_predictions)
    diagnostics_path = Path(args.size_diagnostics_predictions)
    for path in (gold_path, baseline_path, diagnostics_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    result = analyze_repository_size_groups(
        read_records(gold_path),
        read_records(baseline_path),
        read_records(diagnostics_path),
        semantic_candidate_k=args.semantic_candidate_k,
    )
    result["sources"] = {
        "gold": str(gold_path),
        "baseline_predictions": str(baseline_path),
        "size_diagnostics_predictions": str(diagnostics_path),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "repository_size_groups.json"
    report_path = output_dir / "E5_REPOSITORY_SIZE_GROUPS_BASELINE_ZH.md"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(render_markdown(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "repository_size_groups": str(json_path),
                "report": str(report_path),
                "repositories": len(result["repositories"]),
                "tickets": result["overall_baseline"]["tickets"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def analyze_repository_size_groups(
    gold_rows: list[dict[str, Any]],
    baseline_predictions: list[dict[str, Any]],
    size_diagnostics_predictions: list[dict[str, Any]],
    *,
    semantic_candidate_k: int = 50,
) -> dict[str, Any]:
    if semantic_candidate_k <= 0:
        raise ValueError("semantic_candidate_k must be positive.")
    gold_by_id = _index_by_ticket_id(gold_rows, "gold")
    baseline_by_id = _index_by_ticket_id(baseline_predictions, "baseline predictions")
    diagnostics_by_id = _index_by_ticket_id(
        size_diagnostics_predictions,
        "size diagnostics predictions",
    )
    expected_ids = set(gold_by_id)
    if set(baseline_by_id) != expected_ids:
        raise ValueError("Baseline prediction IDs must exactly match gold IDs.")
    if set(diagnostics_by_id) != expected_ids:
        raise ValueError("Size-diagnostic prediction IDs must exactly match gold IDs.")

    repository_file_counts: dict[str, list[int]] = {}
    ticket_rows: list[dict[str, Any]] = []
    for ticket_id in sorted(expected_ids):
        gold = gold_by_id[ticket_id]
        baseline = baseline_by_id[ticket_id]
        diagnostics = diagnostics_by_id[ticket_id]
        repository = (
            _repository_name(gold)
            or _repository_name(baseline)
            or _repository_name(diagnostics)
            or "unknown"
        )
        file_count = extract_code_index_file_count(diagnostics)
        repository_file_counts.setdefault(repository, []).append(file_count)
        ticket_rows.append(
            {
                "ticket_id": ticket_id,
                "repository": repository,
                "indexed_file_count": file_count,
                "gold_files": _gold_files(gold),
                "candidate_files": _stage1_candidate_files(baseline)[:20],
            }
        )

    repositories = build_repository_groups(repository_file_counts)
    group_by_repository = {row["repository"]: row["size_group"] for row in repositories}
    for row in ticket_rows:
        row["size_group"] = group_by_repository[row["repository"]]

    repository_baselines = []
    for repository_row in repositories:
        repository = repository_row["repository"]
        summary = summarize_predictions(
            row for row in ticket_rows if row["repository"] == repository
        )
        summary.update(
            {
                "repository": repository,
                "size_group": repository_row["size_group"],
                "size_group_zh": repository_row["size_group_zh"],
            }
        )
        repository_baselines.append(summary)

    groups = []
    for group_label in GROUP_LABELS:
        group_tickets = [row for row in ticket_rows if row["size_group"] == group_label]
        group_repositories = [
            row["repository"] for row in repositories if row["size_group"] == group_label
        ]
        summary = summarize_predictions(group_tickets)
        file_counts = [row["indexed_file_count"] for row in group_tickets]
        pool_fractions = [
            min(semantic_candidate_k, value) / value for value in file_counts if value > 0
        ]
        group_repository_metrics = [
            row for row in repository_baselines if row["size_group"] == group_label
        ]
        summary.update(
            {
                "size_group": group_label,
                "size_group_zh": GROUP_LABELS_ZH[group_label],
                "repositories": group_repositories,
                "repository_count": len(group_repositories),
                "indexed_file_count": summarize_numeric(file_counts),
                "semantic_candidate_k": semantic_candidate_k,
                "candidate_pool_fraction_of_index": summarize_numeric(pool_fractions),
                "macro_repository_metrics": {
                    metric: statistics.fmean(
                        float(row[metric]) for row in group_repository_metrics
                    )
                    for metric in (
                        "hit_at_20",
                        "recall_at_20",
                        "top_1_accuracy",
                        "mrr_at_20",
                    )
                },
            }
        )
        groups.append(summary)

    return {
        "analysis_scope": "Stage-1 E5 repository-size grouping and existing E3-C baseline",
        "data_policy": {
            "split": "Validation only",
            "holdout_used": False,
            "group_assignment_uses_gold": False,
            "gold_usage": "Gold files are used only after grouping to calculate baseline metrics.",
        },
        "grouping_policy": {
            "size_signal": (
                "Unique Code Index file count recorded as "
                "stage1_diagnostics.call_graph.files"
            ),
            "repository_aggregation": (
                "Median indexed file count across the repository's Validation base commits"
            ),
            "assignment": (
                "Sort repositories by median file count, then split them into three "
                "balanced repository-count groups"
            ),
            "labels": list(GROUP_LABELS),
            "semantic_candidate_k": semantic_candidate_k,
        },
        "overall_baseline": summarize_predictions(ticket_rows),
        "repositories": repositories,
        "repository_baselines": repository_baselines,
        "groups": groups,
        "limitations": [
            (
                "The candidate-pool fraction is 50 divided by indexed file count; "
                "it is not TF-IDF Top-50 gold-file coverage."
            ),
            (
                "TF-IDF Top-50 Hit/Recall must be computed in the next E5 diagnostic "
                "before testing candidate pools 75 and 100."
            ),
        ],
    }


def extract_code_index_file_count(prediction: dict[str, Any]) -> int:
    diagnostics = prediction.get("stage1_diagnostics") or {}
    candidates = (
        (diagnostics.get("call_graph") or {}).get("files"),
        diagnostics.get("indexed_file_count"),
    )
    for value in candidates:
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            return count
    ticket_id = _ticket_id(prediction) or "unknown"
    raise ValueError(f"Missing positive Code Index file count for {ticket_id}.")


def build_repository_groups(
    repository_file_counts: dict[str, list[int]],
) -> list[dict[str, Any]]:
    if len(repository_file_counts) < len(GROUP_LABELS):
        raise ValueError("At least three repositories are required for size grouping.")
    repository_rows = []
    for repository, values in repository_file_counts.items():
        if not values or any(value <= 0 for value in values):
            raise ValueError(f"Invalid indexed file counts for {repository}.")
        repository_rows.append(
            {
                "repository": repository,
                "tickets": len(values),
                "median_indexed_files": float(statistics.median(values)),
                "minimum_indexed_files": min(values),
                "maximum_indexed_files": max(values),
            }
        )
    repository_rows.sort(key=lambda row: (row["median_indexed_files"], row["repository"]))
    group_sizes = balanced_group_sizes(len(repository_rows), len(GROUP_LABELS))
    offset = 0
    for label, size in zip(GROUP_LABELS, group_sizes):
        for row in repository_rows[offset : offset + size]:
            row["size_group"] = label
            row["size_group_zh"] = GROUP_LABELS_ZH[label]
        offset += size
    return repository_rows


def balanced_group_sizes(item_count: int, group_count: int) -> list[int]:
    if group_count <= 0 or item_count < group_count:
        raise ValueError("item_count must be at least group_count, and group_count positive.")
    quotient, remainder = divmod(item_count, group_count)
    return [quotient + (1 if index < remainder else 0) for index in range(group_count)]


def summarize_predictions(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    row_list = list(rows)
    if not row_list:
        return {
            "tickets": 0,
            "hit_at_20": 0.0,
            "recall_at_20": 0.0,
            "top_1_accuracy": 0.0,
            "mrr_at_20": 0.0,
            "full_recall_rows": 0,
            "partial_recall_rows": 0,
            "miss_rows": 0,
        }
    hit_values: list[float] = []
    recall_values: list[float] = []
    top1_values: list[float] = []
    reciprocal_ranks: list[float] = []
    full_recall_rows = 0
    partial_recall_rows = 0
    miss_rows = 0
    for row in row_list:
        gold_files = list(row.get("gold_files") or [])
        candidates = list(row.get("candidate_files") or [])[:20]
        if not gold_files:
            raise ValueError(f"Ticket {row.get('ticket_id', 'unknown')} has no gold files.")
        recovered = sum(
            any(_file_matches(candidate, gold_file) for candidate in candidates)
            for gold_file in gold_files
        )
        recall = recovered / len(gold_files)
        hit_values.append(float(recovered > 0))
        recall_values.append(recall)
        top1_values.append(
            float(
                bool(candidates)
                and any(_file_matches(candidates[0], gold_file) for gold_file in gold_files)
            )
        )
        first_rank = next(
            (
                rank
                for rank, candidate in enumerate(candidates, start=1)
                if any(_file_matches(candidate, gold_file) for gold_file in gold_files)
            ),
            None,
        )
        reciprocal_ranks.append(0.0 if first_rank is None else 1.0 / first_rank)
        if recovered == len(gold_files):
            full_recall_rows += 1
        elif recovered:
            partial_recall_rows += 1
        else:
            miss_rows += 1
    return {
        "tickets": len(row_list),
        "hit_at_20": statistics.fmean(hit_values),
        "recall_at_20": statistics.fmean(recall_values),
        "top_1_accuracy": statistics.fmean(top1_values),
        "mrr_at_20": statistics.fmean(reciprocal_ranks),
        "full_recall_rows": full_recall_rows,
        "partial_recall_rows": partial_recall_rows,
        "miss_rows": miss_rows,
    }


def summarize_numeric(values: Iterable[float | int]) -> dict[str, float]:
    value_list = [float(value) for value in values]
    if not value_list:
        return {"minimum": 0.0, "median": 0.0, "maximum": 0.0, "mean": 0.0}
    return {
        "minimum": min(value_list),
        "median": float(statistics.median(value_list)),
        "maximum": max(value_list),
        "mean": statistics.fmean(value_list),
    }


def render_markdown(result: dict[str, Any]) -> str:
    overall = result["overall_baseline"]
    lines = [
        "# E5 Repository大小分組與E3-C基準診斷",
        "",
        "## 一句話結論",
        "",
        (
            "已依Code Index檔案數將12個Repository固定分為小、中、大三組，"
            "每組4個Repository。分組只使用修正前程式碼索引大小，不使用Gold；"
            "Gold只在分組完成後計算既有E3-C基準指標。"
        ),
        "",
        "## 分組方法",
        "",
        "1. 取得每張Validation Ticket在base commit的Code Index不重複檔案數。",
        "2. 對同一Repository的不同base commit取檔案數中位數。",
        "3. 依中位數由小到大排序12個Repository。",
        "4. 每4個Repository依序分為小型、中型與大型。",
        "",
        "此方法讓三組的Repository數量相同，且不會使用準確率或Gold決定分組。",
        "",
        "## Repository分組結果",
        "",
        "| 分組 | Repository | Ticket數 | Code Index檔案數中位數 | 範圍 |",
        "|---|---|---:|---:|---:|",
    ]
    for row in result["repositories"]:
        lines.append(
            "| {group} | {repo} | {tickets} | {median:.0f} | {minimum}～{maximum} |".format(
                group=row["size_group_zh"],
                repo=row["repository"],
                tickets=row["tickets"],
                median=row["median_indexed_files"],
                minimum=row["minimum_indexed_files"],
                maximum=row["maximum_indexed_files"],
            )
        )
    lines.extend(
        [
            "",
            "## 各大小組的E3-C基準結果",
            "",
            "| 分組 | Repository數 | Ticket數 | Hit@20 | Ticket加權Recall@20 | Repository等權Recall@20 | Top-1 | MRR@20 | 完整／部分／未命中 | Top-50候選池占索引中位比例 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in result["groups"]:
        pool_fraction = row["candidate_pool_fraction_of_index"]["median"]
        lines.append(
            "| {group} | {repos} | {tickets} | {hit:.2%} | {recall:.2%} | {macro_recall:.2%} | {top1:.2%} | {mrr:.4f} | {full}／{partial}／{miss} | {pool:.2%} |".format(
                group=row["size_group_zh"],
                repos=row["repository_count"],
                tickets=row["tickets"],
                hit=row["hit_at_20"],
                recall=row["recall_at_20"],
                macro_recall=row["macro_repository_metrics"]["recall_at_20"],
                top1=row["top_1_accuracy"],
                mrr=row["mrr_at_20"],
                full=row["full_recall_rows"],
                partial=row["partial_recall_rows"],
                miss=row["miss_rows"],
                pool=pool_fraction,
            )
        )
    lines.extend(
        [
            "",
            (
                "Ticket加權結果反映500筆資料的實際平均；Repository等權結果讓每個Repository"
                "各占相同比例，可避免Ticket較多的Django主導大型組。"
            ),
            "",
            "整體E3-C基準為：Hit@20 {hit:.2%}、Recall@20 {recall:.2%}、Top-1 {top1:.2%}、MRR@20 {mrr:.4f}。".format(
                hit=overall["hit_at_20"],
                recall=overall["recall_at_20"],
                top1=overall["top_1_accuracy"],
                mrr=overall["mrr_at_20"],
            ),
            "",
            "## 結果判讀限制",
            "",
            (
                "「Top-50候選池占索引比例」只是50個候選相對於Code Index檔案數的比例，"
                "不是正確檔案進入TF-IDF Top-50的準確率。"
            ),
            "",
            (
                "下一個E5步驟必須逐筆計算TF-IDF Top-50 Hit@50與Recall@50，"
                "才能判斷大型Repository是否真的因候選池固定為50而遺漏正確檔案。"
            ),
            "",
            "本分析沒有使用Holdout，也沒有改動E3-C或E4的正式設定。",
            "",
        ]
    )
    return "\n".join(lines)


def _index_by_ticket_id(
    rows: Iterable[dict[str, Any]],
    label: str,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticket_id = _ticket_id(row)
        if not ticket_id:
            raise ValueError(f"{label} contains a row without ticket_id.")
        if ticket_id in indexed:
            raise ValueError(f"{label} contains duplicate ticket_id {ticket_id}.")
        indexed[ticket_id] = row
    return indexed


if __name__ == "__main__":
    main()
