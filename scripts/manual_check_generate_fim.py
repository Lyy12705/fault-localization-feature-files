"""Stage-4 WP1 acceptance check: manually verify ``OllamaClient.generate_fim()``
against a real local Ollama server on a handful of hand-picked examples.

Per STAGE4_PATCH_GENERATION_IMPLEMENTATION_PLAN_ZH.md section 9 (WP1), one
acceptance criterion is:

    "FIM 呼叫在至少 3 個手動範例上能產生語法合法的輸出"
    (the FIM call must produce syntactically valid output on at least 3
    manual examples)

This CANNOT be checked from the cloud dev environment that implemented WP1's
plumbing, because that environment has no Ollama server to call -- it only
has curl/subprocess mocked in the unit tests. This script must be run on a
machine with:

    1. Ollama installed and running (``ollama serve``, or the desktop app).
    2. The FIM model pulled:  ollama pull codellama:7b-code

Note the model tag: infilling uses the CODE-completion variant, not the
"-instruct" chat variant Stage-2/3 rerank uses. Asking "-instruct" to infill
failed in three different ways across three real runs (conversational prose,
self-invented end markers, and a completion that silently deleted the target
function) -- see llm_client.DEFAULT_FIM_MODEL's comment. Same Code Llama 7B
family, same size, different fine-tune.

Usage:

    python scripts/manual_check_generate_fim.py
    python scripts/manual_check_generate_fim.py --fim-model codellama:13b-code
    python scripts/manual_check_generate_fim.py --no-native-suffix   # hand-built PSM fallback
    python scripts/manual_check_generate_fim.py --timeout 300

Each example prints:
    - the FIM prompt's prefix/suffix (truncated for readability)
    - the raw generated middle text
    - the reassembled file, its syntax_valid flag and apply_status
      (via utils.patch_generation.apply_patch, so this exercises the same
      validation path Stage-4 WP2 will use)
    - whether the target symbol was actually (re)defined
      (utils.patch_generation.contains_expected_symbol_definition)

That last check matters on its own: a real run (2026-09-12) showed
syntax_valid=True/apply_status=applied_clean on a completion that had
silently deleted the target function entirely (a bare statement got
absorbed into the PRECEDING function's body, since Python doesn't require a
block to be explicitly closed) -- syntactically perfect, semantically
broken. An example only counts as PASS here if BOTH checks pass.

Exit code is 0 iff ALL examples pass both checks; 1 otherwise (with
per-example detail printed either way).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.llm_client import DEFAULT_FIM_MODEL, OllamaClient  # noqa: E402
from utils.patch_generation import apply_patch, contains_expected_symbol_definition  # noqa: E402


class FimExample(NamedTuple):
    name: str
    file_text: str
    start_line: int
    end_line: int
    ticket_comment: str
    symbol_kind: str
    symbol_name: str


EXAMPLES = [
    # NOTE (2026-09-12): the first two examples originally had an EMPTY
    # prefix (the target symbol was the file's first line) -- a real
    # Ollama run showed this is meaningfully harder than production usage:
    # with no preceding code, the model has no pattern to key off of and
    # can fail to regenerate even the "def ...():" signature line itself
    # (something structural trimming cannot fix; see
    # utils.patch_generation.trim_generated_code_to_symbol_scope's
    # docstring). Real Stage-3 symbols always have some prefix (imports,
    # other functions), so a one-function prefix was added here to make
    # these examples representative rather than an artificially hard
    # edge case.
    FimExample(
        name="simple_function_body",
        file_text=(
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
        ),
        start_line=5,
        end_line=6,
        ticket_comment=(
            "clamp(value, low, high) should return low if value < low, "
            "high if value > high, otherwise value."
        ),
        symbol_kind="function",
        symbol_name="clamp",
    ),
    FimExample(
        name="bug_fix_off_by_one",
        file_text=(
            "def first_index(items):\n"
            "    return 0\n"
            "\n"
            "\n"
            "def last_index(items):\n"
            "    return len(items)\n"
            "\n"
            "\n"
            "def use_last_index(items):\n"
            "    return items[last_index(items)]\n"
        ),
        start_line=5,
        end_line=6,
        ticket_comment=(
            "last_index(items) raises IndexError: it returns len(items), an "
            "out-of-range index; it should return the index of the last element."
        ),
        symbol_kind="function",
        symbol_name="last_index",
    ),
    FimExample(
        name="class_method_infill",
        file_text=(
            "class Counter:\n"
            "    def __init__(self):\n"
            "        self.value = 0\n"
            "\n"
            "    def increment(self, amount=1):\n"
            "        pass\n"
            "\n"
            "    def reset(self):\n"
            "        self.value = 0\n"
        ),
        start_line=5,
        end_line=6,
        ticket_comment="Counter.increment(amount) should add amount to self.value and return the new value.",
        symbol_kind="method",
        symbol_name="increment",
    ),
]


def run_example(client: OllamaClient, example: FimExample, *, use_native_suffix: bool) -> bool:
    from utils.patch_generation import append_ticket_comment_to_prefix, slice_prefix_suffix

    fim_slice = slice_prefix_suffix(example.file_text, example.start_line, example.end_line)
    prefix_with_comment = append_ticket_comment_to_prefix(fim_slice.prefix_text, example.ticket_comment)

    print(f"=== {example.name} ===")
    print("--- prefix (with Ticket comment) ---")
    print(prefix_with_comment)
    print("--- suffix ---")
    print(fim_slice.suffix_text or "(empty)")

    try:
        generated = client.generate_fim(
            prefix_with_comment, fim_slice.suffix_text, use_native_suffix=use_native_suffix
        )
    except Exception as exc:  # noqa: BLE001 - report, do not crash the whole run
        print(f"!! generate_fim() raised: {exc}")
        if "not found" in str(exc).lower():
            print(
                f"   The FIM model does not look pulled yet. Run:  ollama pull {client.fim_model}"
            )
        print()
        return False

    print("--- generated middle ---")
    print(generated or "(empty)")

    result = apply_patch(
        original_file_text=example.file_text,
        start_line=example.start_line,
        end_line=example.end_line,
        generated_code=generated,
        file_path=f"{example.name}.py",
        symbol_kind=example.symbol_kind,
        symbol_name=example.symbol_name,
    )
    print(f"--- syntax_valid={result.syntax_valid} apply_status={result.apply_status} ---")
    if result.notes:
        for note in result.notes:
            print(f"  note: {note}")
    print("--- reassembled file ---")
    print(result.patched_file_text)

    original_line = example.file_text.splitlines(keepends=True)[example.start_line - 1]
    base_indent = len(original_line) - len(original_line.lstrip(" \t"))
    symbol_defined = contains_expected_symbol_definition(
        generated,
        base_indent=base_indent,
        symbol_kind=example.symbol_kind,
        symbol_name=example.symbol_name,
    )
    print(f"--- target symbol '{example.symbol_name}' (re)defined: {symbol_defined} ---")
    if not symbol_defined:
        print(
            "  !! syntax can still be 'valid' here even though the target symbol was "
            "NOT redefined -- see contains_expected_symbol_definition()'s docstring."
        )
    print()

    apply_ok = result.syntax_valid and result.apply_status in ("applied_clean", "applied_with_offset")
    return apply_ok and symbol_defined


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:11434/api/generate")
    parser.add_argument("--fim-model", default=DEFAULT_FIM_MODEL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--no-native-suffix",
        action="store_true",
        help="Use the hand-built ' <PRE> ... <SUF> ... <MID>' + raw:true fallback "
        "instead of Ollama's native suffix/infilling field.",
    )
    args = parser.parse_args(argv)

    use_native_suffix = not args.no_native_suffix
    client = OllamaClient(url=args.url, fim_model=args.fim_model, timeout=args.timeout)

    print(f"FIM model: {client.fim_model}")
    print(f"FIM request mode: {'native suffix field' if use_native_suffix else 'hand-built PSM prompt + raw:true'}")
    print()

    results = []
    for example in EXAMPLES:
        try:
            ok = run_example(client, example, use_native_suffix=use_native_suffix)
        except Exception as exc:  # noqa: BLE001
            print(f"!! {example.name} failed unexpectedly: {exc}")
            ok = False
        results.append((example.name, ok))

    passed = sum(1 for _, ok in results if ok)
    print("=== Summary ===")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"{passed}/{len(results)} examples produced a syntactically valid, appliable patch that actually redefined the target symbol.")

    if passed == 0:
        print()
        print(
            "If every example failed, check that Ollama is running and that the FIM model "
            f"is pulled:  ollama pull {client.fim_model}"
        )

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
