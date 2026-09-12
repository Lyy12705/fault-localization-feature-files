"""Tests for utils.repo_snapshot: everything here uses a local temp git repo
(created with plain `git init`/`git commit`) -- no network access, matching
the rest of this project's offline-test policy.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for import_path in (str(SRC_ROOT), str(PROJECT_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from utils.repo_snapshot import (
    RepoSnapshotError,
    materialize_commit_snapshot,
    read_file_text,
    resolve_repository_path,
)


def _run(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _init_repo_with_one_commit(repo_dir: Path, *, file_name: str = "module.py", file_text: str = "x = 1\n") -> str:
    repo_dir.mkdir(parents=True, exist_ok=True)
    _run(["init"], cwd=repo_dir)
    _run(["config", "user.email", "test@example.com"], cwd=repo_dir)
    _run(["config", "user.name", "Test"], cwd=repo_dir)
    target_file = repo_dir / file_name
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(file_text, encoding="utf-8")
    _run(["add", "."], cwd=repo_dir)
    _run(["commit", "-m", "initial"], cwd=repo_dir)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir), capture_output=True, text=True, check=True)
    return result.stdout.strip()


class ResolveRepositoryPathTests(unittest.TestCase):
    def test_uses_local_repo_path_when_present(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp) / "somewhere" / "checked-out"
            _init_repo_with_one_commit(repo_dir)
            resolved = resolve_repository_path(
                {"local_repo_path": str(repo_dir)}, repo_cache_dir=Path(tmp) / "unused-cache"
            )
            self.assertEqual(resolved, repo_dir.resolve())

    def test_local_repo_path_missing_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(RepoSnapshotError):
                resolve_repository_path(
                    {"local_repo_path": str(Path(tmp) / "does-not-exist")},
                    repo_cache_dir=Path(tmp) / "cache",
                )

    def test_falls_back_to_repo_cache_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            repo_dir = cache_dir / "owner__project"
            _init_repo_with_one_commit(repo_dir)
            resolved = resolve_repository_path({"repo": "owner/project"}, repo_cache_dir=cache_dir)
            self.assertEqual(resolved, repo_dir.resolve())

    def test_missing_cache_without_clone_missing_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(RepoSnapshotError):
                resolve_repository_path(
                    {"repo": "owner/project"}, repo_cache_dir=Path(tmp) / "empty-cache", clone_missing=False
                )

    def test_no_repo_field_and_no_local_path_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(RepoSnapshotError):
                resolve_repository_path({}, repo_cache_dir=Path(tmp) / "cache")


class MaterializeCommitSnapshotTests(unittest.TestCase):
    def test_checks_out_the_requested_commit_detached(self) -> None:
        with TemporaryDirectory() as tmp:
            source_repo = Path(tmp) / "source"
            commit = _init_repo_with_one_commit(source_repo, file_text="value = 1\n")

            snapshot_path = materialize_commit_snapshot(
                source_repo,
                repo="owner/project",
                base_commit=commit,
                snapshot_cache_dir=Path(tmp) / "snapshots",
            )

            self.assertTrue((snapshot_path / "module.py").exists())
            self.assertEqual((snapshot_path / "module.py").read_text(encoding="utf-8"), "value = 1\n")

    def test_reuses_existing_snapshot_at_the_same_commit(self) -> None:
        with TemporaryDirectory() as tmp:
            source_repo = Path(tmp) / "source"
            commit = _init_repo_with_one_commit(source_repo)
            snapshot_cache_dir = Path(tmp) / "snapshots"

            first = materialize_commit_snapshot(
                source_repo, repo="owner/project", base_commit=commit, snapshot_cache_dir=snapshot_cache_dir
            )
            second = materialize_commit_snapshot(
                source_repo, repo="owner/project", base_commit=commit, snapshot_cache_dir=snapshot_cache_dir
            )
            self.assertEqual(first, second)

    def test_short_commit_prefix_resolves_via_rev_parse(self) -> None:
        with TemporaryDirectory() as tmp:
            source_repo = Path(tmp) / "source"
            commit = _init_repo_with_one_commit(source_repo)

            snapshot_path = materialize_commit_snapshot(
                source_repo,
                repo="owner/project",
                base_commit=commit[:10],
                snapshot_cache_dir=Path(tmp) / "snapshots",
            )
            self.assertTrue(snapshot_path.exists())

    def test_unknown_commit_raises_without_fetch_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            source_repo = Path(tmp) / "source"
            _init_repo_with_one_commit(source_repo)

            with self.assertRaises(RepoSnapshotError):
                materialize_commit_snapshot(
                    source_repo,
                    repo="owner/project",
                    base_commit="0" * 40,
                    snapshot_cache_dir=Path(tmp) / "snapshots",
                    fetch_missing_commits=False,
                )

    def test_empty_base_commit_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            source_repo = Path(tmp) / "source"
            _init_repo_with_one_commit(source_repo)
            with self.assertRaises(RepoSnapshotError):
                materialize_commit_snapshot(
                    source_repo, repo="owner/project", base_commit="", snapshot_cache_dir=Path(tmp) / "snapshots"
                )

    def test_not_a_git_checkout_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            not_a_repo = Path(tmp) / "plain-dir"
            not_a_repo.mkdir()
            with self.assertRaises(RepoSnapshotError):
                materialize_commit_snapshot(
                    not_a_repo,
                    repo="owner/project",
                    base_commit="deadbeef",
                    snapshot_cache_dir=Path(tmp) / "snapshots",
                )


class ReadFileTextTests(unittest.TestCase):
    def test_reads_file_content_from_snapshot(self) -> None:
        with TemporaryDirectory() as tmp:
            source_repo = Path(tmp) / "source"
            commit = _init_repo_with_one_commit(source_repo, file_name="pkg/module.py", file_text="def f():\n    pass\n")
            snapshot_path = materialize_commit_snapshot(
                source_repo, repo="owner/project", base_commit=commit, snapshot_cache_dir=Path(tmp) / "snapshots"
            )
            text = read_file_text(snapshot_path, "pkg/module.py")
            self.assertEqual(text, "def f():\n    pass\n")

    def test_missing_file_raises_repo_snapshot_error_not_os_error(self) -> None:
        with TemporaryDirectory() as tmp:
            source_repo = Path(tmp) / "source"
            commit = _init_repo_with_one_commit(source_repo)
            snapshot_path = materialize_commit_snapshot(
                source_repo, repo="owner/project", base_commit=commit, snapshot_cache_dir=Path(tmp) / "snapshots"
            )
            with self.assertRaises(RepoSnapshotError):
                read_file_text(snapshot_path, "does_not_exist.py")

    def test_path_traversal_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            source_repo = Path(tmp) / "source"
            commit = _init_repo_with_one_commit(source_repo)
            snapshot_path = materialize_commit_snapshot(
                source_repo, repo="owner/project", base_commit=commit, snapshot_cache_dir=Path(tmp) / "snapshots"
            )
            with self.assertRaises(RepoSnapshotError):
                read_file_text(snapshot_path, "../../../../etc/passwd")


if __name__ == "__main__":
    unittest.main()
