#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for import_path in (str(ROOT), str(SRC)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from scripts.analyze_stage1_failure_cases import (  # noqa: E402
    build_top50_cache_row,
    read_jsonl_by_id,
    write_json,
    write_jsonl,
)
from scripts.evaluate_fault_localization import (  # noqa: E402
    _file_matches,
    _gold_files,
    _repository_name,
    _ticket_id,
    read_records,
)


GROUP_ORDER = ("small", "medium", "large")
GROUP_LABELS_ZH = {
    "small": "小型",
    "medium": "中型",
    "large": "大型",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build raw TF-IDF Top-50 file candidates for all Validation tickets "
            "and report Hit@50 and Recall@50 by fixed repository-size group."
        )
    )
    parser.add_argument("--tickets", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--repository-groups", required=True)
    parser.add_argument("--index-cache-dir", action="append", required=True)
    parser.add_argument(
        "--seed-cache",
        action="append",
        default=[],
        help="Existing compatible TF-IDF Top-50 JSONL cache to reuse.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/fault_localization/stage1_next_iteration/e5_repository_size",
    )
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--checkpoint-every", type=int, default=10)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.max_workers <= 0:
        raise ValueError("max-workers must be positive.")
    if args.checkpoint_every <= 0:
        raise ValueError("checkpoint-every must be positive.")

    tickets_path = Path(args.tickets)
    gold_path = Path(args.gold)
    groups_path = Path(args.repository_groups)
    index_cache_dirs = [Path(value) for value in args.index_cache_dir]
    seed_cache_paths = [Path(value) for value in args.seed_cache]
    for path in (tickets_path, gold_path, groups_path, *index_cache_dirs):
        if not path.exists():
            raise FileNotFoundError(path)
    for path in seed_cache_paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    tickets = read_records(tickets_path)
    gold_rows = read_records(gold_path)
    groups = json.loads(groups_path.read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / "tfidf_top50_all_500.jsonl"
    json_path = output_dir / "tfidf_top50_by_size.json"
    previous_execution: dict[str, Any] = {}
    if json_path.is_file():
        previous_result = json.loads(json_path.read_text(encoding="utf-8"))
        previous_execution = dict(previous_result.get("execution") or {})

    start = time.monotonic()
    cache, reused_rows, computed_rows = build_complete_top50_cache(
        tickets,
        index_cache_dirs=index_cache_dirs,
        cache_path=cache_path,
        seed_cache_paths=seed_cache_paths,
        max_workers=args.max_workers,
        checkpoint_every=args.checkpoint_every,
    )
    result = analyze_top50_by_size(
        tickets,
        gold_rows,
        cache,
        groups,
    )
    current_execution = {
        "cache_rows_reused": reused_rows,
        "cache_rows_computed": computed_rows,
        "cache_rows_total": len(cache),
        "max_workers": args.max_workers,
        "wall_seconds": round(time.monotonic() - start, 3),
    }
    if (
        computed_rows == 0
        and int(previous_execution.get("cache_rows_total") or 0) == len(cache)
    ):
        current_execution = previous_execution
        current_execution["last_analysis_refresh_seconds"] = round(
            time.monotonic() - start,
            3,
        )
    result.update(
        {
            "sources": {
                "tickets": str(tickets_path),
                "gold": str(gold_path),
                "repository_groups": str(groups_path),
                "index_cache_dirs": [str(path) for path in index_cache_dirs],
                "seed_caches": [str(path) for path in seed_cache_paths],
                "complete_top50_cache": str(cache_path),
            },
            "execution": current_execution,
        }
    )
    report_path = output_dir / "E5_TFIDF_TOP50_BY_SIZE_ZH.md"
    write_json(json_path, result)
    report_path.write_text(render_markdown(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "cache": str(cache_path),
                "analysis": str(json_path),
                "report": str(report_path),
                "tickets": result["overall"]["tickets"],
                "hit_at_50": result["overall"]["hit_at_50"],
                "recall_at_50": result["overall"]["recall_at_50"],
                "cache_rows_reused": reused_rows,
                "cache_rows_computed": computed_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_complete_top50_cache(
    tickets: list[dict[str, Any]],
    *,
    index_cache_dirs: list[Path],
    cache_path: Path,
    seed_cache_paths: list[Path],
    max_workers: int,
    checkpoint_every: int,
) -> tuple[dict[str, dict[str, Any]], int, int]:
    tickets_by_id = index_by_ticket_id(tickets, "tickets")
    cache = read_jsonl_by_id(cache_path)
    for seed_path in seed_cache_paths:
        for ticket_id, row in read_jsonl_by_id(seed_path).items():
            if ticket_id in tickets_by_id and cache_row_is_compatible(
                row,
                tickets_by_id[ticket_id],
            ):
                cache.setdefault(ticket_id, row)
    reused_rows = sum(
        cache_row_is_compatible(cache.get(ticket_id), ticket)
        for ticket_id, ticket in tickets_by_id.items()
    )
    missing_ids = [
        ticket_id
        for ticket_id, ticket in tickets_by_id.items()
        if not cache_row_is_compatible(cache.get(ticket_id), ticket)
    ]
    if missing_ids:
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    build_top50_cache_row,
                    tickets_by_id[ticket_id],
                    index_cache_dirs=index_cache_dirs,
                    compute_tfidf_top50=True,
                ): ticket_id
                for ticket_id in missing_ids
            }
            for future in as_completed(futures):
                ticket_id = futures[future]
                cache[ticket_id] = future.result()
                completed += 1
                print(
                    f"[e5_tfidf_top50] computed {completed}/{len(missing_ids)} "
                    f"{ticket_id}",
                    flush=True,
                )
                if completed % checkpoint_every == 0:
                    write_jsonl(
                        cache_path,
                        (
                            row
                            for current_id, row in cache.items()
                            if current_id in tickets_by_id
                        ),
                    )
        write_jsonl(
            cache_path,
            (
                row
                for ticket_id, row in cache.items()
                if ticket_id in tickets_by_id
            ),
        )
    elif not cache_path.is_file():
        write_jsonl(cache_path, cache.values())

    invalid = [
        ticket_id
        for ticket_id, ticket in tickets_by_id.items()
        if not cache_row_is_compatible(cache.get(ticket_id), ticket)
    ]
    if invalid:
        raise ValueError(
            "Complete Top-50 cache is missing compatible rows: "
            + ", ".join(invalid[:5])
        )
    return (
        {ticket_id: cache[ticket_id] for ticket_id in tickets_by_id},
        reused_rows,
        len(missing_ids),
    )


def cache_row_is_compatible(
    row: dict[str, Any] | None,
    ticket: dict[str, Any],
) -> bool:
    if not row or not bool(row.get("index_available")):
        return False
    if not bool(row.get("tfidf_top50_computed")):
        return False
    if str(row.get("base_commit") or "") != str(ticket.get("base_commit") or ""):
        return False
    if str(row.get("repo") or "") != str(ticket.get("repo") or ""):
        return False
    return isinstance(row.get("tfidf_top50"), list)


def analyze_top50_by_size(
    tickets: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
    cache: dict[str, dict[str, Any]],
    groups: dict[str, Any],
) -> dict[str, Any]:
    tickets_by_id = index_by_ticket_id(tickets, "tickets")
    gold_by_id = index_by_ticket_id(gold_rows, "gold")
    if set(tickets_by_id) != set(gold_by_id):
        raise ValueError("Ticket and gold IDs must match exactly.")
    if set(cache) != set(gold_by_id):
        raise ValueError("Top-50 cache IDs must match gold IDs exactly.")
    group_by_repository = {
        str(row["repository"]): str(row["size_group"])
        for row in groups.get("repositories") or []
    }
    if set(group_by_repository.values()) != set(GROUP_ORDER):
        raise ValueError("Repository groups must contain small, medium, and large.")

    evaluation_rows = []
    for ticket_id in sorted(gold_by_id):
        gold = gold_by_id[ticket_id]
        cache_row = cache[ticket_id]
        repository = _repository_name(gold) or _repository_name(tickets_by_id[ticket_id])
        if repository not in group_by_repository:
            raise ValueError(f"Repository {repository} is missing from size groups.")
        evaluation_rows.append(
            {
                "ticket_id": ticket_id,
                "repository": repository,
                "size_group": group_by_repository[repository],
                "gold_files": _gold_files(gold),
                "indexed_files": list(cache_row.get("indexed_files") or []),
                "tfidf_top50_files": [
                    str(row.get("file_path") or "")
                    for row in cache_row.get("tfidf_top50") or []
                    if str(row.get("file_path") or "")
                ][:50],
            }
        )

    repository_metrics = []
    for repository in sorted(
        group_by_repository,
        key=lambda value: (GROUP_ORDER.index(group_by_repository[value]), value),
    ):
        summary = summarize_top50(
            row for row in evaluation_rows if row["repository"] == repository
        )
        summary.update(
            {
                "repository": repository,
                "size_group": group_by_repository[repository],
                "size_group_zh": GROUP_LABELS_ZH[group_by_repository[repository]],
            }
        )
        repository_metrics.append(summary)

    group_metrics = []
    for group_label in GROUP_ORDER:
        summary = summarize_top50(
            row for row in evaluation_rows if row["size_group"] == group_label
        )
        repositories = [
            row for row in repository_metrics if row["size_group"] == group_label
        ]
        summary.update(
            {
                "size_group": group_label,
                "size_group_zh": GROUP_LABELS_ZH[group_label],
                "repository_count": len(repositories),
                "repositories": [row["repository"] for row in repositories],
                "macro_repository_metrics": {
                    metric: statistics.fmean(float(row[metric]) for row in repositories)
                    for metric in (
                        "index_hit",
                        "index_recall",
                        "hit_at_50",
                        "recall_at_50",
                        "retrieval_recall_gap",
                        "mrr_at_50",
                    )
                },
            }
        )
        group_metrics.append(summary)

    return {
        "analysis_scope": "Raw TF-IDF file-level Top-50 coverage by E5 repository-size group",
        "method": {
            "embedding_backend": "tfidf",
            "ranking_level": "best TF-IDF chunk per file",
            "candidate_file_k": 50,
            "file_aggregation": True,
            "symbol_expansion": False,
            "api_implementation_expansion": False,
            "import_graph": False,
            "call_graph": False,
            "sbert_rerank": False,
        },
        "data_policy": {
            "split": "Validation only",
            "holdout_used": False,
            "group_assignment_uses_gold": False,
            "ranking_uses_gold": False,
            "gold_usage": "Gold is used only after TF-IDF ranking to calculate metrics.",
        },
        "definitions": {
            "hit_at_50": "Fraction of tickets with at least one gold file in raw TF-IDF Top-50.",
            "recall_at_50": "Mean fraction of all gold files recovered in raw TF-IDF Top-50.",
            "index_recall": "Mean fraction of gold files that exist in the Code Index.",
            "mrr_at_50": "Mean reciprocal rank of the first gold file in raw TF-IDF Top-50.",
        },
        "overall": summarize_top50(evaluation_rows),
        "groups": group_metrics,
        "repositories": repository_metrics,
    }


def summarize_top50(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    row_list = list(rows)
    if not row_list:
        return empty_summary()
    index_hits: list[float] = []
    index_recalls: list[float] = []
    hits: list[float] = []
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    full_recall_rows = 0
    partial_recall_rows = 0
    miss_rows = 0
    top50_counts: list[int] = []
    for row in row_list:
        gold_files = list(row.get("gold_files") or [])
        indexed_files = list(row.get("indexed_files") or [])
        top50_files = list(row.get("tfidf_top50_files") or [])[:50]
        if not gold_files:
            raise ValueError(f"Ticket {row.get('ticket_id', 'unknown')} has no gold files.")
        indexed_gold = matching_count(gold_files, indexed_files)
        recovered_gold = matching_count(gold_files, top50_files)
        index_hits.append(float(indexed_gold > 0))
        index_recalls.append(indexed_gold / len(gold_files))
        hits.append(float(recovered_gold > 0))
        recalls.append(recovered_gold / len(gold_files))
        first_rank = first_matching_rank(gold_files, top50_files)
        reciprocal_ranks.append(0.0 if first_rank is None else 1.0 / first_rank)
        top50_counts.append(len(top50_files))
        if recovered_gold == len(gold_files):
            full_recall_rows += 1
        elif recovered_gold:
            partial_recall_rows += 1
        else:
            miss_rows += 1
    return {
        "tickets": len(row_list),
        "index_hit": statistics.fmean(index_hits),
        "index_recall": statistics.fmean(index_recalls),
        "hit_at_50": statistics.fmean(hits),
        "recall_at_50": statistics.fmean(recalls),
        "retrieval_recall_gap": (
            statistics.fmean(index_recalls) - statistics.fmean(recalls)
        ),
        "mrr_at_50": statistics.fmean(reciprocal_ranks),
        "full_recall_rows": full_recall_rows,
        "partial_recall_rows": partial_recall_rows,
        "miss_rows": miss_rows,
        "top50_candidate_count": numeric_summary(top50_counts),
    }


def empty_summary() -> dict[str, Any]:
    return {
        "tickets": 0,
        "index_hit": 0.0,
        "index_recall": 0.0,
        "hit_at_50": 0.0,
        "recall_at_50": 0.0,
        "retrieval_recall_gap": 0.0,
        "mrr_at_50": 0.0,
        "full_recall_rows": 0,
        "partial_recall_rows": 0,
        "miss_rows": 0,
        "top50_candidate_count": numeric_summary([]),
    }


def matching_count(gold_files: list[str], candidates: list[str]) -> int:
    return sum(
        any(_file_matches(candidate, gold_file) for candidate in candidates)
        for gold_file in gold_files
    )


def first_matching_rank(gold_files: list[str], candidates: list[str]) -> int | None:
    return next(
        (
            rank
            for rank, candidate in enumerate(candidates, start=1)
            if any(_file_matches(candidate, gold_file) for gold_file in gold_files)
        ),
        None,
    )


def numeric_summary(values: Iterable[int | float]) -> dict[str, float]:
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
    overall = result["overall"]
    execution = result.get("execution") or {}
    lines = [
        "# E5：TF-IDF Top-50候選涵蓋率分組結果",
        "",
        "## 一句話結論",
        "",
        (
            "完整500筆Validation的純TF-IDF Top-50候選已建立。"
            "本結果用來判斷固定50個候選是否較容易在大型Repository遺漏正確檔案，"
            "沒有使用Holdout。"
        ),
        "",
        "## 評估方法",
        "",
        "- 使用Ticket與base commit修正前Code Index進行純TF-IDF檔案排序。",
        "- 同一檔案只保留TF-IDF分數最高的代表程式碼區塊，再取前50個檔案。",
        "- 不使用SBERT、Symbol/API擴充、Import Graph或Call Graph。",
        "- Repository大小分組沿用上一輪固定結果，不使用Gold重新分組。",
        "- Gold只在Top-50產生後計算Hit@50、Recall@50與MRR@50。",
        "",
        "## 三組正式診斷結果",
        "",
        "| 分組 | Repository數 | Ticket數 | Index Recall | Hit@50 | Ticket加權Recall@50 | Index→Top-50遺失 | Repository等權Recall@50 | MRR@50 | 完整／部分／未命中 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["groups"]:
        lines.append(
            "| {group} | {repos} | {tickets} | {index_recall:.2%} | {hit:.2%} | {recall:.2%} | {gap:.2%} | {macro_recall:.2%} | {mrr:.4f} | {full}／{partial}／{miss} |".format(
                group=row["size_group_zh"],
                repos=row["repository_count"],
                tickets=row["tickets"],
                index_recall=row["index_recall"],
                hit=row["hit_at_50"],
                recall=row["recall_at_50"],
                gap=row["retrieval_recall_gap"],
                macro_recall=row["macro_repository_metrics"]["recall_at_50"],
                mrr=row["mrr_at_50"],
                full=row["full_recall_rows"],
                partial=row["partial_recall_rows"],
                miss=row["miss_rows"],
            )
        )
    lines.extend(
        [
            "",
            "整體結果：Index Recall {index_recall:.2%}、Hit@50 {hit:.2%}、Recall@50 {recall:.2%}、Index到Top-50遺失 {gap:.2%}、MRR@50 {mrr:.4f}。".format(
                index_recall=overall["index_recall"],
                hit=overall["hit_at_50"],
                recall=overall["recall_at_50"],
                gap=overall["retrieval_recall_gap"],
                mrr=overall["mrr_at_50"],
            ),
            "",
            "## 各Repository結果",
            "",
            "| 分組 | Repository | Ticket數 | Index Recall | Hit@50 | Recall@50 | MRR@50 |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in result["repositories"]:
        lines.append(
            "| {group} | {repo} | {tickets} | {index_recall:.2%} | {hit:.2%} | {recall:.2%} | {mrr:.4f} |".format(
                group=row["size_group_zh"],
                repo=row["repository"],
                tickets=row["tickets"],
                index_recall=row["index_recall"],
                hit=row["hit_at_50"],
                recall=row["recall_at_50"],
                mrr=row["mrr_at_50"],
            )
        )
    lines.extend(
        [
            "",
            "## 判讀方式",
            "",
            (
                "Index Recall代表修正前Code Index理論上能找回多少Gold檔案；"
                "Recall@50與Index Recall之間的差距，代表檔案存在但沒有進入純TF-IDF前50名。"
            ),
            "",
            (
                "本結果只診斷純TF-IDF候選池，不等同完整E3-C模型。"
                "診斷結果支持對中型與大型Repository正式執行候選池75與100。"
            ),
            "",
            "## 下一步實驗設定",
            "",
            "1. 小型Repository維持候選池50，避免增加沒有必要的計算。",
            "2. 中型Repository比較候選池50、75與100。",
            "3. 大型Repository比較候選池50、75與100。",
            "4. 三種設定的最終輸出皆固定Top-20，並以Recall@20與執行時間判定。",
            "",
            "## 執行完整性",
            "",
            f"- 完整快取：{execution.get('cache_rows_total', 0)}筆。",
            f"- 重用既有快取：{execution.get('cache_rows_reused', 0)}筆。",
            f"- 本輪新計算：{execution.get('cache_rows_computed', 0)}筆。",
            f"- 執行時間：{execution.get('wall_seconds', 0):.3f}秒。",
            "- Holdout使用：否。",
            "",
        ]
    )
    return "\n".join(lines)


def index_by_ticket_id(
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
