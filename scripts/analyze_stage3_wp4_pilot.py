"""Paired-outcome and bootstrap-CI analysis for a WP4 pilot output file.

Consumes the per-ticket JSONL produced by run_stage3_wp4_symbol_llm_pilot.py
and reports, for each K in {1,3,5}: paired improved/unchanged/worsened/
both-miss ticket counts, and a 2,000-resample percentile bootstrap 95% CI on
the mean (LLM - baseline) delta - following the same convention already used
in scripts/evaluate_fault_localization.py (_bootstrap_mean_ci).

This is a pilot-tier analysis (single development set, n<200, no
repo-disjoint holdout) - it supports a G5 adoption/rejection call but is not
itself the formal G4 validation described in the plan's section 9.1.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def bootstrap_mean_ci(values: list[float], *, samples: int = 2000, seed: int = 42) -> dict[str, float]:
    if not values:
        return {"lower": 0.0, "upper": 0.0}
    if len(values) == 1:
        value = float(values[0])
        return {"lower": value, "upper": value}
    generator = random.Random(seed)
    size = len(values)
    means = sorted(
        sum(values[generator.randrange(size)] for _ in range(size)) / size
        for _ in range(samples)
    )
    lower_index = max(0, int(0.025 * samples) - 1)
    upper_index = min(samples - 1, int(0.975 * samples))
    return {"lower": round(float(means[lower_index]), 6), "upper": round(float(means[upper_index]), 6)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pilot_output")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    rows = [r for r in load_jsonl(args.pilot_output) if r.get("eligible")]
    ks = ("1", "3", "5")
    report: dict[str, Any] = {
        "ticket_count": len(rows),
        "llm_valid_count": sum(1 for r in rows if r["llm_valid"]),
        "llm_fallback_count": sum(1 for r in rows if not r["llm_valid"]),
        "fallback_ticket_ids": [r["ticket_id"] for r in rows if not r["llm_valid"]],
        "per_k": {},
    }

    for k in ks:
        deltas = []
        improved = unchanged_hit = worsened = both_miss = 0
        for row in rows:
            b = row["baseline_eval"]["exact"]["hit_at"][k]
            l = row["llm_eval"]["exact"]["hit_at"][k]
            deltas.append(float(l - b))
            if l == b == 1:
                unchanged_hit += 1
            elif l == b == 0:
                both_miss += 1
            elif l > b:
                improved += 1
            else:
                worsened += 1
        report["per_k"][k] = {
            "baseline_hit_rate": sum(row["baseline_eval"]["exact"]["hit_at"][k] for row in rows) / len(rows),
            "llm_hit_rate": sum(row["llm_eval"]["exact"]["hit_at"][k] for row in rows) / len(rows),
            "mean_delta": sum(deltas) / len(deltas),
            "delta_95ci": bootstrap_mean_ci(deltas),
            "paired_outcomes": {
                "improved": improved,
                "unchanged_hit": unchanged_hit,
                "worsened": worsened,
                "both_miss": both_miss,
            },
        }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
