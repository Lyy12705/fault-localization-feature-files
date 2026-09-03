#!/usr/bin/env python3
"""Create and validate a deterministic, stratified Symbol Gold audit sample."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_SEED = 20260902
DEFAULT_SAMPLE_SIZE = 50
DEFAULT_MIN_REPOSITORIES = 5
DEFAULT_EXACT_THRESHOLD = 0.95
DEFAULT_STRATUM_MINIMUMS = {
    "nested_symbol": 10,
    "module_level": 5,
    "pure_addition": 5,
    "deletion": 5,
    "multi_file_ticket": 10,
}
AUDIT_METADATA_FIELDS = ("sample_index", "audit_seed", "audit_strata")
REVIEW_FIELDS = (
    "review_status",
    "file_correct",
    "qualified_name_correct",
    "symbol_kind_correct",
    "review_note",
)
REQUIRED_COLUMNS = frozenset(
    {
        "gold_id",
        "ticket_id",
        "repo",
        "base_commit",
        "file_path",
        "mapping_status",
        "mapping_method",
        "symbol_id",
        "qualified_name",
        "symbol_kind",
        "start_line",
        "start_column",
        "end_line",
        "end_column",
        "change_type",
        "hunk_index",
        "old_file_path",
        "new_file_path",
        "old_start_line",
        "old_line_count",
        "new_start_line",
        "new_line_count",
        "matched_old_lines",
        "context_old_lines",
        "insertion_anchor_line",
        "patch_sha256",
        *REVIEW_FIELDS,
    }
)
HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-fA-F]{7,64}")
INTEGER_PATTERN = re.compile(r"\d+")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or validate a fixed-seed Symbol Gold audit sample."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample_parser = subparsers.add_parser(
        "sample", help="Create a deterministic stratified audit CSV."
    )
    sample_parser.add_argument("--input", required=True, help="Full Symbol Gold audit CSV.")
    sample_parser.add_argument("--output", required=True, help="Output audit sample CSV.")
    sample_parser.add_argument("--summary", help="Optional JSON validation summary path.")
    _add_sampling_arguments(sample_parser)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate provenance and completed human review labels."
    )
    validate_parser.add_argument("--input", required=True, help="Audit sample CSV.")
    validate_parser.add_argument("--summary", help="Optional JSON summary path.")
    validate_parser.add_argument(
        "--expected-sample-size", type=int, default=DEFAULT_SAMPLE_SIZE
    )
    validate_parser.add_argument(
        "--min-repositories", type=int, default=DEFAULT_MIN_REPOSITORIES
    )
    validate_parser.add_argument(
        "--exact-threshold", type=float, default=DEFAULT_EXACT_THRESHOLD
    )
    validate_parser.add_argument(
        "--stratum-minimum",
        action="append",
        default=[],
        metavar="NAME=COUNT",
        help="Override a default stratum minimum; may be repeated.",
    )
    return parser


def _add_sampling_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--min-repositories", type=int, default=DEFAULT_MIN_REPOSITORIES)
    parser.add_argument(
        "--stratum-minimum",
        action="append",
        default=[],
        metavar="NAME=COUNT",
        help="Override a default stratum minimum; may be repeated.",
    )


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    input_path = Path(args.input).resolve()
    rows, fieldnames = read_audit_csv(input_path)
    minimums = parse_stratum_minimums(args.stratum_minimum)

    if args.command == "sample":
        sampled = create_stratified_sample(
            rows,
            sample_size=args.sample_size,
            seed=args.seed,
            min_repositories=args.min_repositories,
            stratum_minimums=minimums,
        )
        output_path = Path(args.output).resolve()
        write_audit_csv(output_path, sampled, source_fields=fieldnames)
        summary = validate_audit_sample(
            sampled,
            expected_sample_size=args.sample_size,
            min_repositories=args.min_repositories,
            stratum_minimums=minimums,
        )
        summary.update(
            {
                "command": "sample",
                "seed": args.seed,
                "source": str(input_path),
                "output": str(output_path),
            }
        )
    else:
        summary = validate_audit_sample(
            rows,
            expected_sample_size=args.expected_sample_size,
            min_repositories=args.min_repositories,
            stratum_minimums=minimums,
            exact_threshold=args.exact_threshold,
        )
        summary.update({"command": "validate", "input": str(input_path)})

    if args.summary:
        atomic_write_text(
            Path(args.summary).resolve(),
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def read_audit_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Audit CSV does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Audit CSV has no header.")
        fieldnames = list(reader.fieldnames)
        missing = sorted(REQUIRED_COLUMNS.difference(fieldnames))
        if missing:
            raise ValueError(f"Audit CSV is missing required columns: {', '.join(missing)}.")
        return [dict(row) for row in reader], fieldnames


def parse_stratum_minimums(values: Sequence[str]) -> dict[str, int]:
    minimums = dict(DEFAULT_STRATUM_MINIMUMS)
    for value in values:
        name, separator, raw_count = value.partition("=")
        name = name.strip()
        if not separator or name not in minimums or not INTEGER_PATTERN.fullmatch(raw_count.strip()):
            supported = ", ".join(sorted(minimums))
            raise ValueError(f"Invalid stratum minimum {value!r}; expected one of {supported}=COUNT.")
        minimums[name] = int(raw_count)
    return minimums


def classify_rows(rows: Sequence[Mapping[str, str]]) -> list[frozenset[str]]:
    ticket_files: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        ticket_files[row.get("ticket_id", "")].add(row.get("file_path", ""))

    classifications: list[frozenset[str]] = []
    for row in rows:
        strata = {
            name
            for name in row.get("audit_strata", "").split()
            if name in DEFAULT_STRATUM_MINIMUMS
        }
        qualified_name = row.get("qualified_name", "").strip()
        symbol_kind = row.get("symbol_kind", "").strip().casefold()
        mapping_method = row.get("mapping_method", "").strip().casefold()
        change_type = row.get("change_type", "").strip().casefold()
        if qualified_name != "<module>" and "." in qualified_name:
            strata.add("nested_symbol")
        if qualified_name == "<module>" or symbol_kind == "module":
            strata.add("module_level")
        if mapping_method == "insertion_anchor_containment":
            strata.add("pure_addition")
        if change_type == "deleted" or (
            mapping_method in {"modified_line_containment", "deleted_line_containment"}
            and bool(row.get("matched_old_lines", "").strip())
        ):
            strata.add("deletion")
        if len(ticket_files[row.get("ticket_id", "")]) > 1:
            strata.add("multi_file_ticket")
        classifications.append(frozenset(strata))
    return classifications


def create_stratified_sample(
    rows: Sequence[Mapping[str, str]],
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: int = DEFAULT_SEED,
    min_repositories: int = DEFAULT_MIN_REPOSITORIES,
    stratum_minimums: Mapping[str, int] | None = None,
) -> list[dict[str, str]]:
    minimums = _validated_sampling_parameters(
        sample_size=sample_size,
        min_repositories=min_repositories,
        stratum_minimums=stratum_minimums,
    )
    eligible = [dict(row) for row in rows if row.get("mapping_status", "").strip() == "mapped"]
    if len(eligible) < sample_size:
        raise ValueError(
            f"Need {sample_size} mapped rows, but the audit CSV contains only {len(eligible)}."
        )
    gold_ids = [row.get("gold_id", "").strip() for row in eligible]
    if any(not gold_id for gold_id in gold_ids):
        raise ValueError("Every mapped audit row must have a gold_id.")
    if len(set(gold_ids)) != len(gold_ids):
        raise ValueError("Mapped audit rows contain duplicate gold_id values.")
    repositories = {row.get("repo", "").strip() for row in eligible if row.get("repo", "").strip()}
    if len(repositories) < min_repositories:
        raise ValueError(
            f"Need {min_repositories} repositories, but mapped rows contain only {len(repositories)}."
        )

    strata_by_index = classify_rows(eligible)
    available = Counter(stratum for strata in strata_by_index for stratum in strata)
    shortages = {
        name: (available[name], minimum)
        for name, minimum in minimums.items()
        if available[name] < minimum
    }
    if shortages:
        details = ", ".join(
            f"{name}={actual}/{required}"
            for name, (actual, required) in sorted(shortages.items())
        )
        raise ValueError(f"Insufficient rows for audit strata: {details}.")

    priorities = {
        index: hashlib.sha256(
            f"{seed}\0{eligible[index]['gold_id']}".encode("utf-8")
        ).hexdigest()
        for index in range(len(eligible))
    }
    selected: list[int] = []
    selected_set: set[int] = set()
    counts: Counter[str] = Counter()
    selected_repositories: set[str] = set()

    while any(counts[name] < minimum for name, minimum in minimums.items()):
        candidates = [index for index in range(len(eligible)) if index not in selected_set]
        candidates.sort(
            key=lambda index: (
                -sum(
                    1
                    for name, minimum in minimums.items()
                    if counts[name] < minimum and name in strata_by_index[index]
                ),
                -(eligible[index].get("repo", "") not in selected_repositories),
                priorities[index],
            )
        )
        chosen = candidates[0]
        gain = sum(
            counts[name] < minimum and name in strata_by_index[chosen]
            for name, minimum in minimums.items()
        )
        if not gain:
            raise ValueError("Unable to satisfy audit stratum minimums within the sample.")
        _select(chosen, eligible, strata_by_index, selected, selected_set, counts, selected_repositories)
        if len(selected) > sample_size:
            raise ValueError("Audit stratum minimums require more rows than the sample size.")

    if len(selected_repositories) < min_repositories:
        for index in sorted(range(len(eligible)), key=priorities.__getitem__):
            repository = eligible[index].get("repo", "")
            if index not in selected_set and repository not in selected_repositories:
                _select(index, eligible, strata_by_index, selected, selected_set, counts, selected_repositories)
                if len(selected_repositories) >= min_repositories:
                    break
        if len(selected) > sample_size:
            raise ValueError("Repository coverage and stratum minimums exceed the sample size.")

    for index in sorted(range(len(eligible)), key=priorities.__getitem__):
        if len(selected) >= sample_size:
            break
        if index not in selected_set:
            _select(index, eligible, strata_by_index, selected, selected_set, counts, selected_repositories)

    ordered = sorted(selected, key=priorities.__getitem__)
    sampled: list[dict[str, str]] = []
    for sample_index, index in enumerate(ordered, start=1):
        row = dict(eligible[index])
        row["sample_index"] = str(sample_index)
        row["audit_seed"] = str(seed)
        row["audit_strata"] = " ".join(sorted(strata_by_index[index]))
        for field in REVIEW_FIELDS:
            row[field] = ""
        sampled.append(row)
    return sampled


def _select(
    index: int,
    rows: Sequence[Mapping[str, str]],
    strata_by_index: Sequence[frozenset[str]],
    selected: list[int],
    selected_set: set[int],
    counts: Counter[str],
    selected_repositories: set[str],
) -> None:
    selected.append(index)
    selected_set.add(index)
    counts.update(strata_by_index[index])
    selected_repositories.add(rows[index].get("repo", ""))


def _validated_sampling_parameters(
    *,
    sample_size: int,
    min_repositories: int,
    stratum_minimums: Mapping[str, int] | None,
) -> dict[str, int]:
    minimums = dict(DEFAULT_STRATUM_MINIMUMS if stratum_minimums is None else stratum_minimums)
    if sample_size <= 0 or min_repositories <= 0:
        raise ValueError("sample_size and min_repositories must be positive.")
    if min_repositories > sample_size:
        raise ValueError("min_repositories cannot exceed sample_size.")
    if set(minimums) != set(DEFAULT_STRATUM_MINIMUMS):
        raise ValueError("stratum_minimums must define every supported stratum exactly once.")
    if any(not isinstance(value, int) or value < 0 for value in minimums.values()):
        raise ValueError("Stratum minimums must be non-negative integers.")
    if any(value > sample_size for value in minimums.values()):
        raise ValueError("A stratum minimum cannot exceed sample_size.")
    return minimums


def validate_audit_sample(
    rows: Sequence[Mapping[str, str]],
    *,
    expected_sample_size: int = DEFAULT_SAMPLE_SIZE,
    min_repositories: int = DEFAULT_MIN_REPOSITORIES,
    stratum_minimums: Mapping[str, int] | None = None,
    exact_threshold: float = DEFAULT_EXACT_THRESHOLD,
) -> dict[str, Any]:
    minimums = _validated_sampling_parameters(
        sample_size=expected_sample_size,
        min_repositories=min_repositories,
        stratum_minimums=stratum_minimums,
    )
    if not 0.0 <= exact_threshold <= 1.0:
        raise ValueError("exact_threshold must be between 0 and 1.")

    classifications = classify_rows(rows)
    stratum_counts = Counter(stratum for strata in classifications for stratum in strata)
    repositories = {row.get("repo", "").strip() for row in rows if row.get("repo", "").strip()}
    sampling_issues: list[str] = []
    if len(rows) != expected_sample_size:
        sampling_issues.append(f"sample_size={len(rows)}, expected={expected_sample_size}")
    if len(repositories) < min_repositories:
        sampling_issues.append(
            f"repository_count={len(repositories)}, required={min_repositories}"
        )
    gold_ids = [row.get("gold_id", "").strip() for row in rows]
    if len(set(gold_ids)) != len(gold_ids):
        sampling_issues.append("sample contains duplicate gold_id values")
    for name, minimum in minimums.items():
        if stratum_counts[name] < minimum:
            sampling_issues.append(f"{name}={stratum_counts[name]}, required={minimum}")

    provenance_errors: list[dict[str, Any]] = []
    review_errors: list[dict[str, Any]] = []
    reviewed_count = 0
    exact_count = 0
    for index, row in enumerate(rows, start=1):
        provenance_issues = _provenance_issues(row)
        if provenance_issues:
            provenance_errors.append(_row_error(index, row, provenance_issues))
        review_state, is_exact, review_issues = _review_result(row)
        if review_state == "reviewed":
            reviewed_count += 1
            exact_count += int(is_exact)
        elif review_state == "invalid":
            review_errors.append(_row_error(index, row, review_issues))

    row_count = len(rows)
    exact_rate = exact_count / reviewed_count if reviewed_count else None
    provenance_complete_count = row_count - len(provenance_errors)
    provenance_rate = provenance_complete_count / row_count if row_count else 0.0
    if review_errors:
        exact_gate_status = "invalid_review"
    elif reviewed_count < row_count:
        exact_gate_status = "pending_review"
    elif exact_rate is not None and exact_rate >= exact_threshold:
        exact_gate_status = "passed"
    else:
        exact_gate_status = "failed"
    provenance_gate_status = "passed" if not provenance_errors and row_count else "failed"
    sampling_gate_status = "passed" if not sampling_issues else "failed"
    if "failed" in {sampling_gate_status, provenance_gate_status} or exact_gate_status in {
        "failed",
        "invalid_review",
    }:
        overall_gate_status = "failed"
    elif exact_gate_status == "pending_review":
        overall_gate_status = "pending_review"
    else:
        overall_gate_status = "passed"

    return {
        "sample_count": row_count,
        "expected_sample_count": expected_sample_size,
        "repository_count": len(repositories),
        "required_repository_count": min_repositories,
        "stratum_counts": dict(sorted(stratum_counts.items())),
        "stratum_minimums": dict(sorted(minimums.items())),
        "sampling_gate_status": sampling_gate_status,
        "sampling_issues": sampling_issues,
        "reviewed_count": reviewed_count,
        "exact_count": exact_count,
        "exact_rate": exact_rate,
        "exact_threshold": exact_threshold,
        "exact_gate_status": exact_gate_status,
        "review_error_count": len(review_errors),
        "review_errors": review_errors,
        "provenance_complete_count": provenance_complete_count,
        "provenance_complete_rate": provenance_rate,
        "provenance_gate_status": provenance_gate_status,
        "provenance_errors": provenance_errors,
        "overall_gate_status": overall_gate_status,
    }


def _provenance_issues(row: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    nonempty_fields = (
        "gold_id",
        "ticket_id",
        "repo",
        "base_commit",
        "file_path",
        "mapping_status",
        "mapping_method",
        "symbol_id",
        "qualified_name",
        "symbol_kind",
        "start_line",
        "start_column",
        "end_line",
        "end_column",
        "change_type",
        "hunk_index",
        "old_file_path",
        "old_start_line",
        "old_line_count",
        "new_start_line",
        "new_line_count",
        "patch_sha256",
    )
    for field in nonempty_fields:
        if not row.get(field, "").strip():
            issues.append(f"missing {field}")
    for field in ("gold_id", "symbol_id", "patch_sha256"):
        value = row.get(field, "").strip().lower()
        if value and not HASH_PATTERN.fullmatch(value):
            issues.append(f"invalid {field}")
    commit = row.get("base_commit", "").strip()
    if commit and not COMMIT_PATTERN.fullmatch(commit):
        issues.append("invalid base_commit")
    for field in (
        "hunk_index",
        "old_start_line",
        "old_line_count",
        "new_start_line",
        "new_line_count",
        "start_line",
        "start_column",
        "end_line",
        "end_column",
    ):
        value = row.get(field, "").strip()
        if value and not INTEGER_PATTERN.fullmatch(value):
            issues.append(f"invalid {field}")
    for field in ("start_line", "end_line"):
        value = row.get(field, "").strip()
        if INTEGER_PATTERN.fullmatch(value) and int(value) <= 0:
            issues.append(f"{field} must be positive")
    if row.get("mapping_status", "").strip() != "mapped":
        issues.append("mapping_status must be mapped")
    change_type = row.get("change_type", "").strip()
    old_path = row.get("old_file_path", "").strip()
    new_path = row.get("new_file_path", "").strip()
    file_path = row.get("file_path", "").strip()
    if change_type == "deleted":
        if new_path:
            issues.append("deleted provenance must not have new_file_path")
    elif change_type in {"modified", "renamed"} and not new_path:
        issues.append(f"{change_type} provenance requires new_file_path")
    elif change_type not in {"modified", "deleted", "renamed"}:
        issues.append("mapped provenance has unsupported change_type")
    if old_path and file_path != old_path:
        issues.append("file_path does not match old_file_path")
    mapping_method = row.get("mapping_method", "").strip()
    if mapping_method == "insertion_anchor_containment":
        anchor = row.get("insertion_anchor_line", "").strip()
        if not anchor or not INTEGER_PATTERN.fullmatch(anchor):
            issues.append("pure addition requires insertion_anchor_line")
    if mapping_method in {"modified_line_containment", "deleted_line_containment"}:
        lines = row.get("matched_old_lines", "").split()
        if not lines or any(not INTEGER_PATTERN.fullmatch(line) or int(line) <= 0 for line in lines):
            issues.append(f"{mapping_method} requires valid matched_old_lines")
    return issues


def _review_result(row: Mapping[str, str]) -> tuple[str, bool, list[str]]:
    status = row.get("review_status", "").strip().casefold()
    values = [row.get(field, "").strip() for field in REVIEW_FIELDS[1:4]]
    if not status and not any(values) and not row.get("review_note", "").strip():
        return "pending", False, []
    issues: list[str] = []
    if status not in {"approved", "rejected"}:
        issues.append("review_status must be approved or rejected")
    parsed: list[bool] = []
    for field, value in zip(REVIEW_FIELDS[1:4], values):
        boolean = _parse_boolean(value)
        if boolean is None:
            issues.append(f"{field} must be true or false")
        else:
            parsed.append(boolean)
    if issues:
        return "invalid", False, issues
    is_exact = all(parsed)
    if status == "approved" and not is_exact:
        issues.append("approved review requires all three exact fields to be true")
    if status == "rejected" and is_exact:
        issues.append("rejected review requires at least one exact field to be false")
    if status == "rejected" and not row.get("review_note", "").strip():
        issues.append("rejected review requires review_note")
    return ("invalid", False, issues) if issues else ("reviewed", is_exact, [])


def _parse_boolean(value: str) -> bool | None:
    normalized = value.strip().casefold()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def _row_error(index: int, row: Mapping[str, str], issues: Sequence[str]) -> dict[str, Any]:
    return {
        "sample_index": row.get("sample_index", "") or index,
        "gold_id": row.get("gold_id", ""),
        "issues": list(issues),
    }


def write_audit_csv(
    path: Path,
    rows: Sequence[Mapping[str, str]],
    *,
    source_fields: Sequence[str],
) -> None:
    fieldnames = [*AUDIT_METADATA_FIELDS, *(field for field in source_fields if field not in AUDIT_METADATA_FIELDS)]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)
    atomic_write_text(path, buffer.getvalue())


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    main()
