"""Stage-4 (WP1) patch-generation building blocks: FIM slicing and validation.

This module implements the pieces of
``STAGE4_PATCH_GENERATION_IMPLEMENTATION_PLAN_ZH.md`` WP1 that live outside
the Stage-3 confidence gate (see ``fault_localization._symbol_gate_status``)
and outside the raw Ollama FIM call (see ``llm_client.OllamaClient.generate_fim``):

- ``PatchRecordV1``: the data contract for one generated patch candidate
  (plan section 4.2).
- ``slice_prefix_suffix``: cuts a base-commit file into the FIM prefix/suffix
  around a Stage-3 symbol's line range, respecting a token budget (plan
  section 5.1, steps 1 and 4; section 5.2's frozen token budgets).
- ``append_ticket_comment_to_prefix``: appends a comment-formatted Ticket
  summary to the prefix so the model has bug context in-line (plan section
  5.1, step 2).
- ``validate_syntax`` / ``apply_patch``: the syntax and apply validation
  Stage 4A requires before a candidate can proceed to test generation (plan
  section 5.3).

Scope note (plan section 1.3): Stage-4 v1 only supports Python; any other
language is reported as ``unsupported`` rather than run through FIM.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import re
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

PATCH_RECORD_SCHEMA_VERSION = "patch-record-v1"

# Stage-4 v1 only covers Python (plan section 1.3); everything else is
# reported as unsupported rather than silently attempted.
SUPPORTED_LANGUAGE = "python"

APPLY_STATUS_VALUES = ("applied_clean", "applied_with_offset", "syntax_error", "apply_failed")

_COMMENT_PREFIX_BY_LANGUAGE = {"python": "#"}


def is_supported_language(file_path: str) -> bool:
    """Return True iff ``file_path`` is a language Stage-4 v1 supports (Python only)."""

    return file_path.rstrip().lower().endswith(".py")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _approx_token_count(text: str) -> int:
    """Cheap, offline token-count heuristic (~4 chars/token for source code).

    This project has no bundled Code Llama tokenizer, so prompt token budgets
    are enforced with this heuristic instead of an exact count. Rounding up
    keeps it conservative: the real prompt should stay within budget even if
    this under-counts relative to the true tokenizer.
    """

    if not text:
        return 0
    return max(1, -(-len(text) // 4))


def _truncate_keep_tail(lines: list[str], token_budget: int) -> tuple[str, int]:
    """Keep as many trailing lines as fit in ``token_budget``.

    Returns the kept text and how many leading lines were dropped. Used for
    the FIM prefix, where the context nearest the insertion point (the end)
    matters most.
    """

    kept: list[str] = []
    total = 0
    for line in reversed(lines):
        cost = _approx_token_count(line)
        if kept and total + cost > token_budget:
            break
        kept.append(line)
        total += cost
    kept.reverse()
    return "".join(kept), len(lines) - len(kept)


def _truncate_keep_head(lines: list[str], token_budget: int) -> tuple[str, int]:
    """Keep as many leading lines as fit in ``token_budget``.

    Returns the kept text and how many lines were kept. Used for the FIM
    suffix, where the context nearest the insertion point (the start)
    matters most.
    """

    kept: list[str] = []
    total = 0
    for line in lines:
        cost = _approx_token_count(line)
        if kept and total + cost > token_budget:
            break
        kept.append(line)
        total += cost
    return "".join(kept), len(kept)


@dataclass(slots=True)
class ResolvedSymbolRange:
    """A patch target's true definition boundaries, resolved from real source.

    ``resolved`` is False when the named definition could not be found in the
    file at all; ``start_line``/``end_line`` then still hold the caller's hint
    range, but a caller must NOT patch with them -- see
    ``resolve_symbol_line_range``.
    """

    start_line: int
    end_line: int
    resolved: bool
    reason: str = ""


def _definition_kind(node: ast.AST) -> str:
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, ast.AsyncFunctionDef):
        return "async function"
    return "function"


def _iter_definitions(tree: ast.AST) -> list[tuple[str, str, str, int, int]]:
    """Collect ``(qualified_name, leaf_name, kind, start_line, end_line)`` for every def/class.

    ``start_line`` includes any decorators: a decorator belongs to the
    definition it decorates, so replacing a symbol without them would leave a
    dangling ``@decorator`` above the new code.
    """

    found: list[tuple[str, str, str, int, int]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = f"{prefix}.{child.name}" if prefix else child.name
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                end = child.end_lineno or child.lineno
                found.append((qualified, child.name, _definition_kind(child), start, end))
                walk(child, qualified)
            else:
                walk(child, prefix)

    walk(tree, "")
    return found


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start) + 1)


def resolve_symbol_line_range(
    file_text: str,
    *,
    symbol_qualified_name: str,
    symbol_name: str = "",
    hint_start_line: int,
    hint_end_line: int,
) -> ResolvedSymbolRange:
    """Resolve a Stage-3 candidate to the TRUE definition boundaries in the source.

    Stage-3's ``stage3_ranked_symbols[*].end_line`` is the end of the
    retrieval CHUNK the symbol was found in, not the end of the symbol's own
    definition: the code index chunks files at a fixed size (80 lines in this
    project's Stage-1 settings), so any definition longer than one chunk is
    reported truncated. Confirmed on 2026-09-12 against
    astropy/io/ascii/ui.py at astropy__astropy-13073's base commit
    (43ee5806): Stage-3 reports ``function read`` at lines 252-331 -- exactly
    80 lines -- while the real ``def read`` spans 252-388 (137 lines). The
    start line happened to be right here; the end was 57 lines short, landing
    inside the function's body.

    Patching that range replaces the first 80 lines of a function with
    generated code and leaves the remaining 57 lines of the old body dangling
    after it. No completion can satisfy that: it would have to end mid-body at
    exactly the indentation the leftover tail continues from. The Stage-4 WP2
    1-ticket smoke run scored 0/3 on exactly this.

    The symbol's NAME and KIND from Stage-3 are reliable, so this re-derives
    the boundaries from the real file: parse it, find the definition with
    that name, and use its own ``lineno``/``end_lineno`` (decorators
    included). The hint range is still used -- as a disambiguator when a name
    occurs more than once (e.g. a method name shared by several classes), by
    preferring the definition that overlaps the chunk Stage-3 actually
    retrieved.

    When the definition cannot be found (a stale line range against a moved
    or deleted symbol, a non-Python file, a syntactically invalid snapshot),
    this returns ``resolved=False`` with a reason; callers must skip the
    candidate rather than fall back to the hint range, which is exactly the
    wrong-boundaries case this exists to prevent.
    """

    if hint_start_line < 1 or hint_end_line < hint_start_line:
        return ResolvedSymbolRange(
            hint_start_line, hint_end_line, False, f"invalid hint range [{hint_start_line}, {hint_end_line}]"
        )

    try:
        # Real-world sources routinely raise SyntaxWarning while parsing
        # (e.g. invalid escape sequences in older code). Those are the file's
        # business, not this pipeline's, and would otherwise spam a batch run.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(file_text)
    except SyntaxError as exc:
        return ResolvedSymbolRange(hint_start_line, hint_end_line, False, f"file does not parse: {exc}")

    definitions = _iter_definitions(tree)
    if not definitions:
        return ResolvedSymbolRange(hint_start_line, hint_end_line, False, "file contains no definitions")

    qualified = (symbol_qualified_name or "").strip()
    leaf = (symbol_name or qualified.rsplit(".", maxsplit=1)[-1]).strip()

    # Most specific match first: full qualified name, then a qualified-name
    # suffix (Stage-3 may carry a module prefix the AST does not), then the
    # bare leaf name.
    candidates = [d for d in definitions if qualified and d[0] == qualified]
    if not candidates and qualified:
        candidates = [d for d in definitions if d[0].endswith(f".{qualified}") or qualified.endswith(f".{d[0]}")]
    if not candidates and leaf:
        candidates = [d for d in definitions if d[1] == leaf]
    if not candidates:
        return ResolvedSymbolRange(
            hint_start_line, hint_end_line, False, f"no definition named {qualified or leaf!r} in this file"
        )

    # Several same-named definitions: take the one the retrieved chunk
    # actually overlaps, falling back to the nearest one.
    best = max(
        candidates,
        key=lambda d: (
            _overlap(d[3], d[4], hint_start_line, hint_end_line),
            -abs(d[3] - hint_start_line),
        ),
    )
    return ResolvedSymbolRange(best[3], best[4], True)


def resolve_num_predict(
    original_symbol_text: str,
    *,
    headroom: float = 2.0,
    minimum: int = 256,
    maximum: int = 4096,
) -> int:
    """Size the FIM generation budget to the symbol actually being replaced.

    A fixed ``num_predict`` cannot work for real targets: Stage-3 symbols
    range from three-line helpers to hundred-line functions, and a budget
    smaller than the symbol guarantees the completion is cut off mid-token,
    mid-string or mid-block -- which then reads as a "syntax_error" that
    looks like a model-quality failure but is really a configuration one.

    Observed for real on 2026-09-12 (Stage-4 WP2 1-ticket smoke run,
    astropy__astropy-13073): the target symbol was 80 lines / 3301 chars
    (~825 tokens) while ``num_predict`` was the 256 carried over from WP1's
    two-to-three-line manual examples. All three samples were truncated
    mid-statement and the run scored 0/3 -- not because the model could not
    write the function, but because it was never given room to finish it.

    A replacement for a buggy symbol is normally within a small multiple of
    the original's size (a fix rarely triples a function's length), so the
    budget is the original's estimated token count times ``headroom``,
    clamped to ``[minimum, maximum]``. The floor keeps tiny symbols
    workable; the ceiling bounds worst-case generation time per sample.
    """

    if headroom <= 0:
        raise ValueError("headroom must be positive.")
    if minimum < 1 or maximum < minimum:
        raise ValueError(f"Invalid num_predict bounds: minimum={minimum}, maximum={maximum}")

    needed = int(_approx_token_count(original_symbol_text) * headroom)
    return max(minimum, min(maximum, needed))


def extract_symbol_text(file_text: str, start_line: int, end_line: int) -> str:
    """Return the exact [start_line, end_line] (1-indexed, inclusive) slice of ``file_text``."""

    if start_line < 1 or end_line < start_line:
        raise ValueError(f"Invalid symbol line range: start_line={start_line}, end_line={end_line}")
    return "".join(file_text.splitlines(keepends=True)[start_line - 1 : end_line])


@dataclass(slots=True)
class FimSlice:
    """FIM prompt context: prefix/suffix text plus their 1-indexed source line ranges.

    ``prefix_lines``/``suffix_lines`` follow the same "empty means start >
    end" convention as the rest of this pipeline's line ranges, so a symbol
    at the very top of a file naturally reports an empty prefix range rather
    than needing a special case.
    """

    prefix_text: str
    suffix_text: str
    prefix_lines: tuple[int, int]
    suffix_lines: tuple[int, int]
    truncated_prefix: bool
    truncated_suffix: bool


def slice_prefix_suffix(
    file_text: str,
    start_line: int,
    end_line: int,
    *,
    prefix_token_budget: int = 2048,
    suffix_token_budget: int = 2048,
) -> FimSlice:
    """Slice ``file_text`` into a FIM prefix/suffix around a Stage-3 symbol.

    ``start_line``/``end_line`` are the 1-indexed, inclusive line range of the
    target symbol (``stage3_ranked_symbols[*].start_line``/``end_line``); the
    symbol body itself is discarded, since the model regenerates it. This
    operates on the base-commit file as given by the caller — it does not
    fetch or resolve ``base_commit`` itself.
    """

    if start_line < 1 or end_line < start_line:
        raise ValueError(f"Invalid symbol line range: start_line={start_line}, end_line={end_line}")

    lines = file_text.splitlines(keepends=True)
    total_lines = len(lines)
    if start_line > total_lines + 1 or end_line > total_lines:
        raise ValueError(
            f"Symbol range [{start_line}, {end_line}] does not fit inside this "
            f"{total_lines}-line file snapshot; the symbol location may be stale."
        )

    prefix_lines_list = lines[: start_line - 1]
    suffix_lines_list = lines[end_line:]

    prefix_text, dropped_from_front = _truncate_keep_tail(prefix_lines_list, prefix_token_budget)
    suffix_text, kept_count = _truncate_keep_head(suffix_lines_list, suffix_token_budget)

    return FimSlice(
        prefix_text=prefix_text,
        suffix_text=suffix_text,
        prefix_lines=(1 + dropped_from_front, start_line - 1),
        suffix_lines=(end_line + 1, end_line + kept_count),
        truncated_prefix=dropped_from_front > 0,
        truncated_suffix=kept_count < len(suffix_lines_list),
    )


def append_ticket_comment_to_prefix(
    prefix_text: str,
    ticket_summary: str,
    *,
    language: str = SUPPORTED_LANGUAGE,
    max_chars: int = 400,
) -> str:
    """Append a comment-formatted Ticket summary to the end of the FIM prefix.

    This gives the model in-context bug information (plan section 5.1, step
    2) formatted as a source comment so it stays syntactically inert even if
    echoed back verbatim. Whitespace/newlines in the Ticket text are
    collapsed and the summary is truncated to ``max_chars`` — this is meant
    to orient the model, not to smuggle the full bug report past the prefix
    token budget.
    """

    comment_char = _COMMENT_PREFIX_BY_LANGUAGE.get(language)
    if comment_char is None:
        raise ValueError(f"Unsupported language for FIM prompt construction: {language!r}")

    summary = " ".join(ticket_summary.split())
    if not summary:
        return prefix_text
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rstrip() + "…"

    comment_line = f"{comment_char} Ticket summary: {summary}\n"
    if prefix_text and not prefix_text.endswith("\n"):
        prefix_text += "\n"
    return prefix_text + comment_line


def validate_syntax(code: str) -> bool:
    """Return True iff ``code`` parses as valid standalone Python source."""

    try:
        ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    return True


# Symbol kinds that are shaped as a def/class statement -- i.e. the kinds
# where "the generated code redefines this symbol" is a meaningful, checkable
# claim. Other kinds (e.g. "module", used for a synthesized whole-file
# candidate) have no single defining statement to look for.
_DEF_SHAPED_SYMBOL_KINDS = {"function", "method", "async function", "async method", "class"}


def contains_expected_symbol_definition(
    generated_code: str,
    *,
    base_indent: int,
    symbol_kind: str,
    symbol_name: str,
) -> bool:
    """Check that ``generated_code`` actually (re)defines the target symbol.

    ``apply_patch()``'s ``syntax_valid`` only confirms the RECONSTRUCTED FILE
    is valid Python -- it says nothing about whether ``generated_code`` is
    the intended replacement. This matters because Python's indentation
    rules do not require a block to be explicitly closed: a degenerate
    completion (e.g. a single stray statement, with no ``def``/``class``
    line at all) can be silently absorbed as more body content of the
    PRECEDING function once spliced back in, producing a perfectly valid
    file that has actually deleted the target symbol entirely. This was
    observed for real during Stage-4 WP1 manual verification (2026-09-12):
    a ``simple_function_body`` FIM completion that was just one call
    expression reported ``syntax_valid=True``/``apply_status=applied_clean``
    while having silently dropped the ``clamp`` function it was supposed to
    replace -- calling code referencing ``clamp`` would raise ``NameError``
    at runtime despite the "clean" apply status.

    This check dedents ``generated_code`` by ``base_indent`` (undoing the
    indentation the symbol sits at in the real file) and looks for a
    top-level ``def``/``class`` node matching ``symbol_name``. For symbol
    kinds this project does not replace as a single definition statement
    (e.g. ``"module"``), the check does not apply and this returns True.
    Callers should treat a patch as usable only when BOTH
    ``ApplyResult.syntax_valid`` and this check pass -- neither one alone is
    sufficient.
    """

    if symbol_kind not in _DEF_SHAPED_SYMBOL_KINDS:
        return True

    prefix = " " * base_indent
    dedented_lines = []
    for line in generated_code.splitlines(keepends=True):
        if not line.strip():
            dedented_lines.append(line)
        elif line.startswith(prefix):
            dedented_lines.append(line[base_indent:])
        else:
            # Line doesn't even have the expected base indent (e.g. the
            # model produced something shallower than the symbol itself) --
            # keep it as-is rather than mangling it further; the parse
            # below will fail or the definition-name check will correctly
            # find no match either way.
            dedented_lines.append(line)
    dedented = "".join(dedented_lines)

    try:
        tree = ast.parse(dedented)
    except SyntaxError:
        return False

    expected_types: tuple[type, ...] = (
        (ast.ClassDef,) if "class" in symbol_kind else (ast.FunctionDef, ast.AsyncFunctionDef)
    )
    return any(
        isinstance(node, expected_types) and node.name == symbol_name for node in tree.body
    )


@dataclass(slots=True)
class ApplyResult:
    """Result of splicing generated code back into the original file (plan section 5.3)."""

    patched_file_text: str
    syntax_valid: bool
    apply_status: str
    diff_unified: str
    notes: list[str] = field(default_factory=list)


def _leading_whitespace_count(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def trim_generated_code_to_symbol_scope(generated_code: str, base_indent: int) -> tuple[str, bool]:
    """Cut ``generated_code`` at the point it stops being the target symbol.

    FIM completions do not reliably self-terminate. Manual verification
    against a real Ollama ``codellama:7b-instruct`` server (see
    ``scripts/manual_check_generate_fim.py``, runs on 2026-09-12) showed the
    model using at least two different, non-standard "end" markers across
    separate runs (``<EOF>``, then ``<INF>`` on a later run) instead of the
    documented ``<EOT>`` -- and llm_client.FIM_STOP_SEQUENCES can only ever
    list markers already observed, never every marker a given checkpoint
    might invent next.

    Rather than chase an open-ended list of ad hoc sentinels, this trims
    based on Python structure instead: the target symbol's own first line
    sits at ``base_indent`` (the indentation ``apply_patch`` measured from
    the original file at the symbol's start line). Once the generated text
    has produced at least one line indented deeper than that (i.e. we are
    inside the symbol's body), the first later non-blank line back at or
    shallower than ``base_indent`` means the model has moved on to something
    else -- a new function, a test, trailing commentary -- and everything
    from that line onward is discarded.

    This intentionally does NOT try to fix a candidate that never produces
    any body content at all (e.g. a single mis-indented line with no
    enclosing ``def``): that is a genuine generation-quality miss for
    ``apply_patch``'s syntax check to catch, not something structural
    trimming can repair.

    Returns ``(trimmed_code, was_trimmed)``.
    """

    lines = generated_code.splitlines(keepends=True)
    seen_deeper_indent = False
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        indent = _leading_whitespace_count(line)
        if indent > base_indent:
            seen_deeper_indent = True
            continue
        if seen_deeper_indent and indent <= base_indent:
            return "".join(lines[:index]), True
    return generated_code, False


def trim_leading_content_before_symbol_definition(
    generated_code: str,
    *,
    symbol_kind: str,
    symbol_name: str,
) -> tuple[str, bool]:
    """Drop anything the model emitted BEFORE the target definition starts.

    ``trim_generated_code_to_symbol_scope()`` only finds where the symbol
    ENDS. Real output also comes with junk at the front: a 2026-09-12 run
    against ``codellama:7b-code`` prefixed the ``Counter.increment`` patch
    with two fabricated "# Ticket summary:" comments describing entirely
    different methods (``decrement``, ``reset``). Those are syntactically
    harmless comments, so every syntax-level check passes -- but they would
    be committed verbatim into the user's class body as part of the patch.

    This finds the line that actually starts the target definition (plus any
    decorator lines immediately above it, which ARE part of the symbol) and
    discards everything before it. If no such definition line is present the
    input is returned untouched, since there is then nothing to anchor on
    and ``contains_expected_symbol_definition()`` will reject the candidate
    anyway.

    Tradeoff worth stating: a genuine explanatory comment the model wrote
    above the definition is dropped too. For patch generation that is the
    right default -- a patch should contain the symbol it claims to replace,
    not free-floating commentary -- but it is a deliberate choice, not an
    oversight.

    Returns ``(trimmed_code, was_trimmed)``.
    """

    if symbol_kind not in _DEF_SHAPED_SYMBOL_KINDS or not symbol_name:
        return generated_code, False

    keyword = "class" if "class" in symbol_kind else "def"
    pattern = re.compile(
        rf"^\s*(?:async\s+)?{keyword}\s+{re.escape(symbol_name)}\s*[\(:]"
    )

    lines = generated_code.splitlines(keepends=True)
    definition_index = next(
        (index for index, line in enumerate(lines) if pattern.match(line)), None
    )
    if definition_index is None:
        return generated_code, False

    # Decorators directly above the definition belong to it; keep them.
    start = definition_index
    while start > 0:
        previous = lines[start - 1].strip()
        if previous.startswith("@"):
            start -= 1
        else:
            break

    if start == 0:
        return generated_code, False
    return "".join(lines[start:]), True


def strip_trailing_blank_lines(generated_code: str) -> tuple[str, bool]:
    """Drop trailing whitespace-only lines from a completion.

    FIM output frequently ends with a stray line containing a single space
    (observed in the 2026-09-12 ``codellama:7b-code`` run). It is harmless
    to the parser but lands in the diff as trailing-whitespace noise, which
    many projects' linters and pre-commit hooks reject.

    Returns ``(trimmed_code, was_trimmed)``.
    """

    lines = generated_code.splitlines(keepends=True)
    end = len(lines)
    while end > 0 and not lines[end - 1].strip():
        end -= 1
    if end == len(lines):
        return generated_code, False
    trimmed = "".join(lines[:end])
    if trimmed and not trimmed.endswith("\n"):
        trimmed += "\n"
    return trimmed, True


def apply_patch(
    *,
    original_file_text: str,
    start_line: int,
    end_line: int,
    generated_code: str,
    file_path: str = "file.py",
    symbol_kind: str | None = None,
    symbol_name: str | None = None,
) -> ApplyResult:
    """Splice ``generated_code`` into ``original_file_text`` at [start_line, end_line] and validate it.

    Passing ``symbol_kind``/``symbol_name`` (both available on every
    ``stage3_ranked_symbols`` entry) enables the symbol-aware cleanup of the
    raw completion -- dropping anything the model emitted before the target
    definition began. Callers should pass them whenever they are known.

    This always reconstructs the patched file from the FULL, untruncated
    ``original_file_text`` — never from the token-truncated prefix/suffix
    ``slice_prefix_suffix`` produces for the prompt — because a candidate can
    only be judged syntactically valid and applicable in the context of a
    real, complete file.

    Per plan section 5.3: syntax failure alone marks ``syntax_error``; if the
    generated code's line count/formatting required an automatic offset fix
    (e.g. a missing trailing newline) to reassemble a parseable file, that is
    marked ``applied_with_offset`` rather than silently accepted as clean, so
    indentation drift is never hidden. Any unexpected failure while
    reconstructing the file is reported as ``apply_failed`` rather than
    raising, so one bad candidate cannot crash a batch run.

    IMPORTANT caveat, confirmed against a real failure during manual
    verification: ``syntax_valid``/``apply_status`` here only say the
    RECONSTRUCTED FILE is valid Python. They do NOT confirm ``generated_code``
    actually redefines the target symbol -- Python's indentation rules do not
    require a block to be explicitly closed, so a degenerate completion (a
    stray statement with no ``def``/``class`` line) can be silently absorbed
    into the PRECEDING symbol's body, producing a file that parses cleanly
    while having deleted the target symbol outright. Callers that know the
    target's ``symbol_kind``/``symbol_name`` (from ``stage3_ranked_symbols``)
    MUST additionally call ``contains_expected_symbol_definition()`` and
    treat the candidate as usable only when both checks pass.
    """

    try:
        if start_line < 1 or end_line < start_line:
            raise ValueError(f"Invalid symbol line range: start_line={start_line}, end_line={end_line}")

        lines = original_file_text.splitlines(keepends=True)
        total_lines = len(lines)
        if start_line > total_lines + 1 or end_line > total_lines:
            raise ValueError(
                f"Symbol range [{start_line}, {end_line}] does not fit inside this "
                f"{total_lines}-line file snapshot; the symbol location may be stale."
            )

        before = lines[: start_line - 1]
        after = lines[end_line:]

        notes: list[str] = []
        offset = False

        body = generated_code
        if symbol_kind and symbol_name:
            body, was_trimmed = trim_leading_content_before_symbol_definition(
                body, symbol_kind=symbol_kind, symbol_name=symbol_name
            )
            if was_trimmed:
                offset = True
                notes.append(
                    "generated_code emitted content before the target definition began "
                    "(e.g. commentary about unrelated symbols); leading content was trimmed."
                )
        if start_line - 1 < len(lines):
            base_indent = _leading_whitespace_count(lines[start_line - 1])
            body, was_trimmed = trim_generated_code_to_symbol_scope(body, base_indent)
            if was_trimmed:
                offset = True
                notes.append(
                    "generated_code continued past the target symbol's own scope "
                    "(the model did not stop cleanly); trailing content was trimmed."
                )
        body, stripped_blanks = strip_trailing_blank_lines(body)
        if stripped_blanks:
            offset = True
            notes.append("trailing whitespace-only line(s) were stripped from generated_code.")
        if body and after and not body.endswith("\n"):
            body += "\n"
            offset = True
            notes.append(
                "generated_code lacked a trailing newline before the following context; one was appended."
            )
        if before and not before[-1].endswith("\n"):
            before = before[:-1] + [before[-1] + "\n"]
            offset = True
            notes.append("preceding context lacked a trailing newline; one was appended.")

        patched_text = "".join(before) + body + "".join(after)
        syntax_valid = validate_syntax(patched_text)

        if not syntax_valid:
            apply_status = "syntax_error"
        elif offset:
            apply_status = "applied_with_offset"
        else:
            apply_status = "applied_clean"

        diff_unified = "".join(
            difflib.unified_diff(
                original_file_text.splitlines(keepends=True),
                patched_text.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
        )

        return ApplyResult(
            patched_file_text=patched_text,
            syntax_valid=syntax_valid,
            apply_status=apply_status,
            diff_unified=diff_unified,
            notes=notes,
        )
    except Exception as exc:  # defensive: one bad candidate must not crash a batch run
        return ApplyResult(
            patched_file_text=original_file_text,
            syntax_valid=False,
            apply_status="apply_failed",
            diff_unified="",
            notes=[f"apply_failed: {exc}"],
        )


def apply_patch_and_verify_symbol(
    *,
    original_file_text: str,
    start_line: int,
    end_line: int,
    generated_code: str,
    file_path: str = "file.py",
    symbol_kind: str | None = None,
    symbol_name: str | None = None,
) -> ApplyResult:
    """``apply_patch()`` plus the mandatory ``contains_expected_symbol_definition()`` check.

    This is the function Stage-4 WP2's batch pipeline (and any other caller
    that has ``symbol_kind``/``symbol_name`` from ``stage3_ranked_symbols``)
    should call instead of ``apply_patch()`` directly. ``apply_patch()`` on
    its own cannot make this guarantee -- see its "IMPORTANT caveat"
    docstring paragraph -- because a real WP1 manual-verification run
    (2026-09-12) produced a candidate that was ``syntax_valid=True`` /
    ``apply_status=applied_clean`` while having silently deleted the target
    function entirely (the generated content was absorbed as extra body
    lines of the PRECEDING function, since Python does not require a block
    to be explicitly closed).

    When ``symbol_kind``/``symbol_name`` are both given and ``apply_patch()``
    reported ``applied_clean``/``applied_with_offset`` but the target symbol
    was NOT actually (re)defined, this downgrades ``apply_status`` to
    ``apply_failed`` and appends an explanatory note -- rather than leaving a
    misleading "applied" status for a candidate that deleted its own target.
    ``apply_patch()`` itself is left unchanged (its four ``apply_status``
    values and existing test suite are the frozen WP1 data contract; this
    wraps it rather than altering its semantics).

    The symbol-definition check runs against ``generated_code`` exactly as
    given -- the same convention ``scripts/manual_check_generate_fim.py``
    already uses -- not against whatever ``apply_patch()`` internally trimmed
    it to, since the base indent is measured from the ORIGINAL file's start
    line either way.

    When ``symbol_kind``/``symbol_name`` are omitted (unknown to the caller),
    this behaves exactly like ``apply_patch()`` -- the check is skipped, not
    silently assumed to pass.
    """

    result = apply_patch(
        original_file_text=original_file_text,
        start_line=start_line,
        end_line=end_line,
        generated_code=generated_code,
        file_path=file_path,
        symbol_kind=symbol_kind,
        symbol_name=symbol_name,
    )

    if (
        symbol_kind
        and symbol_name
        and result.apply_status in ("applied_clean", "applied_with_offset")
    ):
        lines = original_file_text.splitlines(keepends=True)
        base_indent = _leading_whitespace_count(lines[start_line - 1]) if start_line - 1 < len(lines) else 0
        symbol_defined = contains_expected_symbol_definition(
            generated_code,
            base_indent=base_indent,
            symbol_kind=symbol_kind,
            symbol_name=symbol_name,
        )
        if not symbol_defined:
            result.apply_status = "apply_failed"
            result.notes.append(
                f"apply_failed: generated_code did not actually (re)define {symbol_kind} "
                f"{symbol_name!r} -- syntax was valid but the target symbol is missing from "
                "the reassembled file (see contains_expected_symbol_definition())."
            )

    return result


def compute_symbol_id(*, file_path: str, symbol_qualified_name: str, start_line: int, end_line: int) -> str:
    """Stable id for a Stage-3 symbol target, used as ``PatchRecordV1.target_symbol_id``."""

    digest = hashlib.sha256()
    for part in (file_path, symbol_qualified_name, str(start_line), str(end_line)):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return f"sha256:{digest.hexdigest()}"


def compute_patch_id(*, ticket_id: str, target_symbol_id: str, sampling_index: int, generated_code: str) -> str:
    """Stable id for one generated patch candidate (plan section 4.2).

    Built from ``ticket_id``, ``target_symbol_id``, ``sampling_index`` and a
    hash of ``generated_code`` itself, so repeated samples of the same Ticket
    and symbol are distinguishable and de-duplicable across reruns.
    """

    digest = hashlib.sha256()
    digest.update(ticket_id.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(target_symbol_id.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(str(sampling_index).encode("utf-8"))
    digest.update(b"\x00")
    digest.update(generated_code.encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


@dataclass(slots=True)
class PatchRecordV1:
    """Data contract for one generated patch candidate (plan section 4.2)."""

    patch_id: str
    ticket_id: str
    repo: str
    base_commit: str
    target_symbol_id: str
    file_path: str
    fim_prefix_lines: tuple[int, int]
    fim_suffix_lines: tuple[int, int]
    generated_code: str
    sampling_index: int
    temperature: float
    syntax_valid: bool
    apply_status: str
    diff_unified: str
    generation_source: str
    model_digest: str
    prompt_version: str
    generated_at: str
    schema_version: str = PATCH_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.apply_status not in APPLY_STATUS_VALUES:
            raise ValueError(f"Unknown apply_status: {self.apply_status!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "patch_id": self.patch_id,
            "ticket_id": self.ticket_id,
            "repo": self.repo,
            "base_commit": self.base_commit,
            "target_symbol_id": self.target_symbol_id,
            "file_path": self.file_path,
            "fim_prefix_lines": list(self.fim_prefix_lines),
            "fim_suffix_lines": list(self.fim_suffix_lines),
            "generated_code": self.generated_code,
            "sampling_index": self.sampling_index,
            "temperature": self.temperature,
            "syntax_valid": self.syntax_valid,
            "apply_status": self.apply_status,
            "diff_unified": self.diff_unified,
            "generation_source": self.generation_source,
            "model_digest": self.model_digest,
            "prompt_version": self.prompt_version,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_generation(
        cls,
        *,
        ticket_id: str,
        repo: str,
        base_commit: str,
        file_path: str,
        symbol_qualified_name: str,
        start_line: int,
        end_line: int,
        fim_slice: FimSlice,
        generated_code: str,
        sampling_index: int,
        temperature: float,
        apply_result: ApplyResult,
        generation_source: str,
        model_digest: str,
        prompt_version: str,
        generated_at: str | None = None,
    ) -> "PatchRecordV1":
        """Build a ``PatchRecordV1`` from one FIM sample plus its apply/validation result."""

        target_symbol_id = compute_symbol_id(
            file_path=file_path,
            symbol_qualified_name=symbol_qualified_name,
            start_line=start_line,
            end_line=end_line,
        )
        patch_id = compute_patch_id(
            ticket_id=ticket_id,
            target_symbol_id=target_symbol_id,
            sampling_index=sampling_index,
            generated_code=generated_code,
        )
        return cls(
            patch_id=patch_id,
            ticket_id=ticket_id,
            repo=repo,
            base_commit=base_commit,
            target_symbol_id=target_symbol_id,
            file_path=file_path,
            fim_prefix_lines=fim_slice.prefix_lines,
            fim_suffix_lines=fim_slice.suffix_lines,
            generated_code=generated_code,
            sampling_index=sampling_index,
            temperature=temperature,
            syntax_valid=apply_result.syntax_valid,
            apply_status=apply_result.apply_status,
            diff_unified=apply_result.diff_unified,
            generation_source=generation_source,
            model_digest=model_digest,
            prompt_version=prompt_version,
            generated_at=generated_at or _utc_now_iso(),
        )
