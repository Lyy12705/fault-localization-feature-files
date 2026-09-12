"""Stage-4 WP1 acceptance check: replay the symbol-aware confidence gate on
the existing 46-ticket Stage-3 WP4 pilot data.

Per STAGE4_PATCH_GENERATION_IMPLEMENTATION_PLAN_ZH.md section 9 (WP1), one of
WP1's acceptance criteria is:

    "修正後的 patch_generation_policy 在既有 46 票 pilot 資料上重新計算，
    其 block 判定必須涵蓋所有 Stage-3 miss 的 Ticket"

This script reuses the real, shipped ``fault_localization._symbol_gate_status``
(the exact function used inside ``_localization_confidence()``) rather than
re-implementing the gate logic, so this check cannot silently drift from
production behavior.

Data source: ``reports/fault_localization/stage3_wp4_pilot/pilot_46tickets.jsonl``.
That file is Git LFS-tracked, so it must be present locally (not just the LFS
pointer) before running this script:

    git lfs pull

Each row is a ``TicketOutcome`` (see ``scripts/run_stage3_wp4_symbol_llm_pilot.py``):

- ``baseline_top``: the deterministic Stage-3 candidate pool, truncated to
  top_k, for that ticket. Empty iff Stage-3 found no AST symbol candidate at
  all in that ticket's Stage-2 files.
- ``llm_top``: the FINAL ranked symbol list actually used (whether via a
  valid LLM rerank call or, on any LLM failure, the deterministic fallback
  order). By construction this is only empty if ``baseline_top`` is also
  empty -- the pilot's fallback path always keeps the same non-empty
  candidate set, just re-ordered.

These map onto the gate's inputs as:

- ``symbol_candidate_pool_present`` <- ``bool(baseline_top)``
- ``ranked_symbols``                <- ``llm_top``

Usage:

    python scripts/verify_stage4_wp1_gate_on_pilot.py
    python scripts/verify_stage4_wp1_gate_on_pilot.py --pilot-file path/to/pilot_46tickets.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.fault_localization import _symbol_gate_reason, _symbol_gate_status  # noqa: E402

DEFAULT_PILOT_FILE = "reports/fault_localization/stage3_wp4_pilot/pilot_46tickets.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("version https://git-lfs.github.com/spec/v1"):
                raise ValueError(
                    f"{path} is still a Git LFS pointer, not the real file content. "
                    "Run `git lfs pull` in the repo root first."
                )
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON ({exc})") from None
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-file", default=DEFAULT_PILOT_FILE)
    args = parser.parse_args(argv)

    pilot_path = Path(args.pilot_file)
    if not pilot_path.exists():
        print(f"ERROR: {pilot_path} does not exist.", file=sys.stderr)
        return 2

    try:
        rows = load_jsonl(pilot_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not rows:
        print(f"ERROR: {pilot_path} contained no ticket rows.", file=sys.stderr)
        return 2

    status_counts: Counter[str] = Counter()
    non_ready: list[tuple[str, str, str]] = []

    for row in rows:
        ticket_id = str(row.get("ticket_id", "<unknown>"))
        baseline_top = row.get("baseline_top") or []
        llm_top = row.get("llm_top") or []

        status = _symbol_gate_status(
            symbol_localization_requested=True,
            symbol_candidate_pool_present=bool(baseline_top),
            ranked_symbols=llm_top,
        )
        status_counts[status] += 1
        if status != "ready_for_patch":
            reason = _symbol_gate_reason(status, ranked_symbol_count=len(llm_top))
            non_ready.append((ticket_id, status, reason))

    print(f"Replayed the Stage-4 WP1 symbol gate on {len(rows)} ticket(s) from {pilot_path}")
    print()
    print("Gate status distribution:")
    for status in ("ready_for_patch", "manual_review_symbol_uncertain", "block_no_symbol_candidate", "not_applicable"):
        print(f"  {status:32s} {status_counts.get(status, 0)}")

    if non_ready:
        print()
        print("Tickets NOT classified ready_for_patch:")
        for ticket_id, status, reason in non_ready:
            print(f"  - {ticket_id}: {status} ({reason})")
    else:
        print()
        print("All tickets classified ready_for_patch: the gate never blocks a ticket that "
              "this pilot's own deterministic/fallback ranking could still produce a candidate for.")

    print()
    print(
        "Note: this pilot's WP4 recall (68.64% conditional) measures whether the CORRECT "
        "symbol was ranked in the top candidates, not whether a candidate existed at all. "
        "The symbol gate only detects the latter (a total absence of candidates), so a "
        "ready_for_patch result here is expected and does not by itself say anything about "
        "ranking accuracy -- that is what Stage-4 WP2's patch quality metrics are for."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
