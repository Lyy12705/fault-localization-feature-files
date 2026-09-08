from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import run_stage3_wp4_symbol_llm_pilot as wp4  # noqa: E402


def make_candidate(rank: int, file_path: str = "pkg/mod.py", qname: str = "foo") -> dict:
    return {
        "rank": rank,
        "file_path": file_path,
        "symbol_qualified_name": qname,
        "symbol_kind": "function",
        "start_line": 1,
        "end_line": 10,
        "chunk_id": f"{file_path}:1-10:{qname}",
        "code_text": "def foo():\n    pass\n",
    }


class FakeClient:
    def __init__(self, response: dict | None = None, raise_error: Exception | None = None):
        self.response = response
        self.raise_error = raise_error
        self.last_prompt = None
        self.last_schema = None

    def generate_json_with_schema(self, prompt, schema):
        self.last_prompt = prompt
        self.last_schema = schema
        if self.raise_error is not None:
            raise self.raise_error
        return self.response


class BuildShortlistTests(unittest.TestCase):
    def test_shortlist_is_a_permutation_not_rank_order(self):
        candidates = [make_candidate(i) for i in range(1, 11)]
        entries = wp4.build_shortlist(candidates, k=10, seed=42)
        self.assertEqual({e.opaque_id for e in entries}, {f"C{i}" for i in range(1, 11)})
        # The candidate objects assigned to C1..C10 must be a permutation of
        # the input, and for this seed must NOT equal the identity order.
        assigned_ranks = [e.candidate["rank"] for e in entries]
        self.assertEqual(sorted(assigned_ranks), list(range(1, 11)))
        self.assertNotEqual(assigned_ranks, list(range(1, 11)))

    def test_shortlist_is_deterministic_for_fixed_seed(self):
        candidates = [make_candidate(i) for i in range(1, 11)]
        first = [e.candidate["rank"] for e in wp4.build_shortlist(candidates, 10, seed=7)]
        second = [e.candidate["rank"] for e in wp4.build_shortlist(candidates, 10, seed=7)]
        self.assertEqual(first, second)


class PromptNoLeakageTests(unittest.TestCase):
    def test_prompt_never_contains_retrieval_score_or_rank_fields(self):
        candidates = [make_candidate(i) for i in range(1, 4)]
        entries = wp4.build_shortlist(candidates, k=3, seed=1)
        prompt = wp4.build_prompt("some bug report", entries)
        self.assertNotIn('"rank"', prompt)
        self.assertNotIn("retrieval_score", prompt)
        self.assertNotIn("stage2_file_score", prompt)
        # Opaque ids and code must be present.
        for entry in entries:
            self.assertIn(entry.opaque_id, prompt)


class ParseLlmRankingsTests(unittest.TestCase):
    def setUp(self):
        candidates = [make_candidate(i) for i in range(1, 4)]
        self.entries = wp4.build_shortlist(candidates, k=3, seed=3)
        self.ids = [e.opaque_id for e in self.entries]

    def test_valid_full_coverage_is_accepted_and_sorted_by_score(self):
        payload = {
            "rankings": [
                {"candidate_id": self.ids[0], "score": 0.2, "reason": "r"},
                {"candidate_id": self.ids[1], "score": 0.9, "reason": "r"},
                {"candidate_id": self.ids[2], "score": 0.5, "reason": "r"},
            ]
        }
        result = wp4.parse_llm_rankings(payload, self.entries)
        self.assertIsNotNone(result)
        self.assertEqual([e.opaque_id for e in result], [self.ids[1], self.ids[2], self.ids[0]])

    def test_missing_candidate_id_falls_back(self):
        payload = {
            "rankings": [
                {"candidate_id": self.ids[0], "score": 0.2, "reason": "r"},
                {"candidate_id": self.ids[1], "score": 0.9, "reason": "r"},
            ]
        }
        self.assertIsNone(wp4.parse_llm_rankings(payload, self.entries))

    def test_duplicate_candidate_id_falls_back(self):
        payload = {
            "rankings": [
                {"candidate_id": self.ids[0], "score": 0.2, "reason": "r"},
                {"candidate_id": self.ids[0], "score": 0.9, "reason": "r"},
                {"candidate_id": self.ids[2], "score": 0.5, "reason": "r"},
            ]
        }
        self.assertIsNone(wp4.parse_llm_rankings(payload, self.entries))

    def test_unknown_candidate_id_falls_back(self):
        payload = {
            "rankings": [
                {"candidate_id": "C99", "score": 0.2, "reason": "r"},
                {"candidate_id": self.ids[1], "score": 0.9, "reason": "r"},
                {"candidate_id": self.ids[2], "score": 0.5, "reason": "r"},
            ]
        }
        self.assertIsNone(wp4.parse_llm_rankings(payload, self.entries))

    def test_out_of_range_score_falls_back(self):
        payload = {
            "rankings": [
                {"candidate_id": self.ids[0], "score": 1.5, "reason": "r"},
                {"candidate_id": self.ids[1], "score": 0.9, "reason": "r"},
                {"candidate_id": self.ids[2], "score": 0.5, "reason": "r"},
            ]
        }
        self.assertIsNone(wp4.parse_llm_rankings(payload, self.entries))

    def test_nan_score_falls_back(self):
        payload = {
            "rankings": [
                {"candidate_id": self.ids[0], "score": float("nan"), "reason": "r"},
                {"candidate_id": self.ids[1], "score": 0.9, "reason": "r"},
                {"candidate_id": self.ids[2], "score": 0.5, "reason": "r"},
            ]
        }
        self.assertIsNone(wp4.parse_llm_rankings(payload, self.entries))

    def test_malformed_payload_falls_back(self):
        self.assertIsNone(wp4.parse_llm_rankings({"nope": []}, self.entries))
        self.assertIsNone(wp4.parse_llm_rankings(None, self.entries))


