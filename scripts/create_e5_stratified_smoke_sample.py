#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for import_path in (str(ROOT), str(SRC)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from scripts.evaluate_fault_localization import _ticket_id, read_records  # noqa: E402


GROUP_ORDER = ("small", "medium", "large")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a deterministic E5 smoke split with equal tickets per size group."
    )
    parser.add_argument("--tickets", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--repository-size-groups", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--per-group", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260823)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.per_group <= 0:
        raise ValueError("per-group must be positive.")
    tickets_path = Path(args.tickets)
    gold_path = Path(args.gold)
    groups_path = Path(args.repository_size_groups)
    for path in (tickets_path, gold_path, groups_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    tickets = read_records(tickets_path)
    gold_rows = read_records(gold_path)
    group_mapping = load_group_mapping(groups_path)
    selected_ids, counts = select_ticket_ids(
        tickets,
        group_mapping,
        per_group=args.per_group,
        seed=args.seed,
    )
    tickets_by_id = index_rows(tickets, "tickets")
    gold_by_id = index_rows(gold_rows, "gold")
    if not selected_ids.issubset(gold_by_id):
        raise ValueError("Gold data is missing selected E5 smoke ticket IDs.")

    selected_tickets = [tickets_by_id[ticket_id] for ticket_id in sorted(selected_ids)]
    selected_gold = [gold_by_id[ticket_id] for ticket_id in sorted(selected_ids)]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tickets_output = output_dir / "tickets.jsonl"
    gold_output = output_dir / "gold.jsonl"
    manifest_output = output_dir / "sample_manifest.json"
    write_jsonl(tickets_output, selected_tickets)
    write_jsonl(gold_output, selected_gold)
    manifest = {
        "purpose": "E5 size-aware semantic candidate pool smoke test",
        "selection": "Lowest deterministic SHA-256 score within each repository-size group",
        "seed": args.seed,
        "per_group": args.per_group,
        "tickets": len(selected_ids),
        "group_counts": counts,
        "ticket_ids": sorted(selected_ids),
        "sources": {
            "tickets": str(tickets_path),
            "gold": str(gold_path),
            "repository_size_groups": str(groups_path),
        },
        "holdout_used": False,
    }
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def select_ticket_ids(
    tickets: list[dict[str, Any]],
    group_mapping: dict[str, str],
    *,
    per_group: int,
    seed: int,
) -> tuple[set[str], dict[str, int]]:
    if per_group <= 0:
        raise ValueError("per_group must be positive.")
    tickets_by_group: dict[str, list[tuple[str, str]]] = {
        label: [] for label in GROUP_ORDER
    }
    for ticket in tickets:
        ticket_id = _ticket_id(ticket)
        repository = str(ticket.get("repo") or "")
        size_group = group_mapping.get(repository)
        if not ticket_id or size_group not in tickets_by_group:
            continue
        score = hashlib.sha256(
            f"{seed}:{size_group}:{ticket_id}".encode("utf-8")
        ).hexdigest()
        tickets_by_group[size_group].append((score, ticket_id))
    selected: set[str] = set()
    counts: dict[str, int] = {}
    for size_group in GROUP_ORDER:
        candidates = sorted(tickets_by_group[size_group])
        if len(candidates) < per_group:
            raise ValueError(
                f"Size group {size_group} has only {len(candidates)} tickets; "
                f"requires {per_group}."
            )
        current_ids = [ticket_id for _, ticket_id in candidates[:per_group]]
        selected.update(current_ids)
        counts[size_group] = len(current_ids)
    return selected, counts


def load_group_mapping(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for size_group, repositories in (payload.get("groups") or {}).items():
        if size_group not in GROUP_ORDER:
            continue
        for repository in repositories or []:
            mapping[str(repository)] = size_group
    if set(mapping.values()) != set(GROUP_ORDER):
        raise ValueError("Group mapping must contain small, medium, and large.")
    return mapping


def index_rows(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticket_id = _ticket_id(row)
        if not ticket_id:
            raise ValueError(f"{label} contains a row without ticket_id.")
        if ticket_id in indexed:
            raise ValueError(f"{label} contains duplicate ticket_id {ticket_id}.")
        indexed[ticket_id] = row
    return indexed


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
