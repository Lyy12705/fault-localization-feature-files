"""Stage-4 WP2: batch FIM patch generation over conditional-eligible Tickets.

Per STAGE4_PATCH_GENERATION_IMPLEMENTATION_PLAN_ZH.md section 9 (WP2):

    對 conditional-eligible 的 development Tickets（沿用既有 46 票集合，與
    WP4 Symbol Pilot 一致，避免引入新的抽樣差異）執行多樣本 FIM 補丁生成；
    輸出 PatchRecordV1；統計 Syntax Valid Rate 與 Apply Rate。

For each ticket row in ``--predictions`` (the ``stage3_deterministic_g2``-style
output described in plan section 13's command interface -- each row carries
``ticket_id``/``repo``/``base_commit``/``stage3_ranked_symbols``):

    1. Skip tickets that are not conditional-eligible (``stage3_ranked_symbols``
       empty -- Stage-3 found no candidate at all; see ``is_conditional_eligible``).
    2. Take the top ``--symbol-topk`` (default 1) ranked symbol(s).
    3. Resolve a read-only checkout of (repo, base_commit) via
       ``utils.repo_snapshot`` and read the target file's full text -- needed
       because ``stage3_ranked_symbols[*].code_text`` only holds the symbol's
       own body, not the surrounding file ``slice_prefix_suffix`` cuts from.
    4. Slice the FIM prefix/suffix (frozen token budgets from ``--config``),
       optionally append a Ticket-summary comment (only if ``--tickets`` was
       given and a matching row has bug-report text -- this is an
       enhancement, not a hard requirement of the plan's command interface).
    5. Sample one FIM completion per frozen temperature in ``--config``
       (``sampling_index`` == the temperature's position in that list).
    6. Validate with ``apply_patch_and_verify_symbol`` (syntax AND "symbol
       actually redefined" -- see that function's docstring for why both are
       required) and wrap the result as a ``PatchRecordV1``.

One ticket's failure (repo not cached, base_commit unavailable, FIM call
error, ...) is recorded and skipped rather than aborting the batch -- matches
this project's existing batch-script convention (e.g.
``run_swebench_lite_fault_localization.py``).

This script requires a real local Ollama server with the FIM model pulled
(``ollama pull codellama:7b-code`` -- NOT ``-instruct``, see
``llm_client.DEFAULT_FIM_MODEL``'s comment) and a populated repository cache
(``--repo-cache-dir``, e.g. built by ``scripts/prefetch_swebench_repositories.py``).
Per plan section 11.3, run this in stages: ``--limit 1`` first, then
``--limit 10``, then the full 46-ticket set -- do not jump straight to the
full pilot.

Usage:

    python scripts/generate_stage4_patches.py \\
      --predictions reports/fault_localization/stage3_deterministic_g2_dev_v1/predictions.jsonl \\
      --repo-cache-dir data/repositories \\
      --config configs/fault_localization/stage4_patch_generation_v1.json \\
      --output reports/fault_localization/stage4_patch_generation_dev_v1/patches.jsonl \\
      --limit 1
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.llm_client import DEFAULT_FIM_MODEL, OllamaClient  # noqa: E402
from utils.patch_generation import (  # noqa: E402
    PatchRecordV1,
    apply_patch_and_verify_symbol,
    append_ticket_comment_to_prefix,
    extract_symbol_text,
    is_supported_language,
    resolve_num_predict,
    resolve_symbol_line_range,
    slice_prefix_suffix,
)
from utils.repo_snapshot import (  # noqa: E402
    RepoSnapshotError,
    materialize_commit_snapshot,
    read_file_text,
    resolve_repository_path,
)

DEFAULT_CONFIG_PATH = "configs/fault_localization/stage4_patch_generation_v1.json"
DEFAULT_SNAPSHOT_SUBDIR = ".stage4_snapshots"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("version https://git-lfs.github.com/spec/v1"):
                raise ValueError(
                    f"{path} is still a Git LFS pointer, not the real file content. "
                    "Run `git lfs pull` in the repo root first."
                )
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON ({exc})") from None
    return rows


def load_config(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_ticket_id_allowlist(path: Path) -> set[str]:
    """Read a ticket_id allowlist from either a JSONL file (any row with a
    ``ticket_id`` field -- e.g. ``pilot_46tickets.jsonl`` itself) or a plain
    text file with one ticket_id per line.

    Plan section 9 (WP2) requires reusing the EXACT SAME 46-ticket set as the
    Stage-3 WP4 Symbol Pilot ("避免引入新的抽樣差異" -- do not introduce a new
    sampling difference). ``--predictions`` typically points at the full
    Stage-3 development-split predictions file (hundreds+ of tickets), so
    without this filter a batch run would silently cover a different, larger
    ticket population than the one WP4's numbers are reported against.
    """

    ids: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            ids.add(line)
            continue
        if isinstance(row, dict):
            ticket_id = str(row.get("ticket_id") or "")
            if ticket_id:
                ids.add(ticket_id)
        else:
            ids.add(str(row))
    return ids


def is_conditional_eligible(ticket_row: dict[str, Any]) -> bool:
    """A ticket is conditional-eligible iff Stage-3 found ANY symbol candidate.

    Matches Stage-3 WP4's own 'conditional' recall definition (plan section
    9, config's ``eligibility`` block) so Stage-4's Patch Apply Rate stays
    comparable to it rather than measuring a differently-sampled ticket set.
    """

    return bool(ticket_row.get("stage3_ranked_symbols"))


def select_target_symbols(ticket_row: dict[str, Any], *, symbol_topk: int) -> list[dict[str, Any]]:
    ranked = ticket_row.get("stage3_ranked_symbols") or []
    return list(ranked[: max(0, symbol_topk)])


# Fields that describe the BUG (safe to show the model: this is what a
# developer reads before writing a fix).
TICKET_DESCRIPTION_FIELDS = ("problem_statement", "bug_report", "issue_text", "description", "title")

# Fields that carry, or can carry, the GROUND TRUTH and must never reach a
# prompt. Plan section 4.1: "developer patch（僅用於事後對照與 held-out
# correctness 檢查，不得出現在任何 LLM prompt 中）". The real ticket files this
# script is pointed at (e.g.
# data/fault_localization/swebench_full/stage3_symbol_gold/development_source_tickets.jsonl)
# DO contain a "patch" field with the developer's actual fix, plus
# "fail_to_pass"/"pass_to_pass" test names and "hints_text". Leaking any of
# these into the FIM prefix would silently invalidate every Stage-4 number,
# and it would look like a great result rather than a bug -- so the ban is
# enforced here in code rather than left to whichever fields a future caller
# happens to read.
TICKET_GROUND_TRUTH_FIELDS = frozenset(
    {"patch", "test_patch", "gold_patch", "fail_to_pass", "pass_to_pass", "hints_text"}
)


class SymbolRangeUnresolvedError(RuntimeError):
    """A Stage-3 candidate's definition could not be located in the real source.

    Raised instead of falling back to Stage-3's chunk range, which would mean
    patching boundaries that are not a definition at all.
    """


def _ticket_comment_text(ticket_id: str, tickets_by_id: dict[str, dict[str, Any]]) -> str:
    """Return bug-description text for the FIM prefix comment, or "" if none.

    Only reads from ``TICKET_DESCRIPTION_FIELDS``; ground-truth fields are
    never consulted (see ``TICKET_GROUND_TRUTH_FIELDS``).
    """

    row = tickets_by_id.get(ticket_id)
    if not row:
        return ""
    for key in TICKET_DESCRIPTION_FIELDS:
        if key in TICKET_GROUND_TRUTH_FIELDS:  # defensive: keep the two lists from ever overlapping
            raise AssertionError(f"{key!r} is a ground-truth field and must never be sent to the model.")
        value = row.get(key)
        if value:
            return str(value)
    return ""


def generate_patch_candidates(
    *,
    client: OllamaClient,
    ticket_id: str,
    repo: str,
    base_commit: str,
    file_path: str,
    file_text: str,
    symbol: dict[str, Any],
    temperatures: list[float],
    prefix_token_budget: int,
    suffix_token_budget: int,
    num_predict_headroom: float,
    min_num_predict: int,
    max_num_predict: int,
    use_native_suffix: bool,
    ticket_comment: str,
    prompt_version: str,
    model_digest: str,
) -> list[PatchRecordV1]:
    """Generate and validate one FIM sample per temperature for one target symbol.

    Never raises for a single sample's generation/validation failure -- a
    bad sample is recorded via ``PatchRecordV1.apply_status`` (syntax_error /
    apply_failed), not dropped or allowed to abort the batch. Only a hard
    error resolving the FIM call itself propagates, since that indicates a
    systemic problem (server down, model not pulled) the caller should stop
    on rather than silently keep sampling.
    """

    symbol_kind = str(symbol.get("symbol_kind") or "")
    symbol_qualified_name = str(symbol.get("symbol_qualified_name") or "")
    symbol_name = str(symbol.get("symbol_name") or symbol_qualified_name.rsplit(".", maxsplit=1)[-1])

    # Stage-3's start_line/end_line are the boundaries of the retrieval CHUNK,
    # not of the symbol's definition -- see resolve_symbol_line_range(). Patch
    # against the chunk range and the target is a fragment of several
    # definitions ending mid-body, which no completion can satisfy. Resolution
    # failures are raised (not silently fallen back on) so the caller records
    # the ticket as skipped rather than generating against wrong boundaries.
    resolved = resolve_symbol_line_range(
        file_text,
        symbol_qualified_name=symbol_qualified_name,
        symbol_name=symbol_name,
        hint_start_line=int(symbol["start_line"]),
        hint_end_line=int(symbol["end_line"]),
    )
    if not resolved.resolved:
        raise SymbolRangeUnresolvedError(
            f"could not resolve {symbol_kind} {symbol_qualified_name or symbol_name!r} in {file_path}: {resolved.reason}"
        )
    start_line, end_line = resolved.start_line, resolved.end_line

    # Size the generation budget to THIS symbol. A fixed cap truncates any
    # symbol larger than it, mid-statement, which surfaces as a bogus
    # "syntax_error" -- see resolve_num_predict()'s docstring for the real
    # 0/3 run that this prevents.
    num_predict = resolve_num_predict(
        extract_symbol_text(file_text, start_line, end_line),
        headroom=num_predict_headroom,
        minimum=min_num_predict,
        maximum=max_num_predict,
    )

    fim_slice = slice_prefix_suffix(
        file_text,
        start_line,
        end_line,
        prefix_token_budget=prefix_token_budget,
        suffix_token_budget=suffix_token_budget,
    )
    prefix_text = (
        append_ticket_comment_to_prefix(fim_slice.prefix_text, ticket_comment)
        if ticket_comment
        else fim_slice.prefix_text
    )

    records: list[PatchRecordV1] = []
    for sampling_index, temperature in enumerate(temperatures):
        generated_code = client.generate_fim(
            prefix_text,
            fim_slice.suffix_text,
            temperature=temperature,
            num_predict=num_predict,
            use_native_suffix=use_native_suffix,
        )
        apply_result = apply_patch_and_verify_symbol(
            original_file_text=file_text,
            start_line=start_line,
            end_line=end_line,
            generated_code=generated_code,
            file_path=file_path,
            symbol_kind=symbol_kind,
            symbol_name=symbol_name,
        )
        record = PatchRecordV1.from_generation(
            ticket_id=ticket_id,
            repo=repo,
            base_commit=base_commit,
            file_path=file_path,
            symbol_qualified_name=str(symbol.get("symbol_qualified_name") or symbol_name),
            start_line=start_line,
            end_line=end_line,
            fim_slice=fim_slice,
            generated_code=generated_code,
            sampling_index=sampling_index,
            temperature=temperature,
            apply_result=apply_result,
            generation_source=f"{client.fim_model}{'-native-suffix' if use_native_suffix else '-raw-psm'}",
            model_digest=model_digest,
            prompt_version=prompt_version,
        )
        records.append(record)
    return records


def run_batch(
    *,
    predictions_rows: list[dict[str, Any]],
    tickets_by_id: dict[str, dict[str, Any]],
    client: OllamaClient,
    config: dict[str, Any],
    repo_cache_dir: Path,
    snapshot_cache_dir: Path,
    symbol_topk: int,
    clone_missing: bool,
    fetch_missing_commits: bool,
    model_digest: str,
    limit: int | None,
    ticket_id_allowlist: set[str] | None = None,
) -> tuple[list[PatchRecordV1], list[dict[str, Any]], Counter]:
    """Returns (patch_records, per_ticket_failures, status_counts).

    ``ticket_id_allowlist``, when given, is applied BEFORE eligibility
    filtering and BEFORE ``limit`` slicing, so ``--limit 10`` staged runs
    take their first 10 from the allowed set (e.g. the 46-ticket WP4 pilot
    set) rather than from whatever larger population ``predictions_rows``
    happens to contain.
    """

    fim_cfg = config["fim"]
    temperatures = list(config["sampling"]["temperatures"])
    prompt_version = config["prompt_version"]

    rows = predictions_rows
    if ticket_id_allowlist is not None:
        rows = [row for row in rows if str(row.get("ticket_id") or "") in ticket_id_allowlist]

    eligible_rows = [row for row in rows if is_conditional_eligible(row)]
    if limit is not None:
        eligible_rows = eligible_rows[:limit]

    patch_records: list[PatchRecordV1] = []
    failures: list[dict[str, Any]] = []
    status_counts: Counter = Counter()

    for row in eligible_rows:
        ticket_id = str(row.get("ticket_id") or "<unknown>")
        repo = str(row.get("repo") or "")
        base_commit = str(row.get("base_commit") or "")
        symbols = select_target_symbols(row, symbol_topk=symbol_topk)
        if not symbols:
            continue

        try:
            if not repo or not base_commit:
                raise RepoSnapshotError(f"Ticket {ticket_id} is missing repo/base_commit.")
            source_repo = resolve_repository_path(
                {"repo": repo}, repo_cache_dir=repo_cache_dir, clone_missing=clone_missing
            )
            snapshot_path = materialize_commit_snapshot(
                source_repo,
                repo=repo,
                base_commit=base_commit,
                snapshot_cache_dir=snapshot_cache_dir,
                fetch_missing_commits=fetch_missing_commits,
            )
        except RepoSnapshotError as exc:
            failures.append({"ticket_id": ticket_id, "reason": "repo_resolution_failed", "detail": str(exc)})
            status_counts["repo_resolution_failed"] += 1
            continue

        ticket_comment = _ticket_comment_text(ticket_id, tickets_by_id)
        # Track this explicitly: with no bug description in the prompt the
        # model has nothing to aim at and will just continue the file
        # plausibly (a real 2026-09-12 run regenerated the module's import
        # block). That failure is invisible in the apply/syntax numbers, so
        # it gets its own line in the summary rather than being inferred.
        status_counts["ticket_context_present" if ticket_comment else "ticket_context_missing"] += 1

        for symbol in symbols:
            file_path = str(symbol.get("file_path") or "")
            if not file_path or not is_supported_language(file_path):
                failures.append(
                    {"ticket_id": ticket_id, "reason": "unsupported_language", "detail": file_path}
                )
                status_counts["unsupported_language"] += 1
                continue
            try:
                file_text = read_file_text(snapshot_path, file_path)
            except RepoSnapshotError as exc:
                failures.append({"ticket_id": ticket_id, "reason": "file_read_failed", "detail": str(exc)})
                status_counts["file_read_failed"] += 1
                continue

            try:
                records = generate_patch_candidates(
                    client=client,
                    ticket_id=ticket_id,
                    repo=repo,
                    base_commit=base_commit,
                    file_path=file_path,
                    file_text=file_text,
                    symbol=symbol,
                    temperatures=temperatures,
                    prefix_token_budget=fim_cfg["prefix_token_budget"],
                    suffix_token_budget=fim_cfg["suffix_token_budget"],
                    num_predict_headroom=float(fim_cfg.get("num_predict_headroom", 2.0)),
                    min_num_predict=int(fim_cfg.get("min_num_predict", 256)),
                    max_num_predict=int(fim_cfg.get("max_num_predict", 4096)),
                    use_native_suffix=fim_cfg["use_native_suffix"],
                    ticket_comment=ticket_comment,
                    prompt_version=prompt_version,
                    model_digest=model_digest,
                )
            except SymbolRangeUnresolvedError as exc:
                # Distinct from a FIM failure: the candidate never became a
                # usable patch target, so no sample was attempted. Counted
                # separately so a run whose input symbols cannot be located
                # is obvious rather than hiding inside "fim_call_failed".
                failures.append(
                    {"ticket_id": ticket_id, "reason": "symbol_range_unresolved", "detail": str(exc)}
                )
                status_counts["symbol_range_unresolved"] += 1
                continue
            except Exception as exc:  # noqa: BLE001 - one bad ticket must not abort the batch
                failures.append({"ticket_id": ticket_id, "reason": "fim_call_failed", "detail": str(exc)})
                status_counts["fim_call_failed"] += 1
                continue

            patch_records.extend(records)
            for record in records:
                status_counts[record.apply_status] += 1

    return patch_records, failures, status_counts


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def print_summary(status_counts: Counter, failures: list[dict[str, Any]], total_candidates: int) -> None:
    print("=== Stage-4 WP2 patch generation summary ===")
    print(f"Total patch candidates generated: {total_candidates}")

    with_context = status_counts.get("ticket_context_present", 0)
    without_context = status_counts.get("ticket_context_missing", 0)
    if with_context or without_context:
        print(f"Tickets with a bug description in the prompt: {with_context}/{with_context + without_context}")
        if without_context:
            print(
                "  WARNING: tickets without a bug description give the model nothing to aim at; "
                "pass --tickets pointing at the ticket source file."
            )
    if total_candidates:
        syntax_valid = status_counts.get("applied_clean", 0) + status_counts.get("applied_with_offset", 0)
        print(f"Syntax Valid Rate:  {syntax_valid}/{total_candidates} ({syntax_valid / total_candidates:.1%})")
        print(f"Apply Rate (usable, both syntax AND target symbol confirmed):")
        print(f"  applied_clean:        {status_counts.get('applied_clean', 0)}")
        print(f"  applied_with_offset:  {status_counts.get('applied_with_offset', 0)}")
        print("Failure reason distribution:")
        print(f"  syntax_error:         {status_counts.get('syntax_error', 0)}")
        print(f"  apply_failed:         {status_counts.get('apply_failed', 0)} (includes: target symbol not actually redefined)")
    if failures:
        print()
        print(f"Tickets/symbols skipped before any FIM sample was generated ({len(failures)}):")
        reason_counts = Counter(f["reason"] for f in failures)
        for reason, count in reason_counts.most_common():
            print(f"  {reason}: {count}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", required=True, help="Stage-3 predictions.jsonl (ticket_id/repo/base_commit/stage3_ranked_symbols).")
    parser.add_argument(
        "--ticket-ids-from",
        default=None,
        help="Restrict to this ticket_id set (JSONL with a ticket_id field, or one id per line). "
        "Plan section 9 requires reusing the same 46-ticket WP4 pilot set -- pass "
        "reports/fault_localization/stage3_wp4_pilot/pilot_46tickets.jsonl for that.",
    )
    parser.add_argument("--tickets", default=None, help="Optional raw ticket source (for a Ticket-summary comment); ticket_id-keyed.")
    parser.add_argument("--repo-cache-dir", default="data/repositories")
    parser.add_argument("--snapshot-cache-dir", default=None, help=f"Defaults to <repo-cache-dir>/{DEFAULT_SNAPSHOT_SUBDIR}")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--model", default=None, help="Override the FIM model tag from --config/DEFAULT_FIM_MODEL.")
    parser.add_argument("--model-digest", default=None, help="Real digest string (e.g. from `ollama show <model>`); a placeholder is used if omitted.")
    parser.add_argument("--url", default="http://localhost:11434/api/generate")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--symbol-topk", type=int, default=None, help="Override symbol_selection.symbol_topk from --config.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N conditional-eligible tickets (for staged smoke runs).")
    parser.add_argument("--clone-missing", action="store_true")
    parser.add_argument("--fetch-missing-commits", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    predictions_rows = load_jsonl(Path(args.predictions))
    tickets_by_id: dict[str, dict[str, Any]] = {}
    if args.tickets:
        for row in load_jsonl(Path(args.tickets)):
            ticket_id = str(row.get("ticket_id") or row.get("instance_id") or row.get("id") or "")
            if ticket_id:
                tickets_by_id[ticket_id] = row

    symbol_topk = args.symbol_topk if args.symbol_topk is not None else int(config["symbol_selection"]["symbol_topk"])
    repo_cache_dir = Path(args.repo_cache_dir)
    snapshot_cache_dir = (
        Path(args.snapshot_cache_dir) if args.snapshot_cache_dir else repo_cache_dir / DEFAULT_SNAPSHOT_SUBDIR
    )
    model_digest = args.model_digest or f"placeholder:{args.model or config.get('fim', {}).get('model') or DEFAULT_FIM_MODEL}"

    client = OllamaClient(
        url=args.url,
        fim_model=args.model or DEFAULT_FIM_MODEL,
        timeout=args.timeout,
    )

    ticket_id_allowlist = load_ticket_id_allowlist(Path(args.ticket_ids_from)) if args.ticket_ids_from else None

    print(f"FIM model: {client.fim_model}")
    scoped_rows = (
        [r for r in predictions_rows if str(r.get("ticket_id") or "") in ticket_id_allowlist]
        if ticket_id_allowlist is not None
        else predictions_rows
    )
    if ticket_id_allowlist is not None:
        print(f"Ticket allowlist ({args.ticket_ids_from}): {len(ticket_id_allowlist)} id(s), {len(scoped_rows)} found in --predictions.")
    print(f"Conditional-eligible ticket pool: {sum(1 for r in scoped_rows if is_conditional_eligible(r))}/{len(scoped_rows)}")
    if args.limit is not None:
        print(f"--limit {args.limit}: staged run, not the full set.")
    print()

    patch_records, failures, status_counts = run_batch(
        predictions_rows=predictions_rows,
        tickets_by_id=tickets_by_id,
        client=client,
        config=config,
        repo_cache_dir=repo_cache_dir,
        snapshot_cache_dir=snapshot_cache_dir,
        symbol_topk=symbol_topk,
        clone_missing=args.clone_missing,
        fetch_missing_commits=args.fetch_missing_commits,
        model_digest=model_digest,
        limit=args.limit,
        ticket_id_allowlist=ticket_id_allowlist,
    )

    _write_jsonl(Path(args.output), [record.to_dict() for record in patch_records])
    print(f"Wrote {len(patch_records)} patch record(s) to {args.output}")
    print()
    print_summary(status_counts, failures, total_candidates=len(patch_records))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
