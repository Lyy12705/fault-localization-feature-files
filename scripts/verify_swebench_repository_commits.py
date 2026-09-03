#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that every ticket base commit exists in the prefetched "
            "repositories without opening sealed gold or running evaluation."
        )
    )
    parser.add_argument("--tickets", required=True)
    parser.add_argument("--repo-cache-dir", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    tickets_path = Path(args.tickets)
    if not tickets_path.is_file():
        raise FileNotFoundError(tickets_path)
    output_path = Path(args.output)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite commit preflight: {output_path}")

    rows = read_jsonl(tickets_path)
    result = verify_base_commits(rows, Path(args.repo_cache_dir).resolve())
    manifest = {
        "status": "ready" if result["missing_count"] == 0 else "incomplete",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "tickets": portable_path(tickets_path),
        "repo_cache_dir": portable_path(Path(args.repo_cache_dir)),
        **result,
        "gold_accessed": False,
        "evaluation_started": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "tickets": manifest["ticket_count"],
                "repositories": manifest["repository_count"],
                "base_commits": manifest["base_commit_count"],
                "reachable": manifest["reachable_count"],
                "missing": manifest["missing_count"],
                "gold_accessed": False,
                "evaluation_started": False,
                "manifest": portable_path(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if manifest["status"] != "ready":
        raise RuntimeError(
            f"Commit preflight found {manifest['missing_count']} unavailable base commits."
        )


def verify_base_commits(
    rows: list[dict[str, Any]],
    cache_dir: Path,
    *,
    commit_exists: Callable[[Path, str], bool] | None = None,
) -> dict[str, Any]:
    checker = commit_exists or git_commit_exists
    references: set[tuple[str, str]] = set()
    ticket_counts: Counter[str] = Counter()
    for row in rows:
        repository = str(row.get("repo") or "").strip()
        base_commit = str(row.get("base_commit") or "").strip()
        if not repository or not base_commit:
            raise ValueError("Every ticket must contain repo and base_commit.")
        references.add((repository, base_commit))
        ticket_counts[repository] += 1

    per_repository: list[dict[str, Any]] = []
    total_reachable = 0
    total_missing = 0
    for repository in sorted(ticket_counts):
        repository_path = cache_dir / safe_name(repository)
        repository_references = sorted(
            commit for repo, commit in references if repo == repository
        )
        if not (repository_path / ".git").is_dir():
            reachable = 0
            missing = len(repository_references)
            repository_status = "repository_missing"
        else:
            reachable = sum(
                checker(repository_path, commit) for commit in repository_references
            )
            missing = len(repository_references) - reachable
            repository_status = "ready" if missing == 0 else "commits_missing"
        total_reachable += reachable
        total_missing += missing
        per_repository.append(
            {
                "repository": repository,
                "ticket_count": ticket_counts[repository],
                "base_commit_count": len(repository_references),
                "reachable_count": reachable,
                "missing_count": missing,
                "status": repository_status,
            }
        )

    return {
        "ticket_count": len(rows),
        "repository_count": len(ticket_counts),
        "base_commit_count": len(references),
        "reachable_count": total_reachable,
        "missing_count": total_missing,
        "repositories": per_repository,
    }


def git_commit_exists(repository_path: Path, commit: str) -> bool:
    process = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository_path}",
            "-C",
            str(repository_path),
            "cat-file",
            "-e",
            f"{commit}^{{commit}}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return process.returncode == 0


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


def safe_name(value: str) -> str:
    normalized = value.replace("/", "__").replace("\\", "__").replace(":", "_")
    return "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in normalized
    )


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    main()
