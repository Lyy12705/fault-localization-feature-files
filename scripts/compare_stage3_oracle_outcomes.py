"""Compare saved symbol-level oracle outcomes without changing retrieval."""
import argparse
import csv
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def read(path):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        keys = [tuple(row[k] for k in ("ticket_id", "file_path", "symbol_kind", "qualified_name")) for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate gold identity")
        return dict(zip(keys, rows))

    before, after = read(args.baseline), read(args.experiment)
    if before.keys() != after.keys():
        raise ValueError("Oracle inputs do not have the same gold identities")
    outcomes = []
    for key, old in before.items():
        new = after[key]
        for field in ("conditional_eligible", "pool_exact", "stage2_file_reached"):
            if old[field] != new[field]:
                raise ValueError(f"Changed evaluation population: {key}: {field}")
        if old["conditional_eligible"] != "True":
            continue
        was_hit, is_hit = old["top30_exact"] == "True", new["top30_exact"] == "True"
        outcome = "retained_hit" if was_hit and is_hit else "recovered" if is_hit else "lost" if was_hit else "still_missed"
        outcomes.append({**dict(zip(("ticket_id", "file_path", "symbol_kind", "qualified_name"), key)),
                         "baseline": old["classification"], "experiment": new["classification"], "outcome": outcome})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticket_id", "file_path", "symbol_kind", "qualified_name", "baseline", "experiment", "outcome"])
        writer.writeheader()
        writer.writerows(outcomes)
    print(dict(Counter(row["outcome"] for row in outcomes)))
    print("Original ranking misses still missed:", sum(row["baseline"] == "top30_ranking_miss" and row["outcome"] == "still_missed" for row in outcomes))


if __name__ == "__main__":
    main()
