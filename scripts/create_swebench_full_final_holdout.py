#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATASET_NAME = "princeton-nlp/SWE-bench"
DATASET_SOURCE_URL = "https://huggingface.co/datasets/princeton-nlp/SWE-bench"
TRAIN_PARQUET_URL = (
    "https://huggingface.co/datasets/princeton-nlp/SWE-bench/resolve/main/"
    "data/train-00000-of-00001.parquet"
)
DEFAULT_SEED = "swebench-full-stage1-final-holdout-v2-20260824"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a write-once, repository-disjoint Final Holdout from the official "
            "SWE-bench train split without using patch contents for selection."
        )
    )
    parser.add_argument("--source-parquet", required=True)
    parser.add_argument(
        "--seen-tickets",
        required=True,
        help="All previously used SWE-bench tickets; their IDs and repositories are excluded.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--dataset-name", default=DATASET_NAME)
    parser.add_argument("--source-split", default="train")
    parser.add_argument("--source-url", default=DATASET_SOURCE_URL)
    parser.add_argument("--source-parquet-url", default=TRAIN_PARQUET_URL)
    parser.add_argument("--protocol", default="swebench-full-stage1-final-holdout-v2")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.size <= 0:
        raise ValueError("size must be positive.")
    source_path = Path(args.source_parquet)
    seen_path = Path(args.seen_tickets)
    for path in (source_path, seen_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    seen_rows = read_jsonl(seen_path)
    seen_ids = {ticket_id(row) for row in seen_rows if ticket_id(row)}
    seen_repositories = {
        str(row.get("repo") or "").strip()
        for row in seen_rows
        if str(row.get("repo") or "").strip()
    }
    frame = pd.read_parquet(source_path)
    required_columns = {
        "instance_id",
        "repo",
        "base_commit",
        "problem_statement",
        "patch",
    }
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"Source parquet is missing columns: {', '.join(missing)}")
    source_rows = [normalize_source_row(row) for row in frame.to_dict(orient="records")]
    selected, eligible_count = select_repository_disjoint_rows(
        source_rows,
        seen_ids=seen_ids,
        seen_repositories=seen_repositories,
        target=args.size,
        seed=args.seed,
    )

    output_dir = Path(args.output_dir)
    tickets_path = output_dir / "final_holdout_tickets.jsonl"
    gold_path = output_dir / "sealed" / "final_holdout_gold.jsonl"
    manifest_path = output_dir / "final_holdout_manifest.json"
    outputs = (tickets_path, gold_path, manifest_path)
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite write-once Final Holdout artifacts: "
            + ", ".join(portable_path(path) for path in existing)
        )

    tickets = [
        ticket_record(row, dataset_name=args.dataset_name, source_split=args.source_split)
        for row in selected
    ]
    gold = [
        gold_record(row, dataset_name=args.dataset_name, source_split=args.source_split)
        for row in selected
    ]
    write_jsonl(tickets_path, tickets)
    write_jsonl(gold_path, gold)
    selected_ids = {ticket_id(row) for row in tickets}
    selected_repositories = {str(row.get("repo") or "") for row in tickets}
    counts = repository_counts(tickets)
    manifest = {
        "protocol": args.protocol,
        "status": "prepared_not_evaluated",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset_name,
        "source_split": args.source_split,
        "source_url": args.source_url,
        "source_parquet_url": args.source_parquet_url,
        "source_rows": len(source_rows),
        "eligible_repository_disjoint_rows": eligible_count,
        "selected_rows": len(tickets),
        "selected_repositories": len(selected_repositories),
        "repository_counts": counts,
        "selection_policy": {
            "seed": args.seed,
            "repository_exclusion": (
                "Exclude every repository present in the complete seen-ticket artifact."
            ),
            "ticket_exclusion": "Exclude every ticket ID in the complete seen-ticket artifact.",
            "sampling": (
                "Deterministic repository-stratified proportional sampling using only "
                "instance_id and repository; patch and gold contents are not selection features."
            ),
        },
        "leakage_checks": {
            "ticket_id_overlap_with_seen": len(selected_ids & seen_ids),
            "repository_overlap_with_seen": len(selected_repositories & seen_repositories),
            "unique_selected_ticket_ids": len(selected_ids) == len(tickets),
        },
        "artifacts": {
            "source_parquet": artifact(source_path),
            "seen_tickets": artifact(seen_path),
            "tickets": artifact(tickets_path),
            "sealed_gold": artifact(gold_path),
        },
        "gold_access_policy": (
            "Do not inspect sealed gold before prediction completes. The one-time runner may use "
            "it only for final metric calculation after the frozen method produces predictions."
        ),
        "evaluation_policy": (
            "Execute the frozen method once. Do not tune, rerank, or rerun based on these results."
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "source_rows": manifest["source_rows"],
                "eligible_repository_disjoint_rows": eligible_count,
                "selected_rows": len(tickets),
                "selected_repositories": len(selected_repositories),
                "ticket_id_overlap_with_seen": 0,
                "repository_overlap_with_seen": 0,
                "manifest": portable_path(manifest_path),
                "sealed_gold_not_displayed": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def select_repository_disjoint_rows(
    rows: list[dict[str, Any]],
    *,
    seen_ids: set[str],
    seen_repositories: set[str],
    target: int,
    seed: str,
) -> tuple[list[dict[str, Any]], int]:
    eligible = [
        row
        for row in rows
        if ticket_id(row)
        and ticket_id(row) not in seen_ids
        and str(row.get("repo") or "").strip()
        and str(row.get("repo") or "").strip() not in seen_repositories
    ]
    if target > len(eligible):
        raise ValueError(
            f"Requested {target} repository-disjoint rows, but only {len(eligible)} are eligible."
        )
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        groups[str(row["repo"])].append(row)
    for repository in groups:
        groups[repository] = sorted(
            groups[repository],
            key=lambda row: stable_score(seed, ticket_id(row)),
        )
    quotas = proportional_quotas(
        {repository: len(group) for repository, group in groups.items()},
        target,
    )
    selected = [
        row
        for repository in sorted(groups)
        for row in groups[repository][: quotas[repository]]
    ]
    selected.sort(
        key=lambda row: (
            str(row["repo"]),
            stable_score(f"{seed}:output", ticket_id(row)),
        )
    )
    if len(selected) != target:
        raise AssertionError(f"Expected {target} rows, selected {len(selected)}.")
    return selected, len(eligible)


def proportional_quotas(capacities: dict[str, int], target: int) -> dict[str, int]:
    total = sum(capacities.values())
    if target < 0 or target > total:
        raise ValueError(f"Invalid target {target} for capacity {total}.")
    raw = {
        repository: target * capacity / total
        for repository, capacity in capacities.items()
    }
    quotas = {
        repository: min(capacities[repository], int(raw[repository]))
        for repository in capacities
    }
    remaining = target - sum(quotas.values())
    order = sorted(
        capacities,
        key=lambda repository: (
            raw[repository] - int(raw[repository]),
            capacities[repository],
            repository,
        ),
        reverse=True,
    )
    while remaining:
        progressed = False
        for repository in order:
            if quotas[repository] >= capacities[repository]:
                continue
            quotas[repository] += 1
            remaining -= 1
            progressed = True
            if remaining == 0:
                break
        if not progressed:
            raise AssertionError("Unable to allocate all Final Holdout rows.")
    return quotas


def normalize_source_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        key: normalize_value(value)
        for key, value in row.items()
    }
    normalized["instance_id"] = str(normalized.get("instance_id") or "")
    normalized["repo"] = str(normalized.get("repo") or "")
    return normalized


def ticket_record(
    row: dict[str, Any],
    *,
    dataset_name: str = DATASET_NAME,
    source_split: str = "train",
) -> dict[str, Any]:
    problem = str(row.get("problem_statement") or "")
    return {
        "ticket_id": ticket_id(row),
        "title": first_nonempty_line(problem) or ticket_id(row),
        "description": problem,
        "bug_report": problem,
        "product": str(row.get("repo") or ""),
        "component": str(row.get("repo") or "").split("/")[-1],
        "source_dataset": dataset_name,
        "source_split": source_split,
        "repo": str(row.get("repo") or ""),
        "repository_url": f"https://github.com/{row.get('repo', '')}",
        "base_commit": str(row.get("base_commit") or ""),
        "pull_number": str(row.get("pull_number") or ""),
        "created_at": str(row.get("created_at") or ""),
        "version": str(row.get("version") or ""),
        "hints_text": str(row.get("hints_text") or ""),
        "fail_to_pass": parse_json_list(row.get("FAIL_TO_PASS")),
        "pass_to_pass": parse_json_list(row.get("PASS_TO_PASS")),
    }


def gold_record(
    row: dict[str, Any],
    *,
    dataset_name: str = DATASET_NAME,
    source_split: str = "train",
) -> dict[str, Any]:
    return {
        "ticket_id": ticket_id(row),
        "fixed_files": extract_modified_files(str(row.get("patch") or "")),
        "fixed_symbols": [],
        "source_dataset": dataset_name,
        "source_split": source_split,
        "repo": str(row.get("repo") or ""),
        "repository_url": f"https://github.com/{row.get('repo', '')}",
        "base_commit": str(row.get("base_commit") or ""),
        "license": "MIT",
        "ground_truth_source": "SWE-bench developer patch parsed after blind selection",
    }


def extract_modified_files(patch_text: str) -> list[str]:
    files: list[str] = []
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:].strip())
        elif line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4 and parts[3].startswith("b/"):
                files.append(parts[3][2:])
    return list(dict.fromkeys(file for file in files if file and file != "/dev/null"))


def normalize_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict)):
        return value
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
        return value.tolist()
    return "" if pd.isna(value) else value


def parse_json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def first_nonempty_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def stable_score(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def ticket_id(row: dict[str, Any]) -> str:
    return str(row.get("ticket_id") or row.get("instance_id") or "")


def repository_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.get("repo") or "")] += 1
    return dict(sorted(counts.items()))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path}:{line_number}.")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


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
