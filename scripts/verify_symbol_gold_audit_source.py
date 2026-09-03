#!/usr/bin/env python3
"""Independently compare Symbol Gold audit rows with patch and base source."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


CALLABLE_KINDS = frozenset({"function", "async_function", "method", "async_method"})
REPORT_FIELDS = (
    "sample_index",
    "gold_id",
    "ticket_id",
    "file_path",
    "evidence_lines",
    "expected_qualified_name",
    "actual_qualified_name",
    "expected_symbol_kind",
    "actual_symbol_kind",
    "file_correct",
    "qualified_name_correct",
    "symbol_kind_correct",
    "source_range",
    "verification_status",
    "verification_note",
)


@dataclass(frozen=True, slots=True)
class IndependentSymbol:
    qualified_name: str
    symbol_kind: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independently verify audit mappings against developer patches and Git objects."
    )
    parser.add_argument("--audit-csv", required=True)
    parser.add_argument("--tickets", required=True)
    parser.add_argument("--repo-cache-dir", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    audit_rows = read_csv(Path(args.audit_csv).resolve())
    tickets = index_tickets(read_jsonl(Path(args.tickets).resolve()))
    results = verify_rows(
        audit_rows,
        tickets=tickets,
        repo_cache_dir=Path(args.repo_cache_dir).resolve(),
    )
    write_report_csv(Path(args.output_csv).resolve(), results)
    write_evidence_markdown(Path(args.output_md).resolve(), results)
    summary = {
        "row_count": len(results),
        "exact_count": sum(row["verification_status"] == "exact" for row in results),
        "mismatch_count": sum(row["verification_status"] == "mismatch" for row in results),
        "error_count": sum(row["verification_status"] == "error" for row in results),
        "output_csv": str(Path(args.output_csv).resolve()),
        "output_md": str(Path(args.output_md).resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def verify_rows(
    audit_rows: Sequence[Mapping[str, str]],
    *,
    tickets: Mapping[str, Mapping[str, Any]],
    repo_cache_dir: Path,
) -> list[dict[str, Any]]:
    source_cache: dict[tuple[str, str, str], str] = {}
    symbol_cache: dict[tuple[str, str, str], tuple[IndependentSymbol, ...]] = {}
    results: list[dict[str, Any]] = []
    for row in audit_rows:
        ticket_id = row.get("ticket_id", "")
        ticket = tickets.get(ticket_id)
        common: dict[str, Any] = {
            "sample_index": row.get("sample_index", ""),
            "gold_id": row.get("gold_id", ""),
            "ticket_id": ticket_id,
            "file_path": row.get("file_path", ""),
            "expected_qualified_name": row.get("qualified_name", ""),
            "expected_symbol_kind": row.get("symbol_kind", ""),
        }
        if ticket is None:
            results.append(_error_result(common, "ticket is absent from source JSONL"))
            continue
        patch = str(ticket.get("patch") or "")
        patch_hash = f"sha256:{hashlib.sha256(patch.encode('utf-8')).hexdigest()}"
        hunk_text = find_hunk_text(
            patch,
            old_file_path=row.get("old_file_path", ""),
            hunk_index=int(row.get("hunk_index", "0")),
        )
        file_correct = bool(hunk_text) and all(
            (
                row.get("file_path", "") == row.get("old_file_path", ""),
                row.get("repo", "") == str(ticket.get("repo") or ""),
                row.get("base_commit", "") == str(ticket.get("base_commit") or ""),
                row.get("patch_sha256", "") == patch_hash,
            )
        )
        cache_key = (
            row.get("repo", ""),
            row.get("base_commit", ""),
            row.get("file_path", ""),
        )
        try:
            if cache_key not in source_cache:
                source_cache[cache_key] = git_show_source(
                    repo_cache_dir / safe_name(cache_key[0]),
                    base_commit=cache_key[1],
                    file_path=cache_key[2],
                )
                symbol_cache[cache_key] = extract_independent_symbols(source_cache[cache_key])
            source = source_cache[cache_key]
            symbols = symbol_cache[cache_key]
        except (OSError, RuntimeError, SyntaxError, UnicodeError) as exc:
            result = _error_result(common, f"{type(exc).__name__}: {exc}")
            result["file_correct"] = file_correct
            result["patch_hunk"] = hunk_text
            results.append(result)
            continue

        evidence = evidence_lines(row)
        actual_symbols = [innermost_symbol(symbols, line) for line in evidence]
        unique_actual = {
            (symbol.qualified_name, symbol.symbol_kind, symbol.start_line, symbol.end_line)
            for symbol in actual_symbols
            if symbol is not None
        }
        has_module_evidence = any(symbol is None for symbol in actual_symbols)
        if not unique_actual and has_module_evidence:
            actual_name = "<module>"
            actual_kind = "module"
            source_range = "module"
        elif len(unique_actual) == 1 and not has_module_evidence:
            actual_name, actual_kind, start_line, end_line = next(iter(unique_actual))
            source_range = f"{start_line}-{end_line}"
        else:
            values = sorted(f"{name}:{kind}:{start}-{end}" for name, kind, start, end in unique_actual)
            if has_module_evidence:
                values.append("<module>:module")
            actual_name = " | ".join(values)
            actual_kind = "ambiguous"
            source_range = "mixed"
        name_correct = actual_name == row.get("qualified_name", "")
        kind_correct = actual_kind == row.get("symbol_kind", "")
        exact = file_correct and name_correct and kind_correct
        results.append(
            {
                **common,
                "evidence_lines": " ".join(map(str, evidence)),
                "actual_qualified_name": actual_name,
                "actual_symbol_kind": actual_kind,
                "file_correct": file_correct,
                "qualified_name_correct": name_correct,
                "symbol_kind_correct": kind_correct,
                "source_range": source_range,
                "verification_status": "exact" if exact else "mismatch",
                "verification_note": (
                    "Independent patch identity and AST scope agree."
                    if exact
                    else "Independent patch identity or AST scope differs."
                ),
                "patch_hunk": hunk_text,
                "source_excerpt": source_excerpt(source, evidence),
            }
        )
    return results


def extract_independent_symbols(source: str) -> tuple[IndependentSymbol, ...]:
    tree = ast.parse(source)
    symbols: list[IndependentSymbol] = []
    stack: list[IndependentSymbol] = []

    class Visitor(ast.NodeVisitor):
        def _add(self, node: ast.AST, *, name: str, kind: str) -> None:
            if stack:
                separator = ".<locals>." if stack[-1].symbol_kind in CALLABLE_KINDS else "."
                qualified_name = f"{stack[-1].qualified_name}{separator}{name}"
            else:
                qualified_name = name
            starts = [(int(node.lineno), int(node.col_offset))]
            starts.extend(
                (int(decorator.lineno), int(decorator.col_offset))
                for decorator in getattr(node, "decorator_list", ())
            )
            start_line, start_column = min(starts)
            symbol = IndependentSymbol(
                qualified_name=qualified_name,
                symbol_kind=kind,
                start_line=start_line,
                start_column=start_column,
                end_line=int(getattr(node, "end_lineno", node.lineno)),
                end_column=int(getattr(node, "end_col_offset", node.col_offset)),
            )
            symbols.append(symbol)
            stack.append(symbol)
            self.generic_visit(node)
            stack.pop()

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self._add(node, name=node.name, kind="class")

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            kind = "method" if stack and stack[-1].symbol_kind == "class" else "function"
            self._add(node, name=node.name, kind=kind)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            kind = "async_method" if stack and stack[-1].symbol_kind == "class" else "async_function"
            self._add(node, name=node.name, kind=kind)

    Visitor().visit(tree)
    return tuple(symbols)


def innermost_symbol(
    symbols: Sequence[IndependentSymbol], line: int
) -> IndependentSymbol | None:
    matches = [symbol for symbol in symbols if symbol.start_line <= line <= symbol.end_line]
    if not matches:
        return None
    return min(
        matches,
        key=lambda symbol: (
            symbol.end_line - symbol.start_line,
            symbol.end_column - symbol.start_column
            if symbol.end_line == symbol.start_line
            else symbol.end_column,
            -symbol.start_column,
        ),
    )


def evidence_lines(row: Mapping[str, str]) -> tuple[int, ...]:
    matched = tuple(int(value) for value in row.get("matched_old_lines", "").split())
    if matched:
        return matched
    anchor = row.get("insertion_anchor_line", "").strip()
    if anchor:
        return (int(anchor),)
    old_start = int(row.get("old_start_line", "0"))
    return (max(1, old_start),)


def find_hunk_text(patch: str, *, old_file_path: str, hunk_index: int) -> str:
    lines = patch.splitlines()
    block_starts = [index for index, line in enumerate(lines) if line.startswith("diff --git ")]
    block_starts.append(len(lines))
    for position in range(len(block_starts) - 1):
        block = lines[block_starts[position] : block_starts[position + 1]]
        try:
            parts = shlex.split(block[0], posix=True)
        except ValueError:
            continue
        if len(parts) != 4:
            continue
        path = parts[2][2:] if parts[2].startswith("a/") else parts[2]
        rename_from = next(
            (line[len("rename from ") :] for line in block if line.startswith("rename from ")),
            "",
        )
        if (rename_from or path) != old_file_path:
            continue
        starts = [index for index, line in enumerate(block) if line.startswith("@@ ")]
        if hunk_index >= len(starts):
            return ""
        end = next((value for value in starts if value > starts[hunk_index]), len(block))
        return "\n".join(block[starts[hunk_index] : end])
    return ""


def git_show_source(repository: Path, *, base_commit: str, file_path: str) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository}",
            "-C",
            str(repository),
            "show",
            f"{base_commit}:{file_path}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout.decode("utf-8")


def source_excerpt(source: str, evidence: Sequence[int], radius: int = 2) -> str:
    lines = source.splitlines()
    start = max(1, min(evidence) - radius)
    end = min(len(lines), max(evidence) + radius)
    return "\n".join(f"{line_number}: {lines[line_number - 1]}" for line_number in range(start, end + 1))


def _error_result(common: Mapping[str, Any], note: str) -> dict[str, Any]:
    return {
        **common,
        "evidence_lines": "",
        "actual_qualified_name": "",
        "actual_symbol_kind": "",
        "file_correct": False,
        "qualified_name_correct": False,
        "symbol_kind_correct": False,
        "source_range": "",
        "verification_status": "error",
        "verification_note": note,
        "patch_hunk": "",
        "source_excerpt": "",
    }


def safe_name(value: str) -> str:
    normalized = value.replace("/", "__").replace("\\", "__").replace(":", "_")
    return "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in normalized
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def index_tickets(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("ticket_id") or row.get("instance_id") or ""): row for row in rows}


def write_report_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=REPORT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field, "") for field in REPORT_FIELDS} for row in rows)
    atomic_write_text(path, buffer.getvalue())


def write_evidence_markdown(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    parts = ["# Stage 3 Symbol Gold audit evidence\n"]
    for row in rows:
        parts.extend(
            [
                f"## Sample {row['sample_index']}: `{row['ticket_id']}`\n",
                f"- Status: **{row['verification_status']}**\n",
                f"- File: `{row['file_path']}` — {row['file_correct']}\n",
                f"- Expected: `{row['expected_qualified_name']}` / `{row['expected_symbol_kind']}`\n",
                f"- Independent AST: `{row['actual_qualified_name']}` / `{row['actual_symbol_kind']}`\n",
                f"- Evidence lines: `{row['evidence_lines']}`; source range: `{row['source_range']}`\n",
                "\n### Patch hunk\n\n```diff\n",
                str(row.get("patch_hunk", "")),
                "\n```\n\n### Base source\n\n```python\n",
                str(row.get("source_excerpt", "")),
                "\n```\n",
            ]
        )
    atomic_write_text(path, "\n".join(parts))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    main()
