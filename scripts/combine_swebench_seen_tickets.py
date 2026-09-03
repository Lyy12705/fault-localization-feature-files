#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine previously used SWE-bench ticket files into one unique seen set."
    )
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite seen-ticket artifact: {output}")

    rows_by_id: dict[str, dict[str, Any]] = {}
    source_rows = 0
    for raw_path in args.input:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            source_rows += 1
            instance_id = str(row.get("instance_id") or row.get("ticket_id") or "").strip()
            repository = str(row.get("repo") or "").strip()
            if not instance_id or not repository:
                raise ValueError(f"Seen ticket lacks instance_id/ticket_id or repo: {path}")
            previous = rows_by_id.get(instance_id)
            if previous is not None and str(previous.get("repo") or "") != repository:
                raise ValueError(f"Conflicting repositories for seen ticket {instance_id}")
            rows_by_id[instance_id] = row

    rows = [rows_by_id[key] for key in sorted(rows_by_id)]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "source_rows": source_rows,
                "unique_rows": len(rows),
                "repositories": len({str(row["repo"]) for row in rows}),
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
