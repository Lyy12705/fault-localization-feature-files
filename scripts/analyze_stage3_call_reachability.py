#!/usr/bin/env python3
"""Measure call-graph reachability for the selected baseline's Top-30 misses."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for import_path in (str(SRC), str(ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from scripts.run_stage3_deterministic_g2 import (
    _index_path,
    _project_path,
    _read_jsonl,
    _stage2_files,
    _ticket_id,
    _validate_config,
)
from utils.fault_localization import (
    _normalize_path,
    build_call_graph,
    build_symbol_candidate_pool,
    load_code_index,
    rank_symbol_candidates,
)
from utils.symbol_evaluation import SymbolEvaluationItemV1, match_symbol


DEFAULT_CONFIG = ROOT / "configs/fault_localization/stage3_call_neighborhood_v1.json"
DEFAULT_BASELINE = (
    ROOT
    / "reports/fault_localization/stage3_deterministic_g2_dev_v1"
    / "oracle_symbol_classification.csv"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--baseline-classification", default=str(DEFAULT_BASELINE))
    parser.add_argument("--variant", default="b1_call_neighborhood_v1")
    return parser


def classify_reachability(
    *,
    prefix_neighbors: set[tuple[str, str]],
    pool_neighbors: set[tuple[str, str]],
) -> str:
    """Classify evidence without claiming an absent resolved edge is a true non-call."""

    if prefix_neighbors:
        return "prefix_one_hop_reachable"
    if pool_neighbors:
        return "connected_outside_prefix"
    return "no_resolved_incident_edge"


def main() -> None:
    args = build_parser().parse_args()
    config_path = Path(args.config).resolve()
    baseline_path = Path(args.baseline_classification).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_config(config)
    if config.get("data_scope") != "development-only":
        raise SystemExit("Call reachability analysis accepts development data only.")

    tickets_path = _project_path(config["tickets"])
    stage2_path = _project_path(config["stage2_predictions"])
    index_dir = _project_path(config["index_dir"])
    output_dir = _project_path(config["output_dir"])
    prediction_path = output_dir / f"{args.variant}_predictions.jsonl"
    for path in (tickets_path, stage2_path, index_dir, baseline_path, prediction_path):
        if not path.exists():
            raise SystemExit(f"Required input does not exist: {path}")

    tickets = {_ticket_id(row): row for row in _read_jsonl(tickets_path)}
    stage2 = {_ticket_id(row): row for row in _read_jsonl(stage2_path)}
    predictions = {_ticket_id(row): row for row in _read_jsonl(prediction_path)}
    misses = _read_baseline_misses(baseline_path)
    details: list[dict[str, Any]] = []

    for ticket_id in sorted(misses):
        ticket = tickets[ticket_id]
        stage2_rows = _stage2_files(stage2[ticket_id])
        paths = {str(row["file_path"]) for row in stage2_rows}
        scores = {
            str(row["file_path"]): float(row.get("score") or row.get("retrieval_score") or 0.0)
            for row in stage2_rows
        }
        index = load_code_index(_index_path(ticket, index_dir))
        pool = build_symbol_candidate_pool(index.chunks, paths)
        ranking = rank_symbol_candidates(
            ticket,
            pool,
            stage2_file_scores=scores,
            mode="b1-structured",
            top_k=max(1, len(pool)),
            per_file_quota=0,
            selection_mode="global",
        )
        prefix = _coverage_prefix(ranking, scores, top_k=int(config["candidate_k"]))
        graph = build_call_graph(candidate.chunk for candidate in ranking)
        adjacency = _adjacency(graph.outgoing)
        prefix_nodes = {
            (_normalize_path(candidate.chunk.file_path), candidate.chunk.symbol_qualified_name)
            for candidate in prefix
            if candidate.chunk.symbol_kind != "module"
        }
        selected_symbols = [
            SymbolEvaluationItemV1.from_mapping(row)
            for row in predictions[ticket_id].get("stage3_candidate_symbols", [])
        ]
        for miss in misses[ticket_id]:
            gold = SymbolEvaluationItemV1(
                file_path=miss["file_path"],
                qualified_name=miss["qualified_name"],
                symbol_kind=miss["symbol_kind"],
            )
            node = (gold.file_path, gold.qualified_name)
            pool_neighbors = adjacency.get(node, set())
            prefix_neighbors = pool_neighbors & prefix_nodes
            selected = any(match_symbol(candidate, gold).exact for candidate in selected_symbols)
            details.append(
                {
                    "ticket_id": ticket_id,
                    "file_path": gold.file_path,
                    "symbol_kind": gold.symbol_kind,
                    "qualified_name": gold.qualified_name,
                    "baseline_pool_rank": miss.get("pool_rank", ""),
                    "prefix_size": len(prefix),
                    "resolved_degree": len(pool_neighbors),
                    "prefix_neighbor_count": len(prefix_neighbors),
                    "prefix_neighbors": " | ".join(_format_nodes(prefix_neighbors)),
                    "pool_neighbors": " | ".join(_format_nodes(pool_neighbors)),
                    "call_variant_top30_exact": selected,
                    "reachability_class": classify_reachability(
                        prefix_neighbors=prefix_neighbors,
                        pool_neighbors=pool_neighbors,
                    ),
                }
            )

    counts = Counter(row["reachability_class"] for row in details)
    kind_counts = {
        kind: dict(Counter(row["reachability_class"] for row in details if row["symbol_kind"] == kind))
        for kind in sorted({row["symbol_kind"] for row in details})
    }
    report = {
        "schema_version": "stage3-call-reachability-v1",
        "data_scope": "development-only",
        "baseline": "b1_coverage_aware_v1",
        "experiment_variant": args.variant,
        "baseline_ranking_misses": len(details),
        "classification_counts": dict(sorted(counts.items())),
        "classification_by_symbol_kind": kind_counts,
        "prefix_one_hop_reachable": sum(bool(row["prefix_neighbor_count"]) for row in details),
        "pool_graph_connected": sum(bool(row["resolved_degree"]) for row in details),
        "experiment_recovered": sum(bool(row["call_variant_top30_exact"]) for row in details),
        "prefix_reachable_recovered": sum(
            bool(row["prefix_neighbor_count"]) and bool(row["call_variant_top30_exact"])
            for row in details
        ),
        "prefix_reachable_not_selected": sum(
            bool(row["prefix_neighbor_count"]) and not bool(row["call_variant_top30_exact"])
            for row in details
        ),
        "recovered_without_prefix_edge": sum(
            not bool(row["prefix_neighbor_count"]) and bool(row["call_variant_top30_exact"])
            for row in details
        ),
        "interpretation": (
            "No resolved edge is evidence about this static graph only; it does not prove "
            "that no runtime call relationship exists."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "call_reachability_analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(output_dir / "call_reachability_details.csv", details)
    (output_dir / "CALL_REACHABILITY_REPORT_ZH.md").write_text(
        _markdown(report), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)


def _coverage_prefix(candidates, stage2_scores: dict[str, float], *, top_k: int):
    file_order = sorted(
        {_normalize_path(candidate.chunk.file_path) for candidate in candidates},
        key=lambda path: (-stage2_scores.get(path, 0.0), path),
    )
    module_files = {
        _normalize_path(candidate.chunk.file_path)
        for candidate in candidates
        if candidate.chunk.symbol_kind == "module"
    }
    reserved_count = min(top_k, sum(path in module_files for path in file_order))
    expansion_slots = min(5, max(0, top_k - reserved_count - 1))
    return candidates[: max(1, top_k - reserved_count - expansion_slots)]


def _adjacency(outgoing: dict[str, list[dict[str, Any]]]):
    result: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for edges in outgoing.values():
        for edge in edges:
            caller = (_normalize_path(edge["caller_file"]), str(edge["caller_symbol"]))
            callee = (_normalize_path(edge["target_file"]), str(edge["target_symbol"]))
            result.setdefault(caller, set()).add(callee)
            result.setdefault(callee, set()).add(caller)
    return result


def _read_baseline_misses(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("conditional_eligible") == "True" and row.get("classification") == "top30_ranking_miss":
                result.setdefault(str(row["ticket_id"]), []).append(row)
    return result


def _format_nodes(nodes: set[tuple[str, str]]) -> list[str]:
    return [f"{path}::{name}" for path, name in sorted(nodes)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Expected at least one baseline ranking miss.")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _markdown(report: dict[str, Any]) -> str:
    counts = report["classification_counts"]
    return "\n".join(
        [
            "# WP3 剩餘 Ranking Misses 呼叫圖可達性",
            "",
            f"- Baseline ranking misses：{report['baseline_ranking_misses']}",
            f"- Prefix 一跳可達：{report['prefix_one_hop_reachable']}",
            f"- 池內呼叫圖有任一已解析相鄰節點：{report['pool_graph_connected']}",
            f"- call-neighborhood-v1 實際找回：{report['experiment_recovered']}",
            "",
            "## 分類",
            "",
            "| 類別 | 數量 | 解讀 |",
            "|---|---:|---|",
            f"| Prefix 一跳可達 | {counts.get('prefix_one_hop_reachable', 0)} | 其中 {report['prefix_reachable_recovered']} 個找回、{report['prefix_reachable_not_selected']} 個受名額或每-anchor競爭限制 |",
            f"| 只連到 prefix 外 | {counts.get('connected_outside_prefix', 0)} | anchor 覆蓋不足 |",
            f"| 無已解析 incident edge | {counts.get('no_resolved_incident_edge', 0)} | 靜態圖沒有可用證據 |",
            "",
            f"call variant 共找回 {report['experiment_recovered']} 個；其中 {report['recovered_without_prefix_edge']} 個沒有 prefix edge，是選取／回填改變造成，不能歸因於呼叫擴展。",
            "",
            "「無已解析 edge」不代表執行時一定沒有呼叫關係；候選 source 不完整、動態派送或 import 解析限制都可能造成缺邊。",
            "",
        ]
    )


if __name__ == "__main__":
    main()
