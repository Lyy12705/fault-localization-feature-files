#!/usr/bin/env python3
"""Audit Stage-3 misses with no resolved edge in the candidate-pool call graph."""
from __future__ import annotations

import argparse
import ast
import csv
import json
import subprocess
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


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
    _reconstruct_file_source,
    build_call_graph,
    build_symbol_candidate_pool,
    load_code_index,
)


DEFAULT_CONFIG = ROOT / "configs/fault_localization/stage3_call_neighborhood_v1.json"
DEFAULT_DETAILS = (
    ROOT
    / "reports/fault_localization/stage3_call_neighborhood_dev_v1"
    / "call_reachability_details.csv"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--reachability-details", default=str(DEFAULT_DETAILS))
    parser.add_argument("--repository-cache", default=str(ROOT / "data/repositories"))
    return parser


def classify_no_edge_case(
    *,
    full_graph_peers: set[tuple[str, str]],
    peers_in_candidate_pool: set[tuple[str, str]],
    target_file: str,
    reconstructed_parse_ok: bool,
    reconstructed_target_found: bool,
    incoming_unresolved_calls: list[str],
    symbol_kind: str,
    imported_calls: list[str],
    dynamic_calls: list[str],
    direct_calls: list[str],
) -> tuple[str, str]:
    """Choose one evidence-backed primary cause and an explicit confidence."""

    if full_graph_peers:
        if peers_in_candidate_pool:
            if any(path != target_file for path, _ in peers_in_candidate_pool):
                return "import_resolution", "high"
            return "source_reconstruction", "high"
        return "stage2_pool_scope", "high"
    if not reconstructed_parse_ok or not reconstructed_target_found:
        return "source_reconstruction", "high"
    if incoming_unresolved_calls:
        if symbol_kind in {"method", "async_method"}:
            return "dynamic_dispatch", "medium"
        return "import_resolution", "medium"
    if imported_calls:
        return "import_resolution", "medium"
    if dynamic_calls:
        return "dynamic_dispatch", "medium"
    if direct_calls:
        return "import_resolution", "low"
    return "no_static_call_evidence", "medium"


def main() -> None:
    args = build_parser().parse_args()
    config_path = Path(args.config).resolve()
    details_path = Path(args.reachability_details).resolve()
    repository_cache = Path(args.repository_cache).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_config(config)
    if config.get("data_scope") != "development-only":
        raise SystemExit("No-edge audit accepts development data only.")

    tickets = {
        _ticket_id(row): row for row in _read_jsonl(_project_path(config["tickets"]))
    }
    stage2 = {
        _ticket_id(row): row
        for row in _read_jsonl(_project_path(config["stage2_predictions"]))
    }
    index_dir = _project_path(config["index_dir"])
    cases = _read_cases(details_path)
    audited: list[dict[str, Any]] = []
    for row in cases:
        ticket_id = row["ticket_id"]
        ticket = tickets[ticket_id]
        file_path = _normalize_path(row["file_path"])
        qualified_name = row["qualified_name"]
        symbol_kind = row["symbol_kind"]
        stage2_paths = {
            _normalize_path(str(item["file_path"]))
            for item in _stage2_files(stage2[ticket_id])
        }
        index = load_code_index(_index_path(ticket, index_dir))
        pool = build_symbol_candidate_pool(index.chunks, stage2_paths)
        candidate_nodes = {
            (_normalize_path(chunk.file_path), chunk.symbol_qualified_name)
            for chunk in pool
        }
        pool_file_chunks = [
            chunk for chunk in pool if _normalize_path(chunk.file_path) == file_path
        ]
        reconstructed = _reconstruct_file_source(pool_file_chunks)
        reconstructed_tree, reconstructed_error = _parse(reconstructed)
        reconstructed_target = (
            _find_definition(reconstructed_tree, qualified_name, symbol_kind)
            if reconstructed_tree is not None
            else None
        )

        full_graph = index.call_graph or build_call_graph(
            index.chunks, index.symbol_definitions
        )
        peers = _full_graph_peers(
            full_graph.outgoing,
            file_path=file_path,
            qualified_name=qualified_name,
        )
        peers_in_pool = peers & candidate_nodes
        incoming_unresolved = _incoming_unresolved_calls(
            full_graph.unresolved,
            stage2_paths=stage2_paths,
            target_leaf=qualified_name.rsplit(".", 1)[-1],
        )

        repo_name = str(ticket.get("repo") or ticket.get("repository") or "")
        repo_path = repository_cache / repo_name.replace("/", "__")
        source, source_error = _git_source(
            repo_path, str(ticket.get("base_commit") or ""), file_path
        )
        actual_tree, actual_parse_error = _parse(source)
        actual_target = (
            _find_definition(actual_tree, qualified_name, symbol_kind)
            if actual_tree is not None
            else None
        )
        calls = _calls_inside(actual_target) if actual_target is not None else []
        imported_roots = _imported_roots(actual_tree) if actual_tree is not None else set()
        imported_calls, dynamic_calls, direct_calls = _classify_calls(calls, imported_roots)
        cause, confidence = classify_no_edge_case(
            full_graph_peers=peers,
            peers_in_candidate_pool=peers_in_pool,
            target_file=file_path,
            reconstructed_parse_ok=reconstructed_tree is not None,
            reconstructed_target_found=reconstructed_target is not None,
            incoming_unresolved_calls=incoming_unresolved,
            symbol_kind=symbol_kind,
            imported_calls=imported_calls,
            dynamic_calls=dynamic_calls,
            direct_calls=direct_calls,
        )
        audited.append(
            {
                "ticket_id": ticket_id,
                "file_path": file_path,
                "symbol_kind": symbol_kind,
                "qualified_name": qualified_name,
                "primary_cause": cause,
                "confidence": confidence,
                "reconstructed_parse_ok": reconstructed_tree is not None,
                "reconstructed_target_found": reconstructed_target is not None,
                "reconstruction_error": reconstructed_error,
                "base_source_loaded": bool(source),
                "base_parse_ok": actual_tree is not None,
                "base_target_found": actual_target is not None,
                "base_source_error": source_error or actual_parse_error,
                "full_graph_peer_count": len(peers),
                "full_graph_peers": " | ".join(_format_nodes(peers)),
                "full_graph_peers_in_candidate_pool": len(peers_in_pool),
                "candidate_pool_peers": " | ".join(_format_nodes(peers_in_pool)),
                "incoming_unresolved_calls": " | ".join(incoming_unresolved),
                "target_imported_calls": " | ".join(imported_calls),
                "target_dynamic_calls": " | ".join(dynamic_calls),
                "target_direct_calls": " | ".join(direct_calls),
            }
        )

    counts = Counter(row["primary_cause"] for row in audited)
    confidence = Counter(row["confidence"] for row in audited)
    report = {
        "schema_version": "stage3-no-edge-audit-v1",
        "data_scope": "development-only",
        "audited_cases": len(audited),
        "cause_counts": dict(sorted(counts.items())),
        "confidence_counts": dict(sorted(confidence.items())),
        "base_source_failures": sum(not row["base_source_loaded"] for row in audited),
        "base_target_missing": sum(not row["base_target_found"] for row in audited),
        "reconstructed_parse_failures": sum(not row["reconstructed_parse_ok"] for row in audited),
        "reconstructed_target_missing": sum(not row["reconstructed_target_found"] for row in audited),
        "full_graph_incident_edge_cases": sum(bool(row["full_graph_peer_count"]) for row in audited),
        "full_graph_peer_in_candidate_pool_cases": sum(
            bool(row["full_graph_peers_in_candidate_pool"]) for row in audited
        ),
        "methodology": (
            "Cross-check candidate-pool reconstruction, cached full-index call graph, "
            "and base-commit AST. Medium/low classifications are evidence-guided audit "
            "labels rather than proof of runtime dispatch."
        ),
    }
    output_dir = _project_path(config["output_dir"])
    _write_csv(output_dir / "no_edge_case_audit.csv", audited)
    (output_dir / "no_edge_case_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "NO_EDGE_AUDIT_ZH.md").write_text(
        _markdown(report, audited), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)


def _read_cases(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if row.get("reachability_class") == "no_resolved_incident_edge"
        ]


def _parse(source: str) -> tuple[ast.Module | None, str]:
    if not source:
        return None, "empty_source"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return ast.parse(source), ""
    except (SyntaxError, RecursionError, ValueError) as error:
        return None, f"{type(error).__name__}: {error}"


def _find_definition(
    tree: ast.Module, qualified_name: str, symbol_kind: str
) -> ast.AST | None:
    wanted = qualified_name.split(".")
    found: ast.AST | None = None

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def _visit(self, node: ast.AST, name: str) -> None:
            nonlocal found
            self.stack.append(name)
            kind_ok = (
                isinstance(node, ast.ClassDef)
                if symbol_kind == "class"
                else isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            if kind_ok and self.stack == wanted:
                found = node
            self.generic_visit(node)
            self.stack.pop()

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self._visit(node, node.name)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit(node, node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit(node, node.name)

    Visitor().visit(tree)
    return found


def _calls_inside(node: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, item: ast.Call) -> None:
            calls.append(item)
            self.generic_visit(item)

        def visit_FunctionDef(self, item: ast.FunctionDef) -> None:
            if item is node:
                for child in item.body:
                    self.visit(child)

        def visit_AsyncFunctionDef(self, item: ast.AsyncFunctionDef) -> None:
            if item is node:
                for child in item.body:
                    self.visit(child)

        def visit_ClassDef(self, item: ast.ClassDef) -> None:
            if item is node:
                for child in item.body:
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        self.visit(child)

    Visitor().visit(node)
    return calls


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
    return roots


def _call_parts(node: ast.expr) -> list[str]:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return list(reversed(parts))


def _classify_calls(
    calls: Iterable[ast.Call], imported_roots: set[str]
) -> tuple[list[str], list[str], list[str]]:
    imported: list[str] = []
    dynamic: list[str] = []
    direct: list[str] = []
    for call in calls:
        parts = _call_parts(call.func)
        if not parts:
            continue
        name = ".".join(parts)
        if parts[0] in imported_roots:
            imported.append(name)
        elif len(parts) > 1 and parts[0] not in {"self", "cls", "super"}:
            dynamic.append(name)
        elif len(parts) == 1:
            direct.append(name)
    return list(dict.fromkeys(imported)), list(dict.fromkeys(dynamic)), list(dict.fromkeys(direct))


def _full_graph_peers(
    outgoing: dict[str, list[dict[str, Any]]], *, file_path: str, qualified_name: str
) -> set[tuple[str, str]]:
    target = (file_path, qualified_name)
    peers: set[tuple[str, str]] = set()
    for edges in outgoing.values():
        for edge in edges:
            caller = (_normalize_path(edge["caller_file"]), str(edge["caller_symbol"]))
            callee = (_normalize_path(edge["target_file"]), str(edge["target_symbol"]))
            if caller == target:
                peers.add(callee)
            if callee == target:
                peers.add(caller)
    return peers


def _incoming_unresolved_calls(
    unresolved: dict[str, list[str]], *, stage2_paths: set[str], target_leaf: str
) -> list[str]:
    matches: list[str] = []
    for path, calls in unresolved.items():
        if _normalize_path(path) not in stage2_paths:
            continue
        for call in calls:
            if str(call).rsplit(".", 1)[-1] == target_leaf:
                matches.append(f"{_normalize_path(path)}::{call}")
    return sorted(set(matches))


def _git_source(repo: Path, commit: str, file_path: str) -> tuple[str, str]:
    if not (repo / ".git").exists():
        return "", "repository_cache_missing"
    completed = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{file_path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if completed.returncode:
        return "", completed.stderr.strip()[:300]
    return completed.stdout, ""


def _format_nodes(nodes: set[tuple[str, str]]) -> list[str]:
    return [f"{path}::{name}" for path, name in sorted(nodes)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# WP3 無呼叫邊案例審核",
        "",
        f"- 審核案例：{report['audited_cases']}",
        f"- Base source 載入失敗：{report['base_source_failures']}",
        f"- Base target 找不到：{report['base_target_missing']}",
        f"- 完整索引圖已有 incident edge：{report['full_graph_incident_edge_cases']}",
        f"- 完整索引圖的相鄰 symbol 也在候選池：{report['full_graph_peer_in_candidate_pool_cases']}",
        "",
        "## 主因統計",
        "",
        "| 主因 | 數量 |",
        "|---|---:|",
    ]
    for cause, count in report["cause_counts"].items():
        lines.append(f"| `{cause}` | {count} |")
    lines.extend(
        [
            "",
            "`source_reconstruction` 表示同檔完整索引邊在 symbol-only pool 重建時消失；`import_resolution` 表示跨檔完整索引邊在重建時消失。兩者都不代表 base source 或目標定義缺失。",
        ]
    )
    lines.extend(
        [
            "",
            "## 逐筆分類",
            "",
            "| Ticket | Symbol | 主因 | 信心 | 關鍵證據 |",
            "|---|---|---|---|---|",
        ]
    )
    for row in rows:
        evidence = (
            row["full_graph_peers"]
            or row["incoming_unresolved_calls"]
            or row["target_imported_calls"]
            or row["target_dynamic_calls"]
            or row["target_direct_calls"]
            or "no call evidence"
        )
        evidence = str(evidence).replace(" | ", "<br>").replace("|", "\\|")
        lines.append(
            f"| `{row['ticket_id']}` | `{row['qualified_name']}` | "
            f"`{row['primary_cause']}` | {row['confidence']} | {evidence[:120]} |"
        )
    lines.extend(
        [
            "",
            "分類以 candidate reconstruction、完整 index call graph 與 base-commit AST 交叉檢查。medium／low 表示有結構證據但不能證明執行時派送目標。",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
