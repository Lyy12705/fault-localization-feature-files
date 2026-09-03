#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prefetch unique SWE-bench repositories without opening gold or running evaluation."
    )
    parser.add_argument("--tickets", required=True)
    parser.add_argument("--repo-cache-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Retry an incomplete prefetch manifest; a completed manifest remains write-once.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.max_workers <= 0:
        raise ValueError("max-workers must be positive.")
    tickets_path = Path(args.tickets)
    if not tickets_path.is_file():
        raise FileNotFoundError(tickets_path)
    output_path = Path(args.output)
    if output_path.exists():
        previous = json.loads(output_path.read_text(encoding="utf-8"))
        if not args.resume or previous.get("status") == "ready":
            raise FileExistsError(f"Refusing to overwrite prefetch manifest: {output_path}")
    ticket_rows = read_jsonl(tickets_path)
    repositories = collect_repositories(ticket_rows)
    repository_commits = collect_repository_commits(ticket_rows)
    repository_pull_numbers = collect_repository_pull_numbers(ticket_rows)
    cache_dir = Path(args.repo_cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"[prefetch_started] repositories={len(repositories)} workers={args.max_workers}",
        flush=True,
    )
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                prefetch_repository,
                repository,
                url,
                cache_dir,
                repository_commits[repository],
                repository_pull_numbers[repository],
            ): repository
            for repository, url in repositories.items()
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"[repository_ready] repo={result['repository']} status={result['status']}",
                flush=True,
            )
    failures = [row for row in results if row["status"] == "failed"]
    manifest = {
        "status": "ready" if not failures else "incomplete",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "tickets": portable_path(tickets_path),
        "repository_count": len(repositories),
        "ready_count": len(results) - len(failures),
        "failure_count": len(failures),
        "repo_cache_dir": portable_path(cache_dir),
        "repositories": sorted(results, key=lambda row: row["repository"]),
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
                "repositories": len(repositories),
                "ready": manifest["ready_count"],
                "failures": len(failures),
                "evaluation_started": False,
                "manifest": portable_path(output_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    if failures:
        raise RuntimeError(
            "Repository prefetch failed: "
            + ", ".join(row["repository"] for row in failures)
        )


def collect_repositories(rows: list[dict[str, Any]]) -> dict[str, str]:
    repositories: dict[str, str] = {}
    for row in rows:
        repository = str(row.get("repo") or "").strip()
        if not repository:
            raise ValueError("Every ticket must contain a repository.")
        url = str(row.get("repository_url") or f"https://github.com/{repository}").strip()
        previous = repositories.setdefault(repository, url)
        if previous != url:
            raise ValueError(f"Repository has conflicting URLs: {repository}")
    return dict(sorted(repositories.items()))


def collect_repository_commits(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    commits: dict[str, set[str]] = {}
    for row in rows:
        repository = str(row.get("repo") or "").strip()
        base_commit = str(row.get("base_commit") or "").strip()
        if not repository or not base_commit:
            raise ValueError("Every ticket must contain repo and base_commit.")
        commits.setdefault(repository, set()).add(base_commit)
    return {repository: sorted(values) for repository, values in sorted(commits.items())}


def collect_repository_pull_numbers(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    pull_numbers: dict[str, set[str]] = {}
    for row in rows:
        repository = str(row.get("repo") or "").strip()
        explicit = str(row.get("pull_number") or "").strip()
        ticket = str(row.get("ticket_id") or row.get("instance_id") or "").strip()
        inferred = ticket.rsplit("-", 1)[-1] if "-" in ticket else ""
        number = explicit or (inferred if inferred.isdigit() else "")
        pull_numbers.setdefault(repository, set())
        if number.isdigit():
            pull_numbers[repository].add(number)
    return {
        repository: sorted(values, key=int)
        for repository, values in sorted(pull_numbers.items())
    }


def prefetch_repository(
    repository: str,
    url: str,
    cache_dir: Path,
    required_commits: list[str],
    pull_numbers: list[str],
) -> dict[str, Any]:
    destination = cache_dir / safe_name(repository)
    git_dir = destination / ".git"
    if git_dir.is_dir() and all(commit_exists(destination, commit) for commit in required_commits):
        if not ensure_commit_refs(destination, required_commits):
            return failed_result(repository, url, destination, "Unable to preserve required commit refs.")
        return {
            "repository": repository,
            "repository_url": url,
            "cache_path": portable_path(destination),
            "status": "cached",
            "required_commits": len(required_commits),
        }
    if destination.exists() and not git_dir.is_dir():
        return {
            "repository": repository,
            "repository_url": url,
            "cache_path": portable_path(destination),
            "status": "failed",
            "error": "Destination exists but is not a Git repository.",
        }
    if not git_dir.is_dir():
        destination.mkdir(parents=True)
        init = run_git(["init", str(destination)], cwd=cache_dir)
        if init.returncode != 0:
            return failed_result(repository, url, destination, "Git init failed.")
        remote = run_git(["-C", str(destination), "remote", "add", "origin", url], cwd=cache_dir)
        if remote.returncode != 0:
            return failed_result(repository, url, destination, "Git remote setup failed.")
        run_git(["-C", str(destination), "config", "core.longpaths", "true"], cwd=cache_dir)

    missing = [commit for commit in required_commits if not commit_exists(destination, commit)]
    for commit in missing:
        process = run_git(
            ["-C", str(destination), "fetch", "--no-tags", "--depth=1", "origin", commit],
            cwd=cache_dir,
        )
        if process.returncode != 0:
            # GitHub can reject a direct fetch for an older reachable object when
            # upload-pack does not advertise the SHA. Fetch the branch history as
            # a bounded fallback, then verify the exact required commit again.
            fallback = run_git(
                ["-C", str(destination), "fetch", "--no-tags", "origin"],
                cwd=cache_dir,
            )
            if not commit_exists(destination, commit):
                for pull_number in pull_numbers:
                    run_git(
                        [
                            "-C",
                            str(destination),
                            "-c",
                            "core.longpaths=true",
                            "fetch",
                            "--no-tags",
                            "origin",
                            f"refs/pull/{pull_number}/head:refs/remotes/origin/swebench-pr-{pull_number}",
                        ],
                        cwd=cache_dir,
                    )
                    if commit_exists(destination, commit):
                        break
            if not commit_exists(destination, commit):
                return failed_result(
                    repository,
                    url,
                    destination,
                    f"Git fetch failed for required commit {commit}.",
                )
    ready = sum(commit_exists(destination, commit) for commit in required_commits)
    refs_ready = ensure_commit_refs(destination, required_commits) if ready == len(required_commits) else False
    return {
        "repository": repository,
        "repository_url": url,
        "cache_path": portable_path(destination),
        "status": "fetched_commits" if ready == len(required_commits) and refs_ready else "failed",
        "required_commits": len(required_commits),
        "ready_commits": ready,
    }


def ensure_commit_refs(repository: Path, commits: list[str]) -> bool:
    for commit in commits:
        process = run_git(
            [
                "-C",
                str(repository),
                "update-ref",
                f"refs/heads/swebench-base-{commit[:16]}",
                commit,
            ],
            cwd=repository.parent,
        )
        if process.returncode != 0:
            return False
    return True


def run_git(arguments: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def commit_exists(repository: Path, commit: str) -> bool:
    process = run_git(
        ["-C", str(repository), "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=repository.parent,
    )
    return process.returncode == 0


def failed_result(
    repository: str,
    url: str,
    destination: Path,
    error: str,
) -> dict[str, Any]:
    return {
        "repository": repository,
        "repository_url": url,
        "cache_path": portable_path(destination),
        "status": "failed",
        "error": error,
    }


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