class EligibilityTests(unittest.TestCase):
    def test_eligible_when_stage2_localized_files_is_dict_shaped(self):
        # Real prediction files store stage2_localized_files as a list of
        # dicts ({"file_path": ..., "rank": ..., ...}), not plain strings.
        from utils.symbol_evaluation import SymbolEvaluationItemV1

        row = {
            "stage2_localized_files": [
                {"file_path": "pkg/mod.py", "rank": 1, "score": 0.5},
            ]
        }
        gold_items = [
            SymbolEvaluationItemV1(
                file_path="pkg/mod.py", qualified_name="target", symbol_kind="function"
            )
        ]
        self.assertTrue(wp4.is_eligible(row, gold_items))

    def test_ineligible_when_gold_file_not_in_stage2_top5(self):
        from utils.symbol_evaluation import SymbolEvaluationItemV1

        row = {"stage2_localized_files": [{"file_path": "pkg/other.py"}]}
        gold_items = [
            SymbolEvaluationItemV1(
                file_path="pkg/mod.py", qualified_name="target", symbol_kind="function"
            )
        ]
        self.assertFalse(wp4.is_eligible(row, gold_items))


class RunTicketIntegrationTests(unittest.TestCase):
    def _row(self):
        gold_symbol = make_candidate(1, file_path="pkg/mod.py", qname="target")
        candidates = [make_candidate(i, qname=f"sym{i}") for i in range(1, 11)]
        candidates[4] = make_candidate(5, file_path="pkg/mod.py", qname="target")
        return {
            "ticket_id": "demo-1",
            "stage2_localized_files": [{"file_path": "pkg/mod.py", "rank": 1}],
            "stage3_candidate_symbols": candidates,
        }

    def _gold_items(self):
        from utils.symbol_evaluation import SymbolEvaluationItemV1

        return [
            SymbolEvaluationItemV1(
                file_path="pkg/mod.py", qualified_name="target", symbol_kind="function"
            )
        ]

    def test_valid_llm_response_can_recover_a_baseline_miss(self):
        row = self._row()
        entries_preview = wp4.build_shortlist(row["stage3_candidate_symbols"], 10, seed=20260908)
        target_id = next(
            e.opaque_id for e in entries_preview if e.candidate.get("symbol_qualified_name") == "target"
        )
        rankings = [{"candidate_id": target_id, "score": 0.99, "reason": "matches bug"}]
        rankings += [
            {"candidate_id": e.opaque_id, "score": 0.1, "reason": "unrelated"}
            for e in entries_preview
            if e.opaque_id != target_id
        ]
        client = FakeClient(response={"rankings": rankings})

        outcome = wp4.run_ticket(
            row,
            "bug report mentioning target",
            self._gold_items(),
            chunk_lookup={},
            llm_client=client,
            shortlist_k=10,
            top_k=5,
            seed=20260908,
        )
        self.assertTrue(outcome.eligible)
        self.assertTrue(outcome.llm_valid)
        self.assertEqual(outcome.llm_eval["exact"]["hit_at"]["1"], 1)

    def test_invalid_llm_response_falls_back_to_baseline_order(self):
        row = self._row()
        client = FakeClient(response={"rankings": [{"candidate_id": "bogus", "score": 0.5, "reason": "x"}]})
        outcome = wp4.run_ticket(
            row,
            "bug report",
            self._gold_items(),
            chunk_lookup={},
            llm_client=client,
            shortlist_k=10,
            top_k=5,
            seed=20260908,
        )
        self.assertFalse(outcome.llm_valid)
        self.assertEqual(outcome.fallback_reason, "invalid_or_incomplete_output")
        self.assertEqual(
            [c["symbol_qualified_name"] for c in outcome.llm_top],
            [c["symbol_qualified_name"] for c in outcome.baseline_top],
        )

    def test_llm_transport_error_falls_back(self):
        row = self._row()
        client = FakeClient(raise_error=TimeoutError("boom"))
        outcome = wp4.run_ticket(
            row,
            "bug report",
            self._gold_items(),
            chunk_lookup={},
            llm_client=client,
            shortlist_k=10,
            top_k=5,
            seed=20260908,
        )
        self.assertFalse(outcome.llm_valid)
        self.assertIn("llm_error", outcome.fallback_reason)


class SummarizeTests(unittest.TestCase):
    def test_summary_reports_fallback_rate_and_known_limitation(self):
        outcome = wp4.TicketOutcome(
            ticket_id="t1",
            eligible=True,
            llm_valid=False,
            fallback_reason="invalid_or_incomplete_output",
            baseline_eval={"exact": {"hit_at": {"1": 0, "3": 1, "5": 1}}},
            llm_eval={"exact": {"hit_at": {"1": 0, "3": 1, "5": 1}}},
        )
        summary = wp4.summarize([outcome])
        self.assertEqual(summary["eligible_count"], 1)
        self.assertEqual(summary["llm_fallback_count"], 1)
        self.assertIn("known_limitation", summary)
        self.assertIn("68.64%", summary["known_limitation"])


if __name__ == "__main__":
    unittest.main()
