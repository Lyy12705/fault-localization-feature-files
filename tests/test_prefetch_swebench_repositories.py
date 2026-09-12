from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.prefetch_swebench_repositories import (
    collect_repositories,
    collect_repository_commits,
    collect_repository_pull_numbers,
    ensure_origin_remote,
    safe_name,
)


def _git(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", check=True
    )
    return result.stdout.strip()


class EnsureOriginRemoteTest(unittest.TestCase):
    """Regression tests for the half-initialized-cache failure (2026-09-12).

    An interrupted run can leave a repository directory that HAS .git but has
    no origin remote. Repository setup must therefore be idempotent: keying
    "already set up?" off .git alone made every later run fail instantly with
    "fatal: 'origin' does not appear to be a git repository", with no way to
    recover short of deleting the cache by hand.
    """

    def test_adds_origin_when_git_init_ran_but_remote_add_never_did(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            destination = cache_dir / "psf__requests"
            destination.mkdir()
            _git(["init", str(destination)], cwd=cache_dir)

            ok, error = ensure_origin_remote(destination, "https://github.com/psf/requests", cache_dir=cache_dir)

            self.assertTrue(ok, error)
            self.assertEqual(
                _git(["-C", str(destination), "remote", "get-url", "origin"], cwd=cache_dir),
                "https://github.com/psf/requests",
            )

    def test_is_idempotent_when_origin_is_already_correct(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            destination = cache_dir / "psf__requests"
            destination.mkdir()
            _git(["init", str(destination)], cwd=cache_dir)
            _git(["-C", str(destination), "remote", "add", "origin", "https://github.com/psf/requests"], cwd=cache_dir)

            ok, error = ensure_origin_remote(destination, "https://github.com/psf/requests", cache_dir=cache_dir)

            self.assertTrue(ok, error)
            self.assertEqual(
                _git(["-C", str(destination), "remote", "get-url", "origin"], cwd=cache_dir),
                "https://github.com/psf/requests",
            )

    def test_corrects_an_origin_pointing_at_the_wrong_url(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            destination = cache_dir / "psf__requests"
            destination.mkdir()
            _git(["init", str(destination)], cwd=cache_dir)
            _git(["-C", str(destination), "remote", "add", "origin", "https://github.com/wrong/repo"], cwd=cache_dir)

            ok, error = ensure_origin_remote(destination, "https://github.com/psf/requests", cache_dir=cache_dir)

            self.assertTrue(ok, error)
            self.assertEqual(
                _git(["-C", str(destination), "remote", "get-url", "origin"], cwd=cache_dir),
                "https://github.com/psf/requests",
            )


class PrefetchSWEbenchRepositoriesTest(unittest.TestCase):
    def test_collects_explicit_or_inferred_pull_numbers(self) -> None:
        rows = [
            {"repo": "org/a", "ticket_id": "org__a-12", "pull_number": ""},
            {"repo": "org/a", "ticket_id": "org__a-13", "pull_number": "99"},
            {"repo": "org/b", "ticket_id": "not-numeric"},
        ]
        self.assertEqual(
            collect_repository_pull_numbers(rows),
            {"org/a": ["12", "99"], "org/b": []},
        )

    def test_collects_unique_required_commits_by_repository(self) -> None:
        rows = [
            {"repo": "org/a", "base_commit": "aaa"},
            {"repo": "org/a", "base_commit": "bbb"},
            {"repo": "org/a", "base_commit": "aaa"},
            {"repo": "org/b", "base_commit": "ccc"},
        ]
        self.assertEqual(
            collect_repository_commits(rows),
            {"org/a": ["aaa", "bbb"], "org/b": ["ccc"]},
        )

    def test_collects_unique_repositories_without_gold(self) -> None:
        repositories = collect_repositories(
            [
                {"repo": "owner/repo", "repository_url": "https://github.com/owner/repo"},
                {"repo": "owner/repo", "repository_url": "https://github.com/owner/repo"},
                {"repo": "other/project"},
            ]
        )
        self.assertEqual(len(repositories), 2)
        self.assertEqual(repositories["other/project"], "https://github.com/other/project")

    def test_safe_name_matches_runner_layout(self) -> None:
        self.assertEqual(safe_name("owner/repo"), "owner__repo")

    def test_rejects_conflicting_repository_urls(self) -> None:
        with self.assertRaisesRegex(ValueError, "conflicting URLs"):
            collect_repositories(
                [
                    {"repo": "owner/repo", "repository_url": "https://example.com/a"},
                    {"repo": "owner/repo", "repository_url": "https://example.com/b"},
                ]
            )


if __name__ == "__main__":
    unittest.main()
