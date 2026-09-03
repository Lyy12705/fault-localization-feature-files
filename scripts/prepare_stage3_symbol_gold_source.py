#!/usr/bin/env python3
"""Prepare a reproducible development-only ticket subset with developer patches."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.symbol_gold import parse_unified_diff


DEFAULT_SEED = 20260902
DEFAULT_PER_REPOSITORY = 12
DEFAULT_MIN_FEATURE_TICKETS = 15


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Join development tickets with public SWE-bench patches and create a "
            "deterministic repository-balanced Symbol Gold source subset."
        )
    )
    parser.add_argument("--tickets", required=True, help="Development tickets JSONL.")
    parser.add_argument("--source-parquet", required=True, help="Public SWE-bench Parquet.")
    parser.add_argument("--output", required=True, help="Output tickets-with-patch JSONL.")
    parser.add_argument("--manifest", required=True, help="Output selection manifest JSON.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--per-repository", type=int, default=DEFAULT_PER_REPOSITORY)
    parser.add_argument(
        "--min-feature-tickets", type=int, default=DEFAULT_MIN_FEATURE_TICKETS
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.per_repository <= 0 or args.min_feature_tickets < 0:
        raise ValueError("per-repository must be positive and min-feature-tickets non-negative.")
    tickets_path = Path(args.tickets).resolve()
    parquet_path = Path(args.source_parquet).resolve()
    for path in (tickets_path, parquet_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    tickets = read_jsonl(tickets_path)
    patch_rows = read_patch_rows(parquet_path)
    joined = join_development_patches(tickets, patch_rows)
    selected, selection = select_source_tickets(
        joined,
        seed=args.seed,
        per_repository=args.per_repository,
        min_feature_tickets=args.min_feature_tickets,
    )
    output_path = Path(args.output).resolve()
    manifest_path = Path(args.manifest).resolve()
    atomic_write_jsonl(output_path, selected)
    manifest = {
        "purpose": "Stage 3 Symbol Gold development audit source",
        "seed": args.seed,
        "source_ticket_count": len(tickets),
        "joined_ticket_count": len(joined),
        **selection,
        "sources": {
            "development_tickets": portable_path(tickets_path),
            "public_swebench_parquet": portable_path(parquet_path),
        },
        "output": portable_path(output_path),
        "selection_uses_model_predictions": False,
        "selection_uses_frozen_holdout": False,
    }
    atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def read_patch_rows(path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Reading SWE-bench Parquet requires pandas and pyarrow.") from exc
    frame = pd.read_parquet(
        path,
        columns=["instance_id", "repo", "base_commit", "patch"],
    )
    return [dict(row) for row in frame.to_dict(orient="records")]


def join_development_patches(
    tickets: Sequence[Mapping[str, Any]],
    patch_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    patches_by_id: dict[str, Mapping[str, Any]] = {}
    for row in patch_rows:
        ticket_id = str(row.get("instance_id") or "").strip()
        if not ticket_id:
            raise ValueError("Parquet contains a row without instance_id.")
        if ticket_id in patches_by_id:
            raise ValueError(f"Parquet contains duplicate instance_id {ticket_id!r}.")
        patches_by_id[ticket_id] = row

    joined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ticket in tickets:
        ticket_id = str(ticket.get("ticket_id") or ticket.get("instance_id") or "").strip()
        if not ticket_id or ticket_id in seen:
            raise ValueError("Development tickets require unique, non-empty ticket IDs.")
        seen.add(ticket_id)
        source = patches_by_id.get(ticket_id)
        if source is None:
            raise ValueError(f"Public Parquet is missing development ticket {ticket_id!r}.")
        repo = str(ticket.get("repo") or "").strip()
        base_commit = str(ticket.get("base_commit") or "").strip()
        if repo != str(source.get("repo") or "").strip():
            raise ValueError(f"Repository mismatch for {ticket_id!r}.")
        if base_commit != str(source.get("base_commit") or "").strip():
            raise ValueError(f"Base commit mismatch for {ticket_id!r}.")
        patch = str(source.get("patch") or "")
        if not patch:
            raise ValueError(f"Developer patch is empty for {ticket_id!r}.")
        enriched = dict(ticket)
        enriched["patch"] = patch
        joined.append(enriched)
    return joined


def select_source_tickets(
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    per_repository: int,
    min_feature_tickets: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if per_repository <= 0 or min_feature_tickets < 0:
        raise ValueError("Selection counts are invalid.")
    by_repository: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    features_by_id: dict[str, frozenset[str]] = {}
    for row in rows:
        ticket_id = _ticket_id(row)
        repository = str(row.get("repo") or "").strip()
        if not ticket_id or not repository:
            raise ValueError("Source rows require ticket_id and repo.")
        by_repository[repository].append(row)
        features_by_id[ticket_id] = patch_features(str(row.get("patch") or ""))

    selected: dict[str, Mapping[str, Any]] = {}
    for repository, candidates in sorted(by_repository.items()):
        if len(candidates) < per_repository:
            raise ValueError(
                f"Repository {repository!r} has {len(candidates)} tickets; "
                f"requires {per_repository}."
            )
        ordered = sorted(candidates, key=lambda row: _priority(seed, _ticket_id(row)))
        for row in ordered[:per_repository]:
            selected[_ticket_id(row)] = row

    for feature in ("pure_addition", "multi_file"):
        current = sum(feature in features_by_id[ticket_id] for ticket_id in selected)
        if current >= min_feature_tickets:
            continue
        candidates = sorted(
            (
                row
                for row in rows
                if feature in features_by_id[_ticket_id(row)]
                and _ticket_id(row) not in selected
            ),
            key=lambda row: _priority(seed, _ticket_id(row)),
        )
        needed = min_feature_tickets - current
        if len(candidates) < needed:
            raise ValueError(
                f"Feature {feature!r} has only {current + len(candidates)} tickets; "
                f"requires {min_feature_tickets}."
            )
        for row in candidates[:needed]:
            selected[_ticket_id(row)] = row

    ordered_selected = sorted(
        (dict(row) for row in selected.values()),
        key=lambda row: _ticket_id(row),
    )
    feature_counts = Counter(
        feature
        for row in ordered_selected
        for feature in features_by_id[_ticket_id(row)]
    )
    repository_counts = Counter(str(row.get("repo") or "") for row in ordered_selected)
    return ordered_selected, {
        "selected_ticket_count": len(ordered_selected),
        "selected_repository_count": len(repository_counts),
        "per_repository_minimum": per_repository,
        "feature_ticket_minimum": min_feature_tickets,
        "repository_counts": dict(sorted(repository_counts.items())),
        "feature_counts": dict(sorted(feature_counts.items())),
        "selection_policy": (
            "Lowest SHA-256(seed, ticket_id) rows per development repository, then "
            "deterministic additions to meet patch-feature coverage."
        ),
    }


def patch_features(patch: str) -> frozenset[str]:
    features: set[str] = set()
    try:
        hunks = parse_unified_diff(patch)
    except ValueError:
        hunks = ()
    paths = {
        hunk.new_file_path or hunk.old_file_path
        for hunk in hunks
        if hunk.new_file_path or hunk.old_file_path
    }
    if len(paths) > 1:
        features.add("multi_file")
    if any(
        hunk.change_type != "added"
        and bool(hunk.added_new_lines)
        and not hunk.deleted_old_lines
        for hunk in hunks
    ):
        features.add("pure_addition")
    if any(hunk.deleted_old_lines for hunk in hunks):
        features.add("deletion_evidence")
    if any(hunk.change_type == "deleted" for hunk in hunks):
        features.add("deleted_file")
    return frozenset(features)


def _priority(seed: int, ticket_id: str) -> str:
    return hashlib.sha256(f"{seed}\0{ticket_id}".encode("utf-8")).hexdigest()


def _ticket_id(row: Mapping[str, Any]) -> str:
    return str(row.get("ticket_id") or row.get("instance_id") or "").strip()


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


def atomic_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    atomic_write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
    )


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


if __name__ == "__main__":
    main()
