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
    "incorrect_mapping": "錯誤對應",
    "overly_ambiguous": "名稱過度模糊",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sample and classify E3 Symbol-definition evidence on Development data."
        )
    )
    parser.add_argument("--tickets", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260822)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.sample_size <= 0:
        raise ValueError("sample-size must be positive.")

    tickets = read_jsonl(Path(args.tickets))
    gold_rows = read_jsonl(Path(args.gold))
    predictions = read_jsonl(Path(args.predictions))
    cases = build_evidence_cases(tickets, gold_rows, predictions)
    if len(cases) < args.sample_size:
        raise ValueError(
            f"Only {len(cases)} predictions contain E3 evidence; "
            f"cannot sample {args.sample_size}."
        )
    sample = sample_evidence_cases(cases, args.sample_size, args.seed)
    summary = summarize_cases(sample, pool_size=len(cases), seed=args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "e3_evidence_review_30.json"
    csv_path = output_dir / "e3_evidence_review_30.csv"
    markdown_path = output_dir / "E3_DEVELOPMENT_EVIDENCE_REVIEW_30_ZH.md"

    payload = {
        "analysis_scope": "Development E3 Symbol-definition evidence audit",
        "classification_unit": "one Ticket with at least one returned E3 evidence row",
        "classification_rules": classification_rules(),
        "data_policy": (
            "Gold files are used only for post-hoc Development analysis and never as retrieval input."
        ),
        "sources": {
            "tickets": str(Path(args.tickets)),
            "gold": str(Path(args.gold)),
            "predictions": str(Path(args.predictions)),
        },
        "summary": summary,
        "cases": sample,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_cases_csv(csv_path, sample)
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


def build_evidence_cases(
    tickets: Iterable[dict[str, Any]],
    gold_rows: Iterable[dict[str, Any]],
    predictions: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    tickets_by_id = {
        ticket_id(row): row for row in tickets if ticket_id(row)
    }
    gold_by_id = {ticket_id(row): row for row in gold_rows if ticket_id(row)}
    cases: list[dict[str, Any]] = []
    for prediction in predictions:
        current_id = ticket_id(prediction)
        if not current_id:
            continue
        if current_id not in tickets_by_id or current_id not in gold_by_id:
            raise ValueError(f"Missing Ticket or Gold row for prediction: {current_id}")
        diagnostics = prediction.get("stage1_diagnostics") or {}
        symbol_expansion = diagnostics.get("symbol_expansion") or {}
        evidence = [
            dict(row)
            for row in symbol_expansion.get("evidence") or []
            if isinstance(row, dict) and row.get("file_path")
        ]
        if not evidence:
            continue
        cases.append(
            classify_evidence_case(
                ticket=tickets_by_id[current_id],
                gold=gold_by_id[current_id],
                prediction=prediction,
                evidence=evidence,
                ticket_program_names=symbol_expansion.get("ticket_program_names") or [],
            )
        )
    return cases


def classify_evidence_case(
    *,
    ticket: dict[str, Any],
    gold: dict[str, Any],
    prediction: dict[str, Any],
    evidence: list[dict[str, Any]],
    ticket_program_names: list[str],
) -> dict[str, Any]:
    gold_files = unique_paths(gold.get("fixed_files") or gold.get("modified_files") or [])
    evidence_files = unique_paths(row["file_path"] for row in evidence)
    gold_keyed = {normalize_path(path): path for path in gold_files}
    evidence_keyed = {normalize_path(path): path for path in evidence_files}
    matching_keys = sorted(set(gold_keyed) & set(evidence_keyed))
    extra_keys = sorted(set(evidence_keyed) - set(gold_keyed))

    if matching_keys and not extra_keys:
        classification = "correct_mapping"
        basis = "所有E3對應檔案都屬於本Ticket的Gold修改檔案。"
    elif matching_keys:
        classification = "overly_ambiguous"
        basis = "E3有找到Gold修改檔案，但同時把名稱對應到其他檔案。"
    else:
        classification = "incorrect_mapping"
        basis = "E3對應檔案沒有任何一個屬於本Ticket的Gold修改檔案。"

    exact_count = sum(row.get("match_type") == "exact" for row in evidence)
    leaf_count = sum(row.get("match_type") == "leaf" for row in evidence)
    candidates = prediction.get("stage1_candidate_files") or []
    candidate_rank = {
        normalize_path(str(row.get("file_path") or "")): int(row.get("rank") or position)
        for position, row in enumerate(candidates, start=1)
        if row.get("file_path")
    }
    matched_symbols = sorted(
        {
            str(row.get("matched_symbol") or "")
            for row in evidence
            if row.get("matched_symbol")
        }
    )
    matched_ticket_symbols = sorted(
        {
            str(row.get("ticket_symbol") or "")
            for row in evidence
            if row.get("ticket_symbol")
        }
    )
    evidence_details = [
        {
            "ticket_symbol": str(row.get("ticket_symbol") or ""),
            "matched_symbol": str(row.get("matched_symbol") or ""),
            "file_path": str(row.get("file_path") or ""),
            "match_type": str(row.get("match_type") or ""),
            "candidate_rank": candidate_rank.get(normalize_path(str(row["file_path"]))),
        }
        for row in evidence
    ]
    return {
        "ticket_id": ticket_id(ticket),
        "repo": str(gold.get("repo") or ticket.get("repo") or ""),
        "title": str(ticket.get("title") or ""),
        "classification": classification,
        "classification_zh": CLASSIFICATION_LABELS[classification],
        "classification_basis": basis,
        "ticket_program_names": sorted({str(value) for value in ticket_program_names}),
        "matched_ticket_symbols": matched_ticket_symbols,
        "matched_symbols": matched_symbols,
        "gold_files": gold_files,
        "evidence_files": evidence_files,
        "matching_gold_files": [gold_keyed[key] for key in matching_keys],
        "extra_evidence_files": [evidence_keyed[key] for key in extra_keys],
        "evidence_count": len(evidence),
        "exact_match_count": exact_count,
        "leaf_match_count": leaf_count,
        "evidence_details": evidence_details,
    }


def sample_evidence_cases(
    cases: list[dict[str, Any]], size: int, seed: int
) -> list[dict[str, Any]]:
    if size > len(cases):
        raise ValueError("Sample size exceeds available evidence cases.")
    rng = random.Random(seed)
    positions = sorted(rng.sample(range(len(cases)), size))
    return [cases[position] for position in positions]


def summarize_cases(
    cases: list[dict[str, Any]], *, pool_size: int, seed: int
) -> dict[str, Any]:
    counts = Counter(case["classification"] for case in cases)
    repository_counts = Counter(case["repo"] or "unknown" for case in cases)
    size = len(cases)
    return {
        "evidence_pool_size": pool_size,
        "sample_size": size,
        "seed": seed,
        "repository_counts": dict(sorted(repository_counts.items())),
        "classification_counts": {
            key: counts.get(key, 0) for key in CLASSIFICATION_LABELS
        },
        "classification_rates": {
            key: round(counts.get(key, 0) / size, 4) if size else 0.0
            for key in CLASSIFICATION_LABELS
        },
        "exact_evidence_rows": sum(case["exact_match_count"] for case in cases),
        "leaf_evidence_rows": sum(case["leaf_match_count"] for case in cases),
        "gold_overlap_cases": sum(bool(case["matching_gold_files"]) for case in cases),
    }


def classification_rules() -> dict[str, str]:
    return {
        "correct_mapping": "E3對應檔案非空，且全部都是該Ticket的Gold修改檔案。",
        "overly_ambiguous": "E3同時對應到Gold修改檔案與其他非Gold檔案。",
        "incorrect_mapping": "E3對應檔案與Gold修改檔案完全沒有交集。",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    counts = summary["classification_counts"]
    rates = summary["classification_rates"]
    lines = [
        "# E3 Development 30筆證據案例分類",
        "",
        "## 本次目的",
        "",
        "從Development的E3-B輸出中抽取30筆具有Symbol definition證據的Ticket，檢查程式名稱是否被對應到正確修改檔案。這是錯誤分析，不是正式準確率實驗。",
        "",
        "Gold檔案只在候選排序完成後用於分類，沒有輸入模型，也沒有參與排名。",
        "",
        "## 分類規則",
        "",
        "- **正確對應**：E3對應到的檔案全部都是Gold修改檔案。",
        "- **名稱過度模糊**：E3找到Gold修改檔案，但同時對應到其他檔案。",
        "- **錯誤對應**：E3對應的檔案與Gold修改檔案完全沒有交集。",
        "",
        "這是以Gold檔案重疊為準的工程檢查。非Gold檔案仍可能與問題有關，但無法證明它是本Ticket真正需要修改的位置。",
        "",
        "## 分類結果",
        "",
        f"- 證據池：{summary['evidence_pool_size']}筆",
        f"- 固定亂數種子抽樣：{summary['sample_size']}筆（seed={summary['seed']}）",
        "- Repository分布："
        + "、".join(
            f"{repo} {count}筆"
            for repo, count in summary["repository_counts"].items()
        ),
        f"- 正確對應：{counts['correct_mapping']}筆（{rates['correct_mapping']:.1%}）",
        f"- 名稱過度模糊：{counts['overly_ambiguous']}筆（{rates['overly_ambiguous']:.1%}）",
        f"- 錯誤對應：{counts['incorrect_mapping']}筆（{rates['incorrect_mapping']:.1%}）",
        f"- Exact證據：{summary['exact_evidence_rows']}列；Leaf證據：{summary['leaf_evidence_rows']}列",
        "",
        "## 30筆逐案結果",
        "",
        "| # | Ticket | 分類 | Gold命中 | 額外對應檔案 | Exact／Leaf |",
        "|---:|---|---|---|---|---:|",
    ]
    for position, case in enumerate(payload["cases"], start=1):
        gold_hits = "<br>".join(case["matching_gold_files"]) or "—"
        extras = "<br>".join(case["extra_evidence_files"]) or "—"
        lines.append(
            f"| {position} | `{case['ticket_id']}` | {case['classification_zh']} | "
            f"{gold_hits} | {extras} | "
            f"{case['exact_match_count']}／{case['leaf_match_count']} |"
        )
    lines.extend(
        [
            "",
            "## 結果判讀",
            "",
            "若『名稱過度模糊』或『錯誤對應』比例偏高，下一版應先限制leaf-name對應，例如不要把`self.version`、`other.version`或模組路徑的最後一段，直接對應到Repository內所有同名Method。",
            "",
            "本次樣本來自目前已完成的Development證據池；其Repository涵蓋範圍應與正式500筆Validation分開報告，不能用本表取代正式方法比較。",
            "",
        ]
    )
    return "\n".join(lines)


def write_cases_csv(path: Path, cases: list[dict[str, Any]]) -> None:
    fields = [
        "ticket_id",
        "repo",
        "title",
        "classification",
        "classification_zh",
        "classification_basis",
        "ticket_program_names",
        "matched_ticket_symbols",
        "matched_symbols",
        "gold_files",
        "evidence_files",
        "matching_gold_files",
        "extra_evidence_files",
        "evidence_count",
        "exact_match_count",
        "leaf_match_count",
        "evidence_details",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    key: (
                        json.dumps(case[key], ensure_ascii=False)
                        if isinstance(case[key], (list, dict))
                        else case[key]
                    )
                    for key in fields
                }
            )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def ticket_id(row: dict[str, Any]) -> str:
    return str(row.get("ticket_id") or row.get("instance_id") or row.get("id") or "")


def normalize_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def unique_paths(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        path = normalize_path(str(value))
        if path and path not in seen:
            seen.add(path)
            result.append(path)
    return result


if __name__ == "__main__":
    main()
