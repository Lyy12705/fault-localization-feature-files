"""Stage-4 WP2 diagnostic: what KIND of candidates does a predictions file carry?

Stage-4 patch generation replaces a target region with model-generated code,
so it needs candidates whose ``start_line``/``end_line`` are the boundaries of
an actual definition (a function, method or class). A fixed-size retrieval
CHUNK is not usable as a patch target: its boundaries fall wherever the
chunker put them, so a chunk routinely spans two functions and ends in the
middle of a third one's body. Asking a model to infill that is asking it to
reproduce several definitions exactly and land on an arbitrary indentation
level -- it will fail regardless of model quality or token budget.

This was hit for real on 2026-09-12: the Stage-4 1-ticket smoke run scored
0/3 on astropy__astropy-13073, where the top-ranked candidate covered
ui.py lines 252-331 -- exactly 80 lines, starting one line above
``def _expand_user_if_path`` and ending at ``encoding = kwargs.get('encoding')``
nested 12 spaces deep inside a different function.

Run this over every candidate predictions file to see which ones carry
definition-shaped candidates before committing a pilot run to one:

    python scripts/inspect_stage4_input_symbols.py \\
      --predictions reports/fault_localization/stage3_source_neighborhood_dev_v1/b1_coverage_aware_v1_predictions.jsonl \\
      --ticket-ids-from reports/fault_localization/stage3_wp4_pilot/pilot_46tickets.jsonl

Pass several --predictions to compare them side by side.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.patch_generation import _DEF_SHAPED_SYMBOL_KINDS  # noqa: E402


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("version https://git-lfs.github.com/spec/v1"):
                raise ValueError(f"{path} is still a Git LFS pointer. Run `git lfs pull` first.")
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON ({exc})") from None
    return rows


def describe_real_symbol_sizes(
    path: Path,
    allow: set[str] | None,
    *,
    repo_cache_dir: Path,
    snapshot_cache_dir: Path,
) -> None:
    """Resolve each top-1 candidate to its TRUE definition and report the size spread.

    This is the number that decides whether whole-symbol FIM regeneration is
    viable at all: the model has to reproduce the entire definition, so a
    137-line target means reproducing ~136 unchanged lines plus the fix. Sizes
    here are real definition sizes, not Stage-3's chunk-capped ones.
    """

    from utils.patch_generation import resolve_symbol_line_range
    from utils.repo_snapshot import (
        RepoSnapshotError,
        materialize_commit_snapshot,
        read_file_text,
        resolve_repository_path,
    )

    rows = load_jsonl(path)
    if allow is not None:
        rows = [r for r in rows if str(r.get("ticket_id") or "") in allow]

    sizes: list[tuple[int, str, str]] = []
    unresolved: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []

    for row in rows:
        ticket_id = str(row.get("ticket_id") or "?")
        ranked = row.get("stage3_ranked_symbols") or []
        if not ranked:
            continue
        top = ranked[0]
        file_path = str(top.get("file_path") or "")
        if not file_path.endswith(".py"):
            skipped.append((ticket_id, f"not python: {file_path}"))
            continue
        try:
            source_repo = resolve_repository_path({"repo": row.get("repo")}, repo_cache_dir=repo_cache_dir)
            snapshot = materialize_commit_snapshot(
                source_repo,
                repo=str(row.get("repo")),
                base_commit=str(row.get("base_commit")),
                snapshot_cache_dir=snapshot_cache_dir,
            )
            file_text = read_file_text(snapshot, file_path)
        except RepoSnapshotError as exc:
            skipped.append((ticket_id, str(exc)[:80]))
            continue

        resolved = resolve_symbol_line_range(
            file_text,
            symbol_qualified_name=str(top.get("symbol_qualified_name") or ""),
            symbol_name=str(top.get("symbol_name") or ""),
            hint_start_line=int(top.get("start_line") or 1),
            hint_end_line=int(top.get("end_line") or 1),
        )
        if not resolved.resolved:
            unresolved.append((ticket_id, resolved.reason[:80]))
            continue
        sizes.append(
            (resolved.end_line - resolved.start_line + 1, ticket_id, str(top.get("symbol_qualified_name") or ""))
        )

    print("=" * 78)
    print(f"REAL definition sizes for top-1 candidates in {path.name}")
    print(f"  resolved: {len(sizes)}   unresolved: {len(unresolved)}   skipped: {len(skipped)}")
    if not sizes:
        print("  (nothing resolved -- cannot assess)")
        return

    sizes.sort()
    only = [s for s, _, _ in sizes]
    total = len(only)
    print(f"  lines per target: min={only[0]}  median={only[total // 2]}  max={only[-1]}")
    print()
    print("  size distribution (whole-symbol regeneration gets harder with every line):")
    for label, lo, hi in [
        ("<= 20 lines  (very likely regenerable)", 0, 20),
        ("21-50 lines  (plausible)", 21, 50),
        ("51-100 lines (hard for a 7B model)", 51, 100),
        ("> 100 lines  (very unlikely)", 101, 10**9),
    ]:
        count = sum(1 for s in only if lo <= s <= hi)
        bar = "#" * int(40 * count / total)
        print(f"    {label:42s} {count:3d} ({count/total:5.1%}) {bar}")

    print()
    print("  largest 5 targets:")
    for size, ticket, name in sizes[-5:][::-1]:
        print(f"    {size:4d} lines  {ticket}  ({name})")
    print("  smallest 5 targets:")
    for size, ticket, name in sizes[:5]:
        print(f"    {size:4d} lines  {ticket}  ({name})")

    if unresolved:
        print()
        print(f"  unresolved ({len(unresolved)}):")
        for ticket, reason in unresolved[:10]:
            print(f"    {ticket}: {reason}")
    if skipped:
        print()
        print(f"  skipped ({len(skipped)}):")
        for ticket, reason in skipped[:10]:
            print(f"    {ticket}: {reason}")
    print()


def describe_size_limited_selection(
    path: Path,
    allow: set[str] | None,
    *,
    repo_cache_dir: Path,
    snapshot_cache_dir: Path,
    thresholds: tuple[int, ...] = (30, 50, 100, 200),
) -> None:
    """Simulate 'take the highest-ranked candidate that is small enough'.

    Whole-symbol regeneration is infeasible once a target is hundreds of lines
    (and a whole-class target is the wrong granularity for a bug fix anyway:
    the fix changes a few lines inside one method). Stage-3 ranks more than
    one candidate per ticket, so a feasible target may sit further down its
    OWN ranking -- no new ranking signal needed.

    This reports, for several size limits: how many tickets get a target, and
    at what rank, so the limit can be chosen from data instead of guessed.
    """

    from utils.patch_generation import resolve_symbol_line_range
    from utils.repo_snapshot import (
        RepoSnapshotError,
        materialize_commit_snapshot,
        read_file_text,
        resolve_repository_path,
    )

    rows = load_jsonl(path)
    if allow is not None:
        rows = [r for r in rows if str(r.get("ticket_id") or "") in allow]

    # (ticket_id, [(rank, size)]) for every resolvable candidate, in rank order.
    per_ticket: list[tuple[str, list[tuple[int, int, str]]]] = []

    for row in rows:
        ticket_id = str(row.get("ticket_id") or "?")
        ranked = row.get("stage3_ranked_symbols") or []
        if not ranked:
            continue
        try:
            source_repo = resolve_repository_path({"repo": row.get("repo")}, repo_cache_dir=repo_cache_dir)
            snapshot = materialize_commit_snapshot(
                source_repo,
                repo=str(row.get("repo")),
                base_commit=str(row.get("base_commit")),
                snapshot_cache_dir=snapshot_cache_dir,
            )
        except RepoSnapshotError:
            continue

        candidates: list[tuple[int, int, str]] = []
        file_cache: dict[str, str] = {}
        for rank, cand in enumerate(ranked, start=1):
            file_path = str(cand.get("file_path") or "")
            if not file_path.endswith(".py"):
                continue
            if file_path not in file_cache:
                try:
                    file_cache[file_path] = read_file_text(snapshot, file_path)
                except RepoSnapshotError:
                    file_cache[file_path] = ""
            text = file_cache[file_path]
            if not text:
                continue
            resolved = resolve_symbol_line_range(
                text,
                symbol_qualified_name=str(cand.get("symbol_qualified_name") or ""),
                symbol_name=str(cand.get("symbol_name") or ""),
                hint_start_line=int(cand.get("start_line") or 1),
                hint_end_line=int(cand.get("end_line") or 1),
            )
            if resolved.resolved:
                candidates.append(
                    (rank, resolved.end_line - resolved.start_line + 1, str(cand.get("symbol_qualified_name") or ""))
                )
        per_ticket.append((ticket_id, candidates))

    print("=" * 78)
    print("SELECTION POLICY SIMULATION: highest-ranked candidate within a size limit")
    print(f"  tickets examined: {len(per_ticket)}")
    print(f"  candidates per ticket (resolvable): "
          f"min={min((len(c) for _, c in per_ticket), default=0)} "
          f"max={max((len(c) for _, c in per_ticket), default=0)}")
    print()
    print(f"  {'size limit':>12s} {'tickets with a target':>22s} {'used rank 1':>12s} {'used rank>1':>12s} {'no target':>10s}")
    for limit in thresholds:
        got = rank1 = deeper = none = 0
        for _, candidates in per_ticket:
            fit = next((c for c in candidates if c[1] <= limit), None)
            if fit is None:
                none += 1
            else:
                got += 1
                if fit[0] == 1:
                    rank1 += 1
                else:
                    deeper += 1
        total = len(per_ticket) or 1
        print(f"  {limit:>10d} L {got:>13d} ({got/total:5.1%}) {rank1:>12d} {deeper:>12d} {none:>10d}")
    print()
    print("  'used rank>1' = tickets where the top candidate was too big but a smaller,")
    print("  lower-ranked candidate from Stage-3's OWN ranking was usable.")
    print()


def describe(path: Path, allow: set[str] | None) -> None:
    rows = load_jsonl(path)
    if allow is not None:
        rows = [r for r in rows if str(r.get("ticket_id") or "") in allow]

    print("=" * 78)
    print(f"{path}")
    print(f"  rows in scope: {len(rows)}")

    kinds: Counter = Counter()
    spans: list[int] = []
    eligible = 0
    for row in rows:
        ranked = row.get("stage3_ranked_symbols") or []
        if not ranked:
            continue
        eligible += 1
        top = ranked[0]
        kinds[str(top.get("symbol_kind") or "<missing>")] += 1
        try:
            spans.append(int(top["end_line"]) - int(top["start_line"]) + 1)
        except (KeyError, TypeError, ValueError):
            pass

    print(f"  tickets with a ranked candidate: {eligible}")
    print("  top-1 candidate symbol_kind distribution:")
    for kind, count in kinds.most_common():
        usable = "definition-shaped (usable as a patch target)" if kind in _DEF_SHAPED_SYMBOL_KINDS else "NOT a definition -- unusable as a patch target"
        print(f"    {kind:24s} {count:4d}   {usable}")

    if spans:
        spans.sort()
        uniform = len(set(spans)) == 1
        print(f"  top-1 candidate line-span: min={spans[0]} median={spans[len(spans)//2]} max={spans[-1]}")
        if uniform:
            print(f"    NOTE: every candidate is exactly {spans[0]} lines -- that is a fixed-size chunker, not AST boundaries.")

    sample = next((r for r in rows if r.get("stage3_ranked_symbols")), None)
    if sample:
        top = sample["stage3_ranked_symbols"][0]
        print("  sample top-1 candidate:")
        print(f"    ticket_id             : {sample.get('ticket_id')}")
        print(f"    file_path             : {top.get('file_path')}")
        print(f"    symbol_kind           : {top.get('symbol_kind')}")
        print(f"    symbol_qualified_name : {top.get('symbol_qualified_name')}")
        print(f"    symbol_name           : {top.get('symbol_name')}")
        print(f"    lines                 : {top.get('start_line')}-{top.get('end_line')}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", action="append", required=True, help="Repeatable.")
    parser.add_argument("--ticket-ids-from", default=None)
    parser.add_argument(
        "--repo-cache-dir",
        default=None,
        help="When given, also resolve each top-1 candidate to its REAL definition in the "
        "base-commit source and report the true size distribution (needs the repo cache).",
    )
    parser.add_argument("--snapshot-cache-dir", default=None)
    args = parser.parse_args(argv)

    allow: set[str] | None = None
    if args.ticket_ids_from:
        allow = set()
        for line in Path(args.ticket_ids_from).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                ticket_id = str(row.get("ticket_id") or "") if isinstance(row, dict) else str(row)
            except json.JSONDecodeError:
                ticket_id = line
            if ticket_id:
                allow.add(ticket_id)
        print(f"Ticket allowlist: {len(allow)} id(s) from {args.ticket_ids_from}\n")

    for raw in args.predictions:
        path = Path(raw)
        if not path.exists():
            print(f"SKIP (not found): {path}\n")
            continue
        try:
            describe(path, allow)
            if args.repo_cache_dir:
                repo_cache_dir = Path(args.repo_cache_dir)
                snapshot_cache_dir = (
                    Path(args.snapshot_cache_dir)
                    if args.snapshot_cache_dir
                    else repo_cache_dir / ".stage4_snapshots"
                )
                describe_real_symbol_sizes(
                    path, allow, repo_cache_dir=repo_cache_dir, snapshot_cache_dir=snapshot_cache_dir
                )
                describe_size_limited_selection(
                    path, allow, repo_cache_dir=repo_cache_dir, snapshot_cache_dir=snapshot_cache_dir
                )
        except ValueError as exc:
            print(f"SKIP ({exc})\n")

    print("Stage-4 needs definition-shaped candidates (function/method/class).")
    print("A file whose candidates are all 'chunk' (or all the same line-span) cannot be")
    print("used as a patch-generation input no matter how the prompt is tuned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
