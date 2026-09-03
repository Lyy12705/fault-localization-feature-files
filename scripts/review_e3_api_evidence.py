#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


CLASSIFICATION_LABELS = {
    "correct_mapping": "正確對應",
    "irrelevant_mapping": "無關對應",
    "relationship_correct_not_modified": "關係正確但非本次修改位置",
    "unreviewed": "待人工確認",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and finalize a 30-case E3-C API evidence review."
    )
    parser.add_argument("--tickets", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--predictions", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260822)
    parser.add_argument(
        "--decisions",
        default=None,
        help="Optional JSON object mapping Ticket ID to classification and reason.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.sample_size <= 0:
        raise ValueError("sample-size must be positive.")
    tickets = read_jsonl(Path(args.tickets))
    gold = read_jsonl(Path(args.gold))
    predictions: list[dict[str, Any]] = []
    for value in args.predictions:
        predictions.extend(read_jsonl(Path(value)))
    cases = build_api_evidence_cases(tickets, gold, predictions)
    if len(cases) < args.sample_size:
        raise ValueError(
            f"Only {len(cases)} predictions contain API evidence; "
            f"cannot sample {args.sample_size}."
        )
    sample = sample_cases(cases, size=args.sample_size, seed=args.seed)
    decisions = load_decisions(Path(args.decisions)) if args.decisions else {}
    sample = apply_decisions(sample, decisions, require_all=bool(args.decisions))
    summary = summarize(sample, pool_size=len(cases), seed=args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_scope": "Development E3-C API implementation evidence audit",
        "classification_unit": "one Ticket with returned API implementation evidence",
        "classification_rules": classification_rules(),
        "data_policy": (
            "Gold files are used only after ranking for Development error analysis; "
            "they are never retrieval input."
        ),
        "sources": {
            "tickets": str(Path(args.tickets)),
            "gold": str(Path(args.gold)),
            "predictions": [str(Path(value)) for value in args.predictions],
            "decisions": str(Path(args.decisions)) if args.decisions else "",
        },
        "summary": summary,
        "cases": sample,
    }
    json_path = output_dir / "e3_c_api_evidence_review_30.json"
    csv_path = output_dir / "e3_c_api_evidence_review_30.csv"
    markdown_path = output_dir / "E3_C_API_EVIDENCE_REVIEW_30_ZH.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(csv_path, sample)
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "csv": str(csv_path),
                "report": str(markdown_path),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_api_evidence_cases(
    tickets: Iterable[dict[str, Any]],
    gold_rows: Iterable[dict[str, Any]],
    predictions: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    tickets_by_id = {ticket_id(row): row for row in tickets if ticket_id(row)}
    gold_by_id = {ticket_id(row): row for row in gold_rows if ticket_id(row)}
    prediction_by_id: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        current_id = ticket_id(prediction)
        if current_id:
            prediction_by_id[current_id] = prediction

    cases: list[dict[str, Any]] = []
    for current_id, prediction in prediction_by_id.items():
        if current_id not in tickets_by_id or current_id not in gold_by_id:
            raise ValueError(f"Missing Ticket or Gold row for prediction: {current_id}")
        evidence = api_evidence_from_prediction(prediction)
        if not evidence:
            continue
        cases.append(
            build_case(
                ticket=tickets_by_id[current_id],
                gold=gold_by_id[current_id],
                prediction=prediction,
                evidence=evidence,
            )
        )
    return cases


def api_evidence_from_prediction(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for position, candidate in enumerate(
        prediction.get("stage1_candidate_files") or [], start=1
    ):
        signals = candidate.get("scoring_signals") or {}
        for raw in signals.get("api_implementation_evidence") or []:
            if not isinstance(raw, dict) or not raw.get("file_path"):
                continue
            row = dict(raw)
            row["candidate_rank"] = int(candidate.get("rank") or position)
            signature = (
                str(row.get("ticket_symbol") or ""),
                str(row.get("api_symbol") or ""),
                str(row.get("source_file") or ""),
                str(row.get("implementation_symbol") or ""),
                normalize_path(str(row.get("file_path") or "")),
            )
            if signature in seen:
                continue
            seen.add(signature)
            evidence.append(row)
    return evidence


def build_case(
    *,
    ticket: dict[str, Any],
    gold: dict[str, Any],
    prediction: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_files = unique_paths(gold.get("fixed_files") or gold.get("modified_files") or [])
    gold_keys = {normalize_path(path): path for path in gold_files}
    implementation_files = unique_paths(row.get("file_path") or "" for row in evidence)
    source_files = unique_paths(row.get("source_file") or "" for row in evidence)
    implementation_matches = [
        path for path in implementation_files if normalize_path(path) in gold_keys
    ]
    source_matches = [path for path in source_files if normalize_path(path) in gold_keys]
    hint = (
        "correct_mapping"
        if implementation_matches
        else "relationship_correct_not_modified"
        if source_matches
        else "unreviewed"
    )
    diagnostics = (prediction.get("stage1_diagnostics") or {}).get(
        "symbol_expansion"
    ) or {}
    return {
        "ticket_id": ticket_id(ticket),
        "repo": str(gold.get("repo") or ticket.get("repo") or ""),
        "title": str(ticket.get("title") or ""),
        "description": str(ticket.get("description") or ticket.get("body") or "")[:2000],
        "ticket_program_names": sorted(
            {str(value) for value in diagnostics.get("ticket_program_names") or []}
        ),
        "gold_files": gold_files,
        "implementation_files": implementation_files,
        "source_api_files": source_files,
        "matching_implementation_gold_files": implementation_matches,
        "matching_source_gold_files": source_matches,
        "automatic_hint": hint,
        "classification": "unreviewed",
        "classification_zh": CLASSIFICATION_LABELS["unreviewed"],
        "review_reason": "",
        "evidence_count": len(evidence),
        "relation_counts": dict(
            sorted(Counter(str(row.get("relation_type") or "") for row in evidence).items())
        ),
        "evidence_details": evidence,
    }


def sample_cases(cases: list[dict[str, Any]], *, size: int, seed: int) -> list[dict[str, Any]]:
    if size > len(cases):
        raise ValueError("Sample size exceeds available API evidence cases.")
    rng = random.Random(seed)
    positions = sorted(rng.sample(range(len(cases)), size))
    return [dict(cases[position]) for position in positions]


def load_decisions(path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Decisions JSON must contain an object keyed by Ticket ID.")
    return {
        str(key): dict(value)
        for key, value in payload.items()
        if isinstance(value, dict)
    }


def apply_decisions(
    cases: list[dict[str, Any]],
    decisions: dict[str, dict[str, str]],
    *,
    require_all: bool,
) -> list[dict[str, Any]]:
    allowed = set(CLASSIFICATION_LABELS) - {"unreviewed"}
    output: list[dict[str, Any]] = []
    for case in cases:
        current = dict(case)
        decision = decisions.get(str(case["ticket_id"]))
        if decision is None:
            if require_all:
                raise ValueError(f"Missing manual decision for {case['ticket_id']}")
            output.append(current)
            continue
        classification = str(decision.get("classification") or "")
        reason = str(decision.get("reason") or "").strip()
        if classification not in allowed:
            raise ValueError(
                f"Invalid classification for {case['ticket_id']}: {classification}"
            )
        if not reason:
            raise ValueError(f"Missing review reason for {case['ticket_id']}")
        current["classification"] = classification
        current["classification_zh"] = CLASSIFICATION_LABELS[classification]
        current["review_reason"] = reason
        output.append(current)
    return output


def summarize(cases: list[dict[str, Any]], *, pool_size: int, seed: int) -> dict[str, Any]:
    counts = Counter(str(case["classification"]) for case in cases)
    repositories = Counter(str(case.get("repo") or "unknown") for case in cases)
    return {
        "evidence_pool_size": pool_size,
        "sample_size": len(cases),
        "seed": seed,
        "repository_counts": dict(sorted(repositories.items())),
        "classification_counts": {
            key: counts.get(key, 0) for key in CLASSIFICATION_LABELS
        },
        "classification_rates": {
            key: round(counts.get(key, 0) / len(cases), 4) if cases else 0.0
            for key in CLASSIFICATION_LABELS
        },
        "implementation_gold_overlap_cases": sum(
            bool(case["matching_implementation_gold_files"]) for case in cases
        ),
        "source_gold_only_cases": sum(
            bool(case["matching_source_gold_files"])
            and not bool(case["matching_implementation_gold_files"])
            for case in cases
        ),
        "evidence_rows": sum(int(case["evidence_count"]) for case in cases),
    }


def classification_rules() -> dict[str, str]:
    return {
        "correct_mapping": "API證據的底層實作檔案屬於本Ticket的Gold修改檔案。",
        "relationship_correct_not_modified": (
            "API到實作的程式關係成立且與Ticket提到的功能相關，但該實作檔案不是本次Gold修改位置。"
        ),
        "irrelevant_mapping": (
            "抽取名稱或API關係與Ticket主要錯誤無關，屬於會干擾候選排名的證據。"
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    counts = summary["classification_counts"]
    rates = summary["classification_rates"]
    lines = [
        "# E3-C Development 30筆API證據人工分類",
        "",
        "## 本次目的",
        "",
        "從Development輸出中固定抽取30筆具有API重新匯出或wrapper證據的Ticket，逐筆確認證據是否真的指向本次錯誤的實作位置。這是錯誤分析，不是正式準確率實驗。",
        "",
        "Gold檔案只在候選排序完成後用於人工分類，沒有輸入模型或參與排名。",
        "",
        "## 分類規則",
        "",
        "- **正確對應**：底層實作檔案屬於Gold修改檔案。",
        "- **關係正確但非本次修改位置**：API關係成立且與功能相關，但底層檔案不是本次修改點。",
        "- **無關對應**：名稱或API關係不是Ticket主要問題的有效線索。",
        "",
        "## 分類結果",
        "",
        f"- 證據池：{summary['evidence_pool_size']}筆",
        f"- 固定抽樣：{summary['sample_size']}筆（seed={summary['seed']}）",
        "- Repository分布：" + "、".join(
            f"{repo} {count}筆" for repo, count in summary["repository_counts"].items()
        ),
        f"- 正確對應：{counts['correct_mapping']}筆（{rates['correct_mapping']:.1%}）",
        (
            "- 關係正確但非本次修改位置："
            f"{counts['relationship_correct_not_modified']}筆"
            f"（{rates['relationship_correct_not_modified']:.1%}）"
        ),
        f"- 無關對應：{counts['irrelevant_mapping']}筆（{rates['irrelevant_mapping']:.1%}）",
        f"- 待人工確認：{counts['unreviewed']}筆",
        "",
        "## 30筆逐案結果",
        "",
        "| # | Ticket | Repository | 分類 | API→實作 | Gold檔案 | 判定理由 |",
        "|---:|---|---|---|---|---|---|",
    ]
    for position, case in enumerate(payload["cases"], start=1):
        mappings = "<br>".join(
            f"{row.get('ticket_symbol')}→{row.get('implementation_symbol')} ({row.get('file_path')})"
            for row in case["evidence_details"][:4]
        ) or "—"
        gold_files = "<br>".join(case["gold_files"]) or "—"
        reason = str(case.get("review_reason") or "—").replace("|", "／")
        lines.append(
            f"| {position} | `{case['ticket_id']}` | {case['repo']} | "
            f"{case['classification_zh']} | {mappings} | {gold_files} | {reason} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, cases: list[dict[str, Any]]) -> None:
    fields = [
        "ticket_id",
        "repo",
        "title",
        "classification",
        "classification_zh",
        "review_reason",
        "gold_files",
        "implementation_files",
        "source_api_files",
        "evidence_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    field: " | ".join(case[field])
                    if isinstance(case.get(field), list)
                    else case.get(field, "")
                    for field in fields
                }
            )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def ticket_id(row: dict[str, Any]) -> str:
    return str(row.get("ticket_id") or row.get("instance_id") or row.get("id") or "")


def unique_paths(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        path = str(value or "").strip()
        key = normalize_path(path)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(path)
    return output


def normalize_path(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


if __name__ == "__main__":
    main()
