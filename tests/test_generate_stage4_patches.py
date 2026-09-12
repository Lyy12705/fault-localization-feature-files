"""Tests for scripts.generate_stage4_patches (Stage-4 WP2 batch pipeline).

Uses a fake OllamaClient (no real Ollama needed) and a local temp git repo
(no network needed) -- matches the offline-test policy the rest of this
project's batch-script tests already follow.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.generate_stage4_patches import (
    TICKET_DESCRIPTION_FIELDS,
    SymbolRangeUnresolvedError,
    TICKET_GROUND_TRUTH_FIELDS,
    _ticket_comment_text,
    generate_patch_candidates,
    is_conditional_eligible,
    load_ticket_id_allowlist,
    print_summary,
    run_batch,
    select_target_symbols,
)


def _run(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _init_repo_with_file(repo_dir: Path, file_name: str, file_text: str) -> str:
    repo_dir.mkdir(parents=True, exist_ok=True)
    _run(["init"], cwd=repo_dir)
    _run(["config", "user.email", "test@example.com"], cwd=repo_dir)
    _run(["config", "user.name", "Test"], cwd=repo_dir)
    target = repo_dir / file_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(file_text, encoding="utf-8")
    _run(["add", "."], cwd=repo_dir)
    _run(["commit", "-m", "initial"], cwd=repo_dir)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir), capture_output=True, text=True, check=True)
    return result.stdout.strip()


FILE_TEXT = (
    "def to_int(x):\n"
    "    return int(x)\n"
    "\n"
    "\n"
    "def clamp(value, low, high):\n"
    "    pass\n"
    "\n"
    "\n"
    "def main():\n"
    "    print(clamp(15, 0, 10))\n"
)

CLAMP_SYMBOL = {
    "rank": 1,
    "file_path": "pkg/module.py",
    "symbol_qualified_name": "clamp",
    "symbol_name": "clamp",
    "symbol_kind": "function",
    "start_line": 5,
    "end_line": 6,
    "code_text": "def clamp(value, low, high):\n    pass\n",
}

DEFAULT_CONFIG = {
    "prompt_version": "patchgen-fim-v1",
    "fim": {
        "prefix_token_budget": 2048,
        "suffix_token_budget": 2048,
        "num_predict_headroom": 2.0,
        "min_num_predict": 256,
        "max_num_predict": 4096,
        "use_native_suffix": True,
    },
    "sampling": {"temperatures": [0.2, 0.4]},
    "symbol_selection": {"symbol_topk": 1},
}


class FakeOllamaClient:
    """Returns canned completions in order; records every call it received."""

    def __init__(self, responses: list[str], *, fim_model: str = "codellama:7b-code") -> None:
        self._responses = list(responses)
        self.fim_model = fim_model
        self.calls: list[dict[str, object]] = []

    def generate_fim(self, prefix, suffix, *, temperature=0.2, num_predict=256, use_native_suffix=True):
        self.calls.append(
            {
                "prefix": prefix,
                "suffix": suffix,
                "temperature": temperature,
                "num_predict": num_predict,
                "use_native_suffix": use_native_suffix,
            }
        )
        if not self._responses:
            raise AssertionError("FakeOllamaClient ran out of canned responses")
        return self._responses.pop(0)


class EligibilityTests(unittest.TestCase):
    def test_ticket_with_ranked_symbols_is_eligible(self) -> None:
        self.assertTrue(is_conditional_eligible({"stage3_ranked_symbols": [CLAMP_SYMBOL]}))

    def test_ticket_without_ranked_symbols_is_not_eligible(self) -> None:
        self.assertFalse(is_conditional_eligible({"stage3_ranked_symbols": []}))
        self.assertFalse(is_conditional_eligible({}))

    def test_select_target_symbols_respects_topk(self) -> None:
        row = {"stage3_ranked_symbols": [CLAMP_SYMBOL, {**CLAMP_SYMBOL, "rank": 2}]}
        self.assertEqual(len(select_target_symbols(row, symbol_topk=1)), 1)
        self.assertEqual(len(select_target_symbols(row, symbol_topk=2)), 2)
        self.assertEqual(select_target_symbols(row, symbol_topk=0), [])


class GeneratePatchCandidatesTests(unittest.TestCase):
    def test_correct_completion_is_marked_applied_clean(self) -> None:
        client = FakeOllamaClient(["def clamp(value, low, high):\n    return max(min(value, high), low)\n"])
        records = generate_patch_candidates(
            client=client,
            ticket_id="org__proj-1",
            repo="org/proj",
            base_commit="deadbeef",
            file_path="pkg/module.py",
            file_text=FILE_TEXT,
            symbol=CLAMP_SYMBOL,
            temperatures=[0.2],
            prefix_token_budget=2048,
            suffix_token_budget=2048,
            num_predict_headroom=2.0,
            min_num_predict=256,
            max_num_predict=4096,
            use_native_suffix=True,
            ticket_comment="",
            prompt_version="patchgen-fim-v1",
            model_digest="placeholder:codellama:7b-code",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].apply_status, "applied_clean")
        self.assertTrue(records[0].syntax_valid)
        self.assertEqual(records[0].ticket_id, "org__proj-1")
        self.assertEqual(records[0].sampling_index, 0)
        self.assertEqual(records[0].temperature, 0.2)

    def test_one_sample_per_temperature(self) -> None:
        client = FakeOllamaClient(
            [
                "def clamp(value, low, high):\n    return max(min(value, high), low)\n",
                "def clamp(value, low, high):\n    return min(max(value, low), high)\n",
            ]
        )
        records = generate_patch_candidates(
            client=client,
            ticket_id="org__proj-1",
            repo="org/proj",
            base_commit="deadbeef",
            file_path="pkg/module.py",
            file_text=FILE_TEXT,
            symbol=CLAMP_SYMBOL,
            temperatures=[0.2, 0.6],
            prefix_token_budget=2048,
            suffix_token_budget=2048,
            num_predict_headroom=2.0,
            min_num_predict=256,
            max_num_predict=4096,
            use_native_suffix=True,
            ticket_comment="",
            prompt_version="patchgen-fim-v1",
            model_digest="placeholder:codellama:7b-code",
        )
        self.assertEqual([r.temperature for r in records], [0.2, 0.6])
        self.assertEqual([r.sampling_index for r in records], [0, 1])
        self.assertEqual(len(client.calls), 2)

    def test_degenerate_completion_that_deletes_the_symbol_is_apply_failed(self) -> None:
        """The real WP1 false-positive shape: a bare call expression that
        gets silently absorbed into the preceding function's body. Must be
        caught by apply_patch_and_verify_symbol, not left as applied_clean."""

        client = FakeOllamaClient(["    print(clamp(15, 10, 20))\n"])
        records = generate_patch_candidates(
            client=client,
            ticket_id="org__proj-1",
            repo="org/proj",
            base_commit="deadbeef",
            file_path="pkg/module.py",
            file_text=FILE_TEXT,
            symbol=CLAMP_SYMBOL,
            temperatures=[0.2],
            prefix_token_budget=2048,
            suffix_token_budget=2048,
            num_predict_headroom=2.0,
            min_num_predict=256,
            max_num_predict=4096,
            use_native_suffix=True,
            ticket_comment="",
            prompt_version="patchgen-fim-v1",
            model_digest="placeholder:codellama:7b-code",
        )
        self.assertEqual(records[0].apply_status, "apply_failed")

    def test_ticket_comment_is_appended_to_the_prefix_sent_to_the_model(self) -> None:
        client = FakeOllamaClient(["def clamp(value, low, high):\n    return value\n"])
        generate_patch_candidates(
            client=client,
            ticket_id="org__proj-1",
            repo="org/proj",
            base_commit="deadbeef",
            file_path="pkg/module.py",
            file_text=FILE_TEXT,
            symbol=CLAMP_SYMBOL,
            temperatures=[0.2],
            prefix_token_budget=2048,
            suffix_token_budget=2048,
            num_predict_headroom=2.0,
            min_num_predict=256,
            max_num_predict=4096,
            use_native_suffix=True,
            ticket_comment="clamp should clip value into [low, high]",
            prompt_version="patchgen-fim-v1",
            model_digest="placeholder:codellama:7b-code",
        )
        self.assertIn("clamp should clip value into", client.calls[0]["prefix"])


class RunBatchTests(unittest.TestCase):
    def test_end_to_end_over_a_local_snapshot_repo(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_cache_dir = Path(tmp) / "repos"
            source_repo = repo_cache_dir / "org__proj"
            commit = _init_repo_with_file(source_repo, "pkg/module.py", FILE_TEXT)

            predictions_rows = [
                {
                    "ticket_id": "org__proj-1",
                    "repo": "org/proj",
                    "base_commit": commit,
                    "stage3_ranked_symbols": [CLAMP_SYMBOL],
                }
            ]
            client = FakeOllamaClient(["def clamp(value, low, high):\n    return max(min(value, high), low)\n"])

            patch_records, failures, status_counts = run_batch(
                predictions_rows=predictions_rows,
                tickets_by_id={},
                client=client,
                config=DEFAULT_CONFIG | {"sampling": {"temperatures": [0.2]}},
                repo_cache_dir=repo_cache_dir,
                snapshot_cache_dir=Path(tmp) / "snapshots",
                symbol_topk=1,
                clone_missing=False,
                fetch_missing_commits=False,
                model_digest="placeholder:codellama:7b-code",
                limit=None,
            )

            self.assertEqual(len(patch_records), 1)
            self.assertEqual(patch_records[0].apply_status, "applied_clean")
            self.assertEqual(failures, [])
            self.assertEqual(status_counts["applied_clean"], 1)

    def test_ineligible_ticket_is_skipped_without_any_fim_call(self) -> None:
        with TemporaryDirectory() as tmp:
            predictions_rows = [{"ticket_id": "org__proj-2", "repo": "org/proj", "base_commit": "x", "stage3_ranked_symbols": []}]
            client = FakeOllamaClient([])

            patch_records, failures, status_counts = run_batch(
                predictions_rows=predictions_rows,
                tickets_by_id={},
                client=client,
                config=DEFAULT_CONFIG,
                repo_cache_dir=Path(tmp) / "repos",
                snapshot_cache_dir=Path(tmp) / "snapshots",
                symbol_topk=1,
                clone_missing=False,
                fetch_missing_commits=False,
                model_digest="placeholder",
                limit=None,
            )
            self.assertEqual(patch_records, [])
            self.assertEqual(failures, [])
            self.assertEqual(client.calls, [])

    def test_missing_repo_cache_is_recorded_as_a_failure_not_raised(self) -> None:
        with TemporaryDirectory() as tmp:
            predictions_rows = [
                {
                    "ticket_id": "org__proj-3",
                    "repo": "org/missing",
                    "base_commit": "deadbeef",
                    "stage3_ranked_symbols": [CLAMP_SYMBOL],
                }
            ]
            client = FakeOllamaClient([])

            patch_records, failures, status_counts = run_batch(
                predictions_rows=predictions_rows,
                tickets_by_id={},
                client=client,
                config=DEFAULT_CONFIG,
                repo_cache_dir=Path(tmp) / "repos",
                snapshot_cache_dir=Path(tmp) / "snapshots",
                symbol_topk=1,
                clone_missing=False,
                fetch_missing_commits=False,
                model_digest="placeholder",
                limit=None,
            )
            self.assertEqual(patch_records, [])
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["reason"], "repo_resolution_failed")
            self.assertEqual(status_counts["repo_resolution_failed"], 1)

    def test_limit_caps_the_number_of_eligible_tickets_processed(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_cache_dir = Path(tmp) / "repos"
            source_repo = repo_cache_dir / "org__proj"
            commit = _init_repo_with_file(source_repo, "pkg/module.py", FILE_TEXT)

            predictions_rows = [
                {
                    "ticket_id": f"org__proj-{i}",
                    "repo": "org/proj",
                    "base_commit": commit,
                    "stage3_ranked_symbols": [CLAMP_SYMBOL],
                }
                for i in range(3)
            ]
            client = FakeOllamaClient(
                ["def clamp(value, low, high):\n    return max(min(value, high), low)\n"] * 1
            )

            patch_records, _, _ = run_batch(
                predictions_rows=predictions_rows,
                tickets_by_id={},
                client=client,
                config=DEFAULT_CONFIG | {"sampling": {"temperatures": [0.2]}},
                repo_cache_dir=repo_cache_dir,
                snapshot_cache_dir=Path(tmp) / "snapshots",
                symbol_topk=1,
                clone_missing=False,
                fetch_missing_commits=False,
                model_digest="placeholder",
                limit=1,
            )
            self.assertEqual(len(patch_records), 1)

    def test_unsupported_language_symbol_is_skipped_and_recorded(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_cache_dir = Path(tmp) / "repos"
            source_repo = repo_cache_dir / "org__proj"
            commit = _init_repo_with_file(source_repo, "pkg/module.ts", "export const x = 1;\n")

            ts_symbol = {**CLAMP_SYMBOL, "file_path": "pkg/module.ts"}
            predictions_rows = [
                {
                    "ticket_id": "org__proj-4",
                    "repo": "org/proj",
                    "base_commit": commit,
                    "stage3_ranked_symbols": [ts_symbol],
                }
            ]
            client = FakeOllamaClient([])

            patch_records, failures, status_counts = run_batch(
                predictions_rows=predictions_rows,
                tickets_by_id={},
                client=client,
                config=DEFAULT_CONFIG,
                repo_cache_dir=repo_cache_dir,
                snapshot_cache_dir=Path(tmp) / "snapshots",
                symbol_topk=1,
                clone_missing=False,
                fetch_missing_commits=False,
                model_digest="placeholder",
                limit=None,
            )
            self.assertEqual(patch_records, [])
            self.assertEqual(failures[0]["reason"], "unsupported_language")
            self.assertEqual(client.calls, [])


class ChunkRangeResolutionTests(unittest.TestCase):
    """Stage-3 hands over the retrieval CHUNK's line range, not the symbol's.

    The pipeline must re-derive the definition's real boundaries from source
    before patching; using the chunk range targets a fragment of several
    definitions and cannot succeed (real 0/3 run, astropy__astropy-13073).
    """

    def test_patch_targets_the_real_definition_not_the_chunk_range(self) -> None:
        client = FakeOllamaClient(["def clamp(value, low, high):\n    return max(min(value, high), low)\n"])
        # Chunk-style hint: starts 3 lines above the def, ends mid-body.
        chunk_shaped_symbol = {**CLAMP_SYMBOL, "start_line": 2, "end_line": 6}

        records = generate_patch_candidates(
            client=client, ticket_id="t", repo="r", base_commit="c", file_path="pkg/module.py",
            file_text=FILE_TEXT, symbol=chunk_shaped_symbol, temperatures=[0.2],
            prefix_token_budget=2048, suffix_token_budget=2048,
            num_predict_headroom=2.0, min_num_predict=256, max_num_predict=4096,
            use_native_suffix=True, ticket_comment="", prompt_version="v", model_digest="d",
        )

        # The prefix must end at the real definition's start (line 5), so it
        # still contains all of to_int and NOT the "def clamp" line itself.
        prefix = str(client.calls[0]["prefix"])
        self.assertIn("def to_int(x):", prefix)
        self.assertNotIn("def clamp", prefix)
        # And the patch applies cleanly against the true boundaries.
        self.assertEqual(records[0].apply_status, "applied_clean")
        self.assertIn("return max(min(value, high), low)", records[0].diff_unified)

    def test_unresolvable_symbol_is_skipped_not_patched_against_the_chunk_range(self) -> None:
        client = FakeOllamaClient([])
        missing_symbol = {**CLAMP_SYMBOL, "symbol_qualified_name": "gone", "symbol_name": "gone"}

        with self.assertRaises(SymbolRangeUnresolvedError):
            generate_patch_candidates(
                client=client, ticket_id="t", repo="r", base_commit="c", file_path="pkg/module.py",
                file_text=FILE_TEXT, symbol=missing_symbol, temperatures=[0.2],
                prefix_token_budget=2048, suffix_token_budget=2048,
                num_predict_headroom=2.0, min_num_predict=256, max_num_predict=4096,
                use_native_suffix=True, ticket_comment="", prompt_version="v", model_digest="d",
            )
        self.assertEqual(client.calls, [], "no FIM call should be made for an unresolvable target")

    def test_run_batch_records_unresolvable_symbols_as_their_own_reason(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_cache_dir = Path(tmp) / "repos"
            source_repo = repo_cache_dir / "org__proj"
            commit = _init_repo_with_file(source_repo, "pkg/module.py", FILE_TEXT)

            predictions_rows = [{
                "ticket_id": "org__proj-1", "repo": "org/proj", "base_commit": commit,
                "stage3_ranked_symbols": [{**CLAMP_SYMBOL, "symbol_qualified_name": "gone", "symbol_name": "gone"}],
            }]
            client = FakeOllamaClient([])

            patch_records, failures, status_counts = run_batch(
                predictions_rows=predictions_rows, tickets_by_id={}, client=client,
                config=DEFAULT_CONFIG | {"sampling": {"temperatures": [0.2]}},
                repo_cache_dir=repo_cache_dir, snapshot_cache_dir=Path(tmp) / "snapshots",
                symbol_topk=1, clone_missing=False, fetch_missing_commits=False,
                model_digest="placeholder", limit=None,
            )

            self.assertEqual(patch_records, [])
            self.assertEqual(failures[0]["reason"], "symbol_range_unresolved")
            self.assertEqual(status_counts["symbol_range_unresolved"], 1)
            self.assertEqual(status_counts["fim_call_failed"], 0)


class TicketContextLeakTests(unittest.TestCase):
    """The real ticket source file carries the developer's gold patch
    alongside the bug description. Plan section 4.1 forbids that patch from
    reaching any LLM prompt; a leak would silently invalidate every Stage-4
    number while making the results look BETTER, so it is tested, not assumed.
    """

    def test_gold_patch_and_test_names_never_reach_the_prompt(self) -> None:
        ticket_row = {
            "ticket_id": "org__proj-1",
            "bug_report": "clamp() does not clip its input.",
            # Everything below is ground truth and must not be sent:
            "patch": "--- a/pkg/module.py\n+++ b/pkg/module.py\n@@\n-    pass\n+    return max(min(value, high), low)\n",
            "fail_to_pass": ["tests/test_clamp.py::test_clips"],
            "pass_to_pass": ["tests/test_other.py::test_unrelated"],
            "hints_text": "The fix is to use max(min(...)).",
        }
        comment = _ticket_comment_text("org__proj-1", {"org__proj-1": ticket_row})

        self.assertIn("clamp() does not clip", comment)
        for forbidden in ("max(min(", "fail_to_pass", "test_clips", "--- a/", "The fix is"):
            self.assertNotIn(forbidden, comment, f"ground truth leaked into the prompt: {forbidden!r}")

    def test_description_field_names_and_ground_truth_field_names_never_overlap(self) -> None:
        self.assertEqual(set(TICKET_DESCRIPTION_FIELDS) & set(TICKET_GROUND_TRUTH_FIELDS), set())

    def test_end_to_end_prompt_contains_no_ground_truth(self) -> None:
        client = FakeOllamaClient(["def clamp(value, low, high):\n    return value\n"])
        generate_patch_candidates(
            client=client,
            ticket_id="org__proj-1",
            repo="org/proj",
            base_commit="deadbeef",
            file_path="pkg/module.py",
            file_text=FILE_TEXT,
            symbol=CLAMP_SYMBOL,
            temperatures=[0.2],
            prefix_token_budget=2048,
            suffix_token_budget=2048,
            num_predict_headroom=2.0,
            min_num_predict=256,
            max_num_predict=4096,
            use_native_suffix=True,
            ticket_comment=_ticket_comment_text(
                "org__proj-1",
                {
                    "org__proj-1": {
                        "bug_report": "clamp() does not clip its input.",
                        "patch": "+    return max(min(value, high), low)",
                    }
                },
            ),
            prompt_version="patchgen-fim-v1",
            model_digest="placeholder",
        )
        sent = str(client.calls[0]["prefix"]) + str(client.calls[0]["suffix"])
        self.assertIn("clamp() does not clip", sent)
        self.assertNotIn("max(min(", sent)


class NumPredictSizingTests(unittest.TestCase):
    def test_budget_is_sized_to_the_target_symbol_not_a_fixed_constant(self) -> None:
        """A large target must request a larger budget than a small one."""

        big_file = "def head():\n    pass\n\n\n" + "def big(x):\n" + ("    x += 1\n" * 200) + "\n\ndef tail():\n    pass\n"
        big_symbol = {
            "file_path": "pkg/module.py",
            "symbol_qualified_name": "big",
            "symbol_name": "big",
            "symbol_kind": "function",
            "start_line": 5,
            "end_line": 205,
        }
        big_client = FakeOllamaClient(["def big(x):\n    return x\n"])
        generate_patch_candidates(
            client=big_client, ticket_id="t", repo="r", base_commit="c", file_path="pkg/module.py",
            file_text=big_file, symbol=big_symbol, temperatures=[0.2],
            prefix_token_budget=2048, suffix_token_budget=2048,
            num_predict_headroom=2.0, min_num_predict=256, max_num_predict=4096,
            use_native_suffix=True, ticket_comment="", prompt_version="v", model_digest="d",
        )

        small_client = FakeOllamaClient(["def clamp(value, low, high):\n    return value\n"])
        generate_patch_candidates(
            client=small_client, ticket_id="t", repo="r", base_commit="c", file_path="pkg/module.py",
            file_text=FILE_TEXT, symbol=CLAMP_SYMBOL, temperatures=[0.2],
            prefix_token_budget=2048, suffix_token_budget=2048,
            num_predict_headroom=2.0, min_num_predict=256, max_num_predict=4096,
            use_native_suffix=True, ticket_comment="", prompt_version="v", model_digest="d",
        )

        self.assertGreater(big_client.calls[0]["num_predict"], small_client.calls[0]["num_predict"])
        self.assertEqual(small_client.calls[0]["num_predict"], 256)  # floor for a tiny symbol


class TicketIdAllowlistTests(unittest.TestCase):
    def test_reads_ticket_ids_from_jsonl_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "pilot_46tickets.jsonl"
            path.write_text(
                json.dumps({"ticket_id": "a-1", "baseline_top": []}) + "\n"
                + json.dumps({"ticket_id": "a-2", "baseline_top": []}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(load_ticket_id_allowlist(path), {"a-1", "a-2"})

    def test_reads_ticket_ids_from_plain_text_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ids.txt"
            path.write_text("a-1\na-2\n\n", encoding="utf-8")
            self.assertEqual(load_ticket_id_allowlist(path), {"a-1", "a-2"})

    def test_run_batch_restricts_to_the_allowlist_before_limit_and_eligibility(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_cache_dir = Path(tmp) / "repos"
            source_repo = repo_cache_dir / "org__proj"
            commit = _init_repo_with_file(source_repo, "pkg/module.py", FILE_TEXT)

            predictions_rows = [
                {"ticket_id": "org__proj-1", "repo": "org/proj", "base_commit": commit, "stage3_ranked_symbols": [CLAMP_SYMBOL]},
                {"ticket_id": "org__proj-2", "repo": "org/proj", "base_commit": commit, "stage3_ranked_symbols": [CLAMP_SYMBOL]},
            ]
            client = FakeOllamaClient(["def clamp(value, low, high):\n    return max(min(value, high), low)\n"])

            patch_records, failures, _ = run_batch(
                predictions_rows=predictions_rows,
                tickets_by_id={},
                client=client,
                config=DEFAULT_CONFIG | {"sampling": {"temperatures": [0.2]}},
                repo_cache_dir=repo_cache_dir,
                snapshot_cache_dir=Path(tmp) / "snapshots",
                symbol_topk=1,
                clone_missing=False,
                fetch_missing_commits=False,
                model_digest="placeholder",
                limit=None,
                ticket_id_allowlist={"org__proj-2"},
            )
            self.assertEqual(len(patch_records), 1)
            self.assertEqual(patch_records[0].ticket_id, "org__proj-2")
            self.assertEqual(failures, [])


class PrintSummaryTests(unittest.TestCase):
    def test_does_not_raise_on_empty_run(self) -> None:
        # Regression guard: must not divide by zero when nothing was generated.
        print_summary({}, [], total_candidates=0)


if __name__ == "__main__":
    unittest.main()
