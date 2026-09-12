from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for import_path in (str(SRC_ROOT), str(PROJECT_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from utils.patch_generation import (
    ApplyResult,
    FimSlice,
    PatchRecordV1,
    apply_patch,
    apply_patch_and_verify_symbol,
    append_ticket_comment_to_prefix,
    compute_patch_id,
    compute_symbol_id,
    contains_expected_symbol_definition,
    extract_symbol_text,
    is_supported_language,
    resolve_num_predict,
    resolve_symbol_line_range,
    slice_prefix_suffix,
    strip_trailing_blank_lines,
    trim_generated_code_to_symbol_scope,
    trim_leading_content_before_symbol_definition,
    validate_syntax,
)


SAMPLE_FILE = (
    "import os\n"           # line 1
    "\n"                    # line 2
    "\n"                    # line 3
    "def validate_token(token):\n"   # line 4
    "    if not token:\n"            # line 5
    "        return False\n"         # line 6
    "    return token.strip() != ''\n"  # line 7
    "\n"                    # line 8
    "\n"                    # line 9
    "def other():\n"        # line 10
    "    return os.getcwd()\n"       # line 11
)


class SupportedLanguageTests(unittest.TestCase):
    def test_python_file_is_supported(self) -> None:
        self.assertTrue(is_supported_language("src/auth/validator.py"))

    def test_non_python_file_is_unsupported(self) -> None:
        self.assertFalse(is_supported_language("src/handlers.ts"))
        self.assertFalse(is_supported_language("README.md"))


class SlicePrefixSuffixTests(unittest.TestCase):
    def test_slices_around_symbol_without_truncation(self) -> None:
        result = slice_prefix_suffix(SAMPLE_FILE, start_line=4, end_line=7)
        self.assertIsInstance(result, FimSlice)
        self.assertEqual(result.prefix_text, "import os\n\n\n")
        self.assertEqual(result.suffix_text, "\n\ndef other():\n    return os.getcwd()\n")
        self.assertEqual(result.prefix_lines, (1, 3))
        self.assertEqual(result.suffix_lines, (8, 11))
        self.assertFalse(result.truncated_prefix)
        self.assertFalse(result.truncated_suffix)

    def test_symbol_at_top_of_file_has_empty_prefix_range(self) -> None:
        result = slice_prefix_suffix(SAMPLE_FILE, start_line=1, end_line=1)
        self.assertEqual(result.prefix_text, "")
        self.assertEqual(result.prefix_lines, (1, 0))  # start > end == empty range

    def test_symbol_at_end_of_file_has_empty_suffix_range(self) -> None:
        total_lines = len(SAMPLE_FILE.splitlines())
        result = slice_prefix_suffix(SAMPLE_FILE, start_line=10, end_line=total_lines)
        self.assertEqual(result.suffix_text, "")
        self.assertEqual(result.suffix_lines, (total_lines + 1, total_lines))

    def test_prefix_truncated_to_token_budget_keeps_tail(self) -> None:
        big_prefix_file = "".join(f"line_{i}\n" for i in range(1, 101)) + "def target():\n    pass\n"
        start_line = 101
        end_line = 102
        result = slice_prefix_suffix(
            big_prefix_file,
            start_line=start_line,
            end_line=end_line,
            prefix_token_budget=10,  # ~10 tokens -> only a handful of trailing lines fit
        )
        self.assertTrue(result.truncated_prefix)
        self.assertNotIn("line_1\n", result.prefix_text)
        self.assertIn("line_100\n", result.prefix_text)
        # The kept range must end exactly at the symbol boundary and start
        # somewhere after line 1 (i.e. lines were dropped from the front).
        self.assertEqual(result.prefix_lines[1], start_line - 1)
        self.assertGreater(result.prefix_lines[0], 1)

    def test_suffix_truncated_to_token_budget_keeps_head(self) -> None:
        big_suffix_file = "def target():\n    pass\n" + "".join(f"line_{i}\n" for i in range(1, 101))
        result = slice_prefix_suffix(
            big_suffix_file,
            start_line=1,
            end_line=2,
            suffix_token_budget=10,
        )
        self.assertTrue(result.truncated_suffix)
        self.assertIn("line_1\n", result.suffix_text)
        self.assertNotIn("line_100\n", result.suffix_text)
        self.assertEqual(result.suffix_lines[0], 3)

    def test_rejects_invalid_line_range(self) -> None:
        with self.assertRaises(ValueError):
            slice_prefix_suffix(SAMPLE_FILE, start_line=0, end_line=1)
        with self.assertRaises(ValueError):
            slice_prefix_suffix(SAMPLE_FILE, start_line=5, end_line=4)

    def test_rejects_stale_line_range_beyond_file_length(self) -> None:
        with self.assertRaises(ValueError):
            slice_prefix_suffix(SAMPLE_FILE, start_line=1, end_line=9999)


class TicketCommentTests(unittest.TestCase):
    def test_appends_comment_with_newline_boundary(self) -> None:
        prefix = "import os\n"
        result = append_ticket_comment_to_prefix(prefix, "Login crashes when token is None.")
        self.assertEqual(
            result,
            "import os\n# Ticket summary: Login crashes when token is None.\n",
        )

    def test_collapses_whitespace_and_truncates_long_summary(self) -> None:
        long_summary = "word " * 200
        result = append_ticket_comment_to_prefix("", long_summary, max_chars=50)
        comment_line = result.strip("\n")
        self.assertTrue(comment_line.startswith("# Ticket summary: "))
        self.assertLessEqual(len(comment_line), len("# Ticket summary: ") + 50)

    def test_empty_summary_leaves_prefix_untouched(self) -> None:
        self.assertEqual(append_ticket_comment_to_prefix("import os\n", "   "), "import os\n")

    def test_rejects_unsupported_language(self) -> None:
        with self.assertRaises(ValueError):
            append_ticket_comment_to_prefix("prefix", "summary", language="javascript")


class ValidateSyntaxTests(unittest.TestCase):
    def test_valid_python_passes(self) -> None:
        self.assertTrue(validate_syntax("def f():\n    return 1\n"))

    def test_invalid_python_fails(self) -> None:
        self.assertFalse(validate_syntax("def f(:\n    return 1\n"))

    def test_empty_string_is_valid(self) -> None:
        self.assertTrue(validate_syntax(""))


class TrimGeneratedCodeToSymbolScopeTests(unittest.TestCase):
    def test_no_trim_when_body_never_returns_to_base_indent(self) -> None:
        code = "def f():\n    return 1\n"
        trimmed, was_trimmed = trim_generated_code_to_symbol_scope(code, base_indent=0)
        self.assertEqual(trimmed, code)
        self.assertFalse(was_trimmed)

    def test_trims_at_first_dedent_after_seeing_a_body_line(self) -> None:
        code = "def f():\n    return 1\ndef g():\n    return 2\n"
        trimmed, was_trimmed = trim_generated_code_to_symbol_scope(code, base_indent=0)
        self.assertEqual(trimmed, "def f():\n    return 1\n")
        self.assertTrue(was_trimmed)

    def test_trims_at_an_ad_hoc_non_standard_marker_line(self) -> None:
        # The marker string itself is irrelevant to this function -- it
        # trims on indentation structure alone, so it works even for a
        # marker (like the model's observed "<INF>") this module has never
        # heard of.
        code = "def f():\n    return 1\n<INF>\nsome trailing text\n"
        trimmed, was_trimmed = trim_generated_code_to_symbol_scope(code, base_indent=0)
        self.assertEqual(trimmed, "def f():\n    return 1\n")
        self.assertTrue(was_trimmed)

    def test_blank_lines_do_not_count_as_the_dedent_boundary(self) -> None:
        code = "def f():\n    return 1\n\n\ndef g():\n    return 2\n"
        trimmed, was_trimmed = trim_generated_code_to_symbol_scope(code, base_indent=0)
        self.assertEqual(trimmed, "def f():\n    return 1\n\n\n")
        self.assertTrue(was_trimmed)

    def test_nonzero_base_indent_for_a_class_method(self) -> None:
        code = "    def increment(self):\n        return 1\n    def reset(self):\n        self.value = 0\n"
        trimmed, was_trimmed = trim_generated_code_to_symbol_scope(code, base_indent=4)
        self.assertEqual(trimmed, "    def increment(self):\n        return 1\n")
        self.assertTrue(was_trimmed)

    def test_never_seeing_a_deeper_line_leaves_content_untouched(self) -> None:
        # A single mis-indented line with no body content at all is a
        # genuine generation miss, not something structural trimming should
        # try to repair -- apply_patch's syntax check is what should catch it.
        code = "    print('not a function')\n"
        trimmed, was_trimmed = trim_generated_code_to_symbol_scope(code, base_indent=0)
        self.assertEqual(trimmed, code)
        self.assertFalse(was_trimmed)


class TrimLeadingContentTests(unittest.TestCase):
    def test_drops_hallucinated_commentary_before_the_definition(self) -> None:
        """Regression test on the model's own real output (2026-09-12
        codellama:7b-code run): the increment() patch arrived with two
        fabricated '# Ticket summary:' comments about OTHER methods in front
        of it. Comments are syntactically harmless, so every syntax-level
        check passed -- but they would be committed into the class body."""

        code = (
            "    # Ticket summary: Counter.decrement(amount) should subtract amount.\n"
            "    # Ticket summary: Counter.reset() should set self.value to 0.\n"
            "\n"
            "    def increment(self, amount):\n"
            "        self.value += amount\n"
        )
        trimmed, was_trimmed = trim_leading_content_before_symbol_definition(
            code, symbol_kind="method", symbol_name="increment"
        )
        self.assertTrue(was_trimmed)
        self.assertEqual(
            trimmed, "    def increment(self, amount):\n        self.value += amount\n"
        )

    def test_keeps_decorators_attached_to_the_definition(self) -> None:
        code = (
            "# junk commentary\n"
            "@property\n"
            "@functools.cache\n"
            "def value(self):\n"
            "    return self._value\n"
        )
        trimmed, was_trimmed = trim_leading_content_before_symbol_definition(
            code, symbol_kind="method", symbol_name="value"
        )
        self.assertTrue(was_trimmed)
        self.assertTrue(trimmed.startswith("@property\n@functools.cache\ndef value(self):"))

    def test_no_change_when_definition_is_already_first(self) -> None:
        code = "def clamp(value, low, high):\n    return value\n"
        trimmed, was_trimmed = trim_leading_content_before_symbol_definition(
            code, symbol_kind="function", symbol_name="clamp"
        )
        self.assertEqual(trimmed, code)
        self.assertFalse(was_trimmed)

    def test_no_change_when_the_definition_is_absent(self) -> None:
        code = "    print('nothing here defines clamp')\n"
        trimmed, was_trimmed = trim_leading_content_before_symbol_definition(
            code, symbol_kind="function", symbol_name="clamp"
        )
        self.assertEqual(trimmed, code)
        self.assertFalse(was_trimmed)

    def test_matches_async_definitions(self) -> None:
        code = "# junk\nasync def fetch(url):\n    return url\n"
        trimmed, was_trimmed = trim_leading_content_before_symbol_definition(
            code, symbol_kind="function", symbol_name="fetch"
        )
        self.assertTrue(was_trimmed)
        self.assertTrue(trimmed.startswith("async def fetch(url):"))

    def test_class_kind_matches_class_statement(self) -> None:
        code = "# junk\nclass Counter:\n    pass\n"
        trimmed, was_trimmed = trim_leading_content_before_symbol_definition(
            code, symbol_kind="class", symbol_name="Counter"
        )
        self.assertTrue(was_trimmed)
        self.assertTrue(trimmed.startswith("class Counter:"))

    def test_does_not_match_a_similarly_prefixed_name(self) -> None:
        code = "# junk\ndef clamp_all(values):\n    return values\n"
        trimmed, was_trimmed = trim_leading_content_before_symbol_definition(
            code, symbol_kind="function", symbol_name="clamp"
        )
        self.assertEqual(trimmed, code)
        self.assertFalse(was_trimmed)


class StripTrailingBlankLinesTests(unittest.TestCase):
    def test_strips_a_stray_whitespace_only_final_line(self) -> None:
        # Observed verbatim in the real run: completions ended with a line
        # holding a single space, which lands in the diff as trailing
        # whitespace noise that many linters reject.
        code = "def f():\n    return 1\n "
        stripped, was_stripped = strip_trailing_blank_lines(code)
        self.assertTrue(was_stripped)
        self.assertEqual(stripped, "def f():\n    return 1\n")

    def test_no_change_when_there_is_nothing_to_strip(self) -> None:
        code = "def f():\n    return 1\n"
        stripped, was_stripped = strip_trailing_blank_lines(code)
        self.assertEqual(stripped, code)
        self.assertFalse(was_stripped)

    def test_does_not_touch_interior_blank_lines(self) -> None:
        code = "def f():\n    x = 1\n\n    return x\n\n"
        stripped, _ = strip_trailing_blank_lines(code)
        self.assertEqual(stripped, "def f():\n    x = 1\n\n    return x\n")


class ContainsExpectedSymbolDefinitionTests(unittest.TestCase):
    def test_true_when_generated_code_defines_the_expected_function(self) -> None:
        code = "def clamp(value, low, high):\n    return value\n"
        self.assertTrue(
            contains_expected_symbol_definition(
                code, base_indent=0, symbol_kind="function", symbol_name="clamp"
            )
        )

    def test_false_when_generated_code_never_defines_the_symbol_at_all(self) -> None:
        """Regression test for a real failure (manual_check_generate_fim.py,
        2026-09-12): a FIM completion that was just a bare call expression,
        with no 'def clamp(...):' line at all, spliced back in as a
        perfectly valid Python file (Python doesn't require a block to be
        explicitly closed, so the stray statement was silently absorbed into
        the PRECEDING function's body) -- apply_patch reported
        syntax_valid=True/applied_clean even though the target function
        'clamp' had been deleted entirely. This check must catch that."""

        code = "\n    print(clamp(15, 10, 20))\n"
        self.assertFalse(
            contains_expected_symbol_definition(
                code, base_indent=0, symbol_kind="function", symbol_name="clamp"
            )
        )

    def test_false_when_generated_code_defines_a_differently_named_function(self) -> None:
        code = "def not_clamp(value, low, high):\n    return value\n"
        self.assertFalse(
            contains_expected_symbol_definition(
                code, base_indent=0, symbol_kind="function", symbol_name="clamp"
            )
        )

    def test_true_for_a_class_definition_matched_by_name_and_kind(self) -> None:
        code = "class Counter:\n    pass\n"
        self.assertTrue(
            contains_expected_symbol_definition(
                code, base_indent=0, symbol_kind="class", symbol_name="Counter"
            )
        )

    def test_false_when_class_expected_but_function_generated(self) -> None:
        code = "def Counter():\n    pass\n"
        self.assertFalse(
            contains_expected_symbol_definition(
                code, base_indent=0, symbol_kind="class", symbol_name="Counter"
            )
        )

    def test_dedents_by_base_indent_for_a_class_method(self) -> None:
        code = "    def increment(self, amount):\n        return amount\n"
        self.assertTrue(
            contains_expected_symbol_definition(
                code, base_indent=4, symbol_kind="method", symbol_name="increment"
            )
        )

    def test_module_kind_is_not_applicable_and_always_passes(self) -> None:
        self.assertTrue(
            contains_expected_symbol_definition(
                "anything at all, not even valid syntax (((",
                base_indent=0,
                symbol_kind="module",
                symbol_name="<module>",
            )
        )

    def test_false_on_syntax_error_after_dedenting(self) -> None:
        code = "def clamp(value, low, high:\n    return value\n"
        self.assertFalse(
            contains_expected_symbol_definition(
                code, base_indent=0, symbol_kind="function", symbol_name="clamp"
            )
        )


class ApplyPatchTests(unittest.TestCase):
    def test_clean_apply_produces_valid_syntax_and_diff(self) -> None:
        result = apply_patch(
            original_file_text=SAMPLE_FILE,
            start_line=4,
            end_line=7,
            generated_code="def validate_token(token):\n    return bool(token) and token.strip() != ''\n",
            file_path="src/auth/validator.py",
        )
        self.assertIsInstance(result, ApplyResult)
        self.assertTrue(result.syntax_valid)
        self.assertEqual(result.apply_status, "applied_clean")
        self.assertIn("bool(token)", result.patched_file_text)
        self.assertIn("--- a/src/auth/validator.py", result.diff_unified)
        self.assertIn("+++ b/src/auth/validator.py", result.diff_unified)
        self.assertEqual(result.notes, [])

    def test_missing_trailing_newline_is_fixed_and_flagged_as_offset(self) -> None:
        result = apply_patch(
            original_file_text=SAMPLE_FILE,
            start_line=4,
            end_line=7,
            generated_code="def validate_token(token):\n    return True",  # no trailing newline
        )
        self.assertTrue(result.syntax_valid)
        self.assertEqual(result.apply_status, "applied_with_offset")
        self.assertTrue(result.notes)

    def test_syntactically_invalid_generated_code_is_reported(self) -> None:
        result = apply_patch(
            original_file_text=SAMPLE_FILE,
            start_line=4,
            end_line=7,
            generated_code="def validate_token(token:\n    return True\n",
        )
        self.assertFalse(result.syntax_valid)
        self.assertEqual(result.apply_status, "syntax_error")

    def test_apply_patch_trims_content_the_model_generated_past_its_own_scope(self) -> None:
        """Regression test using the model's own real output (2026-09-12 run
        3 of manual_check_generate_fim.py): the model produced a correct-
        looking function, then an ad hoc "<INF>" marker (not one of Code
        Llama's documented sentinels), then kept going into an unrelated
        pytest-style test function. apply_patch must recognize -- from
        indentation alone, independent of what marker (if any) was used --
        that the model left the target symbol's scope, and trim there."""

        file_text = (
            "def last_index(items):\n"
            "    return len(items)\n"
            "\n"
            "\n"
            "def use_last_index(items):\n"
            "    return items[last_index(items)]\n"
        )
        generated_code = (
            "\n\ndef last_index(items):\n"
            "    return len(items) - 1\n"
            "<INF>\n"
            "\n"
            "def test_last_index():\n"
            "    assert last_index([1, 2, 3]) == 2\n"
        )

        result = apply_patch(
            original_file_text=file_text,
            start_line=1,
            end_line=2,
            generated_code=generated_code,
        )

        self.assertTrue(result.syntax_valid)
        self.assertEqual(result.apply_status, "applied_with_offset")
        self.assertIn("def last_index(items):\n    return len(items) - 1\n", result.patched_file_text)
        self.assertNotIn("<INF>", result.patched_file_text)
        self.assertNotIn("test_last_index", result.patched_file_text)
        self.assertTrue(any("target symbol's own scope" in note for note in result.notes))

    def test_apply_patch_cleans_a_real_codellama_7b_code_completion_end_to_end(self) -> None:
        """The exact generated text from the 2026-09-12 codellama:7b-code run
        for Counter.increment: fabricated leading comments about unrelated
        methods, a trailing extra method, and a stray whitespace-only final
        line. All three must be cleaned, leaving exactly the class a human
        would have written."""

        file_text = (
            "class Counter:\n"
            "    def __init__(self):\n"
            "        self.value = 0\n"
            "\n"
            "    def increment(self, amount=1):\n"
            "        pass\n"
            "\n"
            "    def reset(self):\n"
            "        self.value = 0\n"
        )
        generated_code = (
            "    # Ticket summary: Counter.decrement(amount) should subtract amount.\n"
            "    # Ticket summary: Counter.reset() should set self.value to 0.\n"
            "\n"
            "    def increment(self, amount):\n"
            "        self.value += amount\n"
            "        return self.value\n"
            "\n"
            "    def decrement(self, amount):\n"
            "        self.value -= amount\n"
            "        return self.value\n"
            " "
        )

        result = apply_patch(
            original_file_text=file_text,
            start_line=5,
            end_line=6,
            generated_code=generated_code,
            symbol_kind="method",
            symbol_name="increment",
        )

        self.assertTrue(result.syntax_valid)
        self.assertEqual(result.apply_status, "applied_with_offset")
        self.assertEqual(
            result.patched_file_text,
            "class Counter:\n"
            "    def __init__(self):\n"
            "        self.value = 0\n"
            "\n"
            "    def increment(self, amount):\n"
            "        self.value += amount\n"
            "        return self.value\n"
            "\n"
            "    def reset(self):\n"
            "        self.value = 0\n",
        )
        self.assertNotIn("Ticket summary", result.patched_file_text)
        self.assertNotIn("decrement", result.patched_file_text)
        self.assertEqual(len(result.notes), 3)

    def test_apply_patch_does_not_trim_a_well_formed_single_function_completion(self) -> None:
        """No trimming (and no offset note about scope) when the model
        stopped cleanly on its own -- trimming must not fire on ordinary,
        well-behaved output."""

        result = apply_patch(
            original_file_text=SAMPLE_FILE,
            start_line=4,
            end_line=7,
            generated_code="def validate_token(token):\n    return bool(token)\n",
        )
        self.assertEqual(result.apply_status, "applied_clean")
        self.assertEqual(result.notes, [])

    def test_stale_line_range_reports_apply_failed_without_raising(self) -> None:
        result = apply_patch(
            original_file_text=SAMPLE_FILE,
            start_line=1,
            end_line=9999,
            generated_code="pass\n",
        )
        self.assertEqual(result.apply_status, "apply_failed")
        self.assertFalse(result.syntax_valid)
        self.assertTrue(result.notes)


class ResolveSymbolLineRangeTests(unittest.TestCase):
    """Stage-3 reports the retrieval CHUNK's line range, not the symbol's own.

    Real case (2026-09-12, astropy__astropy-13073): Stage-3 reported
    `function read` at lines 252-331 of astropy/io/ascii/ui.py, while the
    real `def read` spans 269-408. Patching the reported range targets a
    fragment of three different definitions and is unsatisfiable.
    """

    FILE = (
        "import os\n"                       # 1
        "\n"                                # 2
        "\n"                                # 3
        "def _helper(x):\n"                 # 4
        "    return x\n"                    # 5
        "\n"                                # 6
        "\n"                                # 7
        "def read(table, guess=None):\n"    # 8
        "    dat = _helper(table)\n"        # 9
        "    if guess:\n"                   # 10
        "        dat = None\n"              # 11
        "    return dat\n"                  # 12
        "\n"                                # 13
        "\n"                                # 14
        "def write(table):\n"               # 15
        "    return table\n"                # 16
    )

    def test_recovers_the_real_definition_from_a_chunk_range(self) -> None:
        # Hint range mimics a chunker: starts above the def, ends mid-body.
        result = resolve_symbol_line_range(
            self.FILE, symbol_qualified_name="read", symbol_name="read", hint_start_line=6, hint_end_line=10
        )
        self.assertTrue(result.resolved)
        self.assertEqual((result.start_line, result.end_line), (8, 12))

    def test_resolved_range_is_a_complete_parseable_definition(self) -> None:
        result = resolve_symbol_line_range(
            self.FILE, symbol_qualified_name="read", symbol_name="read", hint_start_line=6, hint_end_line=10
        )
        target = extract_symbol_text(self.FILE, result.start_line, result.end_line)
        self.assertTrue(target.startswith("def read("))
        self.assertTrue(validate_syntax(target))

    def test_includes_decorators_in_the_range(self) -> None:
        text = (
            "import functools\n"                # 1
            "\n"                                # 2
            "\n"                                # 3
            "@functools.cache\n"                # 4
            "@staticmethod\n"                   # 5
            "def cached(x):\n"                  # 6
            "    return x\n"                    # 7
        )
        result = resolve_symbol_line_range(
            text, symbol_qualified_name="cached", symbol_name="cached", hint_start_line=6, hint_end_line=7
        )
        self.assertTrue(result.resolved)
        self.assertEqual(result.start_line, 4)  # starts at the first decorator, not the def

    def test_resolves_a_method_by_qualified_name(self) -> None:
        text = (
            "class Counter:\n"              # 1
            "    def increment(self):\n"    # 2
            "        self.value += 1\n"     # 3
            "\n"                            # 4
            "    def reset(self):\n"        # 5
            "        self.value = 0\n"      # 6
        )
        result = resolve_symbol_line_range(
            text,
            symbol_qualified_name="Counter.increment",
            symbol_name="increment",
            hint_start_line=1,
            hint_end_line=6,
        )
        self.assertTrue(result.resolved)
        self.assertEqual((result.start_line, result.end_line), (2, 3))

    def test_same_method_name_in_two_classes_is_disambiguated_by_the_hint_range(self) -> None:
        text = (
            "class A:\n"                # 1
            "    def run(self):\n"      # 2
            "        return 'a'\n"      # 3
            "\n"                        # 4
            "\n"                        # 5
            "class B:\n"                # 6
            "    def run(self):\n"      # 7
            "        return 'b'\n"      # 8
        )
        near_b = resolve_symbol_line_range(
            text, symbol_qualified_name="run", symbol_name="run", hint_start_line=6, hint_end_line=8
        )
        self.assertEqual((near_b.start_line, near_b.end_line), (7, 8))

        near_a = resolve_symbol_line_range(
            text, symbol_qualified_name="run", symbol_name="run", hint_start_line=1, hint_end_line=3
        )
        self.assertEqual((near_a.start_line, near_a.end_line), (2, 3))

    def test_missing_definition_is_reported_unresolved_not_silently_fallen_back(self) -> None:
        result = resolve_symbol_line_range(
            self.FILE, symbol_qualified_name="deleted_symbol", symbol_name="deleted_symbol",
            hint_start_line=6, hint_end_line=10,
        )
        self.assertFalse(result.resolved)
        self.assertIn("no definition named", result.reason)

    def test_unparseable_file_is_reported_unresolved(self) -> None:
        result = resolve_symbol_line_range(
            "def broken(:\n    pass\n", symbol_qualified_name="broken", symbol_name="broken",
            hint_start_line=1, hint_end_line=2,
        )
        self.assertFalse(result.resolved)
        self.assertIn("does not parse", result.reason)

    def test_class_target_resolves_to_the_whole_class(self) -> None:
        text = (
            "class Widget:\n"           # 1
            "    def a(self):\n"        # 2
            "        pass\n"            # 3
            "\n"                        # 4
            "    def b(self):\n"        # 5
            "        pass\n"            # 6
            "\n"                        # 7
            "\n"                        # 8
            "x = 1\n"                   # 9
        )
        result = resolve_symbol_line_range(
            text, symbol_qualified_name="Widget", symbol_name="Widget", hint_start_line=1, hint_end_line=6
        )
        self.assertTrue(result.resolved)
        self.assertEqual((result.start_line, result.end_line), (1, 6))


class ResolveNumPredictTests(unittest.TestCase):
    """Regression tests for the 2026-09-12 0/3 smoke run: a fixed 256-token
    budget truncated every sample on an 80-line target."""

    def test_large_symbol_gets_a_budget_bigger_than_itself(self) -> None:
        # The real astropy__astropy-13073 target: 80 lines, 3301 chars (~825 tokens).
        big_symbol = "def f():\n" + ("    x = 1  # padding to reach ~3300 chars\n" * 78)
        budget = resolve_num_predict(big_symbol, headroom=2.0, minimum=256, maximum=4096)
        approx_symbol_tokens = len(big_symbol) // 4
        self.assertGreater(budget, approx_symbol_tokens)

    def test_tiny_symbol_still_gets_the_floor(self) -> None:
        self.assertEqual(resolve_num_predict("def f():\n    pass\n", headroom=2.0, minimum=256, maximum=4096), 256)

    def test_enormous_symbol_is_capped(self) -> None:
        huge = "x = 1\n" * 20000
        self.assertEqual(resolve_num_predict(huge, headroom=2.0, minimum=256, maximum=4096), 4096)

    def test_headroom_scales_the_budget(self) -> None:
        symbol = "y = 2\n" * 500
        low = resolve_num_predict(symbol, headroom=1.0, minimum=1, maximum=100000)
        high = resolve_num_predict(symbol, headroom=3.0, minimum=1, maximum=100000)
        self.assertAlmostEqual(high / low, 3.0, delta=0.05)

    def test_invalid_bounds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_num_predict("x = 1\n", headroom=0, minimum=256, maximum=4096)
        with self.assertRaises(ValueError):
            resolve_num_predict("x = 1\n", headroom=2.0, minimum=500, maximum=100)


class ExtractSymbolTextTests(unittest.TestCase):
    def test_extracts_the_inclusive_line_range(self) -> None:
        self.assertEqual(extract_symbol_text(SAMPLE_FILE, 4, 7), (
            "def validate_token(token):\n"
            "    if not token:\n"
            "        return False\n"
            "    return token.strip() != ''\n"
        ))

    def test_rejects_an_invalid_range(self) -> None:
        with self.assertRaises(ValueError):
            extract_symbol_text(SAMPLE_FILE, 0, 3)


class ApplyPatchAndVerifySymbolTests(unittest.TestCase):
    def test_downgrades_to_apply_failed_when_symbol_silently_deleted(self) -> None:
        """Regression test for the real WP1 false positive (2026-09-12): a
        completion that never redefines `clamp` gets silently absorbed as
        extra body lines of the PRECEDING function `to_int`, so plain
        apply_patch() reports syntax_valid=True/applied_clean even though
        `clamp` no longer exists. apply_patch_and_verify_symbol() must catch
        this and downgrade to apply_failed."""

        file_text = (
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
        # A degenerate completion: no `def clamp` line at all, just a call
        # expression -- indentation lets it merge into to_int's body.
        generated_code = "    print(clamp(15, 10, 20))\n"

        plain_result = apply_patch(
            original_file_text=file_text,
            start_line=5,
            end_line=6,
            generated_code=generated_code,
        )
        self.assertTrue(plain_result.syntax_valid)
        self.assertEqual(plain_result.apply_status, "applied_clean")  # the misleading result

        verified_result = apply_patch_and_verify_symbol(
            original_file_text=file_text,
            start_line=5,
            end_line=6,
            generated_code=generated_code,
            symbol_kind="function",
            symbol_name="clamp",
        )
        self.assertEqual(verified_result.apply_status, "apply_failed")
        self.assertTrue(any("did not actually" in note for note in verified_result.notes))

    def test_keeps_applied_clean_when_symbol_really_is_redefined(self) -> None:
        result = apply_patch_and_verify_symbol(
            original_file_text=SAMPLE_FILE,
            start_line=4,
            end_line=7,
            generated_code="def validate_token(token):\n    return bool(token)\n",
            symbol_kind="function",
            symbol_name="validate_token",
        )
        self.assertEqual(result.apply_status, "applied_clean")
        self.assertEqual(result.notes, [])

    def test_keeps_applied_with_offset_when_trimming_needed_but_symbol_present(self) -> None:
        result = apply_patch_and_verify_symbol(
            original_file_text=SAMPLE_FILE,
            start_line=4,
            end_line=7,
            generated_code="def validate_token(token):\n    return bool(token)",  # no trailing newline
            symbol_kind="function",
            symbol_name="validate_token",
        )
        self.assertEqual(result.apply_status, "applied_with_offset")

    def test_syntax_error_is_left_untouched(self) -> None:
        result = apply_patch_and_verify_symbol(
            original_file_text=SAMPLE_FILE,
            start_line=4,
            end_line=7,
            generated_code="def validate_token(token:\n    return True\n",
            symbol_kind="function",
            symbol_name="validate_token",
        )
        self.assertEqual(result.apply_status, "syntax_error")

    def test_skips_the_check_when_symbol_kind_or_name_is_unknown(self) -> None:
        """Behaves exactly like apply_patch() when the caller doesn't know
        the target symbol -- the check is skipped, not assumed to pass."""

        file_text = (
            "def to_int(x):\n"
            "    return int(x)\n"
            "\n"
            "\n"
            "def clamp(value, low, high):\n"
            "    pass\n"
        )
        generated_code = "    print(clamp(15, 10, 20))\n"

        result = apply_patch_and_verify_symbol(
            original_file_text=file_text,
            start_line=5,
            end_line=6,
            generated_code=generated_code,
        )
        self.assertEqual(result.apply_status, "applied_clean")

    def test_real_counter_increment_output_passes_both_checks(self) -> None:
        file_text = (
            "class Counter:\n"
            "    def __init__(self):\n"
            "        self.value = 0\n"
            "\n"
            "    def increment(self, amount=1):\n"
            "        pass\n"
            "\n"
            "    def reset(self):\n"
            "        self.value = 0\n"
        )
        generated_code = (
            "    # Ticket summary: Counter.decrement(amount) should subtract amount.\n"
            "    def increment(self, amount):\n"
            "        self.value += amount\n"
            "        return self.value\n"
            " "
        )
        result = apply_patch_and_verify_symbol(
            original_file_text=file_text,
            start_line=5,
            end_line=6,
            generated_code=generated_code,
            symbol_kind="method",
            symbol_name="increment",
        )
        self.assertEqual(result.apply_status, "applied_with_offset")


class PatchIdentityTests(unittest.TestCase):
    def test_symbol_id_is_stable_for_same_inputs(self) -> None:
        first = compute_symbol_id(
            file_path="src/auth/validator.py",
            symbol_qualified_name="validator.validate_token",
            start_line=4,
            end_line=7,
        )
        second = compute_symbol_id(
            file_path="src/auth/validator.py",
            symbol_qualified_name="validator.validate_token",
            start_line=4,
            end_line=7,
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))

    def test_symbol_id_differs_for_different_line_ranges(self) -> None:
        base = dict(file_path="a.py", symbol_qualified_name="a.f", start_line=1, end_line=2)
        other = dict(base, end_line=3)
        self.assertNotEqual(compute_symbol_id(**base), compute_symbol_id(**other))

    def test_patch_id_differs_by_sampling_index_and_content(self) -> None:
        symbol_id = compute_symbol_id(file_path="a.py", symbol_qualified_name="a.f", start_line=1, end_line=2)
        id_a = compute_patch_id(ticket_id="T-1", target_symbol_id=symbol_id, sampling_index=0, generated_code="x = 1")
        id_b = compute_patch_id(ticket_id="T-1", target_symbol_id=symbol_id, sampling_index=1, generated_code="x = 1")
        id_c = compute_patch_id(ticket_id="T-1", target_symbol_id=symbol_id, sampling_index=0, generated_code="x = 2")
        self.assertNotEqual(id_a, id_b)
        self.assertNotEqual(id_a, id_c)

    def test_patch_id_is_stable_for_identical_inputs(self) -> None:
        symbol_id = compute_symbol_id(file_path="a.py", symbol_qualified_name="a.f", start_line=1, end_line=2)
        kwargs = dict(ticket_id="T-1", target_symbol_id=symbol_id, sampling_index=0, generated_code="x = 1")
        self.assertEqual(compute_patch_id(**kwargs), compute_patch_id(**kwargs))


class PatchRecordV1Tests(unittest.TestCase):
    def test_from_generation_builds_a_consistent_record(self) -> None:
        fim_slice = slice_prefix_suffix(SAMPLE_FILE, start_line=4, end_line=7)
        apply_result = apply_patch(
            original_file_text=SAMPLE_FILE,
            start_line=4,
            end_line=7,
            generated_code="def validate_token(token):\n    return bool(token)\n",
            file_path="src/auth/validator.py",
        )
        record = PatchRecordV1.from_generation(
            ticket_id="repo__owner-issue-1234",
            repo="owner/repo",
            base_commit="a" * 40,
            file_path="src/auth/validator.py",
            symbol_qualified_name="validator.validate_token",
            start_line=4,
            end_line=7,
            fim_slice=fim_slice,
            generated_code="def validate_token(token):\n    return bool(token)\n",
            sampling_index=0,
            temperature=0.2,
            apply_result=apply_result,
            generation_source="codellama:7b-instruct-fim",
            model_digest="sha256:fake-model-digest",
            prompt_version="patchgen-fim-v1",
        )

        as_dict = record.to_dict()
        self.assertEqual(as_dict["schema_version"], "patch-record-v1")
        self.assertEqual(as_dict["apply_status"], "applied_clean")
        self.assertTrue(as_dict["syntax_valid"])
        self.assertEqual(as_dict["fim_prefix_lines"], [1, 3])
        self.assertEqual(as_dict["fim_suffix_lines"], [8, 11])
        self.assertTrue(as_dict["patch_id"].startswith("sha256:"))
        self.assertTrue(as_dict["target_symbol_id"].startswith("sha256:"))
        self.assertIn("generated_at", as_dict)

    def test_rejects_unknown_apply_status(self) -> None:
        with self.assertRaises(ValueError):
            PatchRecordV1(
                patch_id="sha256:x",
                ticket_id="T-1",
                repo="owner/repo",
                base_commit="a" * 40,
                target_symbol_id="sha256:y",
                file_path="a.py",
                fim_prefix_lines=(1, 0),
                fim_suffix_lines=(2, 1),
                generated_code="pass\n",
                sampling_index=0,
                temperature=0.2,
                syntax_valid=True,
                apply_status="not_a_real_status",
                diff_unified="",
                generation_source="codellama:7b-instruct-fim",
                model_digest="sha256:fake",
                prompt_version="patchgen-fim-v1",
                generated_at="2026-09-12T00:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
