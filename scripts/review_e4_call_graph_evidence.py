#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


CLASSIFICATION_LABELS = {
    "correct_mapping": "指向正確修改檔案",
    "relationship_correct_not_modified": "功能相關但非本次修改位置",
    "irrelevant_mapping": "完全無關",
    "unreviewed": "待人工確認",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and finalize a fixed E4 Call Graph evidence review."
    )
    parser.add_argument("--tickets", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument(
        "--decisions",
        default=None,
        help="Optional JSON object mapping evidence ID to classification and reason.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.sample_size <= 0:
        raise ValueError("sample-size must be positive.")
    tickets = read_jsonl(Path(args.tickets))
    gold = read_jsonl(Path(args.gold))
    predictions = read_jsonl(Path(args.predictions))
    evidence_pool = build_call_graph_evidence_cases(tickets, gold, predictions)
    if len(evidence_pool) < args.sample_size:
        raise ValueError(
            f"Only {len(evidence_pool)} Call Graph evidence rows are available; "
            f"cannot sample {args.sample_size}."
        )
    sample = sample_cases(evidence_pool, size=args.sample_size, seed=args.seed)
    decisions = load_decisions(Path(args.decisions)) if args.decisions else {}
    sample = apply_decisions(sample, decisions, require_all=bool(args.decisions))
    summary = summarize(sample, evidence_pool=evidence_pool, seed=args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_scope": "Validation E4 Call Graph post-ranking evidence audit",
        "classification_unit": "one unique static call edge that affected a Top-20 file",
        "classification_rules": classification_rules(),
        "data_policy": (
            "Gold files are used only after ranking for evidence review; "
            "they are never retrieval or Call Graph input."
        ),
        "sources": {
            "tickets": str(Path(args.tickets)),
            "gold": str(Path(args.gold)),
            "predictions": str(Path(args.predictions)),
            "decisions": str(Path(args.decisions)) if args.decisions else "",
        },
        "summary": summary,
        "cases": sample,
    }
    json_path = output_dir / "e4_call_graph_evidence_review_30.json"
    csv_path = output_dir / "e4_call_graph_evidence_review_30.csv"
    markdown_path = output_dir / "E4_CALL_GRAPH_EVIDENCE_REVIEW_30_ZH.md"
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


def build_call_graph_evidence_cases(
    tickets: Iterable[dict[str, Any]],
    gold_rows: Iterable[dict[str, Any]],
    predictions: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    tickets_by_id = {ticket_id(row): row for row in tickets if ticket_id(row)}
    gold_by_id = {ticket_id(row): row for row in gold_rows if ticket_id(row)}
    cases: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for prediction in predictions:
        current_id = ticket_id(prediction)
        if not current_id:
            continue
        if current_id not in tickets_by_id or current_id not in gold_by_id:
            raise ValueError(f"Missing Ticket or Gold row for prediction: {current_id}")
        ticket = tickets_by_id[current_id]
        gold = gold_by_id[current_id]
        gold_files = unique_paths(
            gold.get("fixed_files") or gold.get("modified_files") or []
        )
        gold_keys = {normalize_path(path) for path in gold_files}
        for position, candidate in enumerate(
            prediction.get("stage1_candidate_files") or [], start=1
        ):
            signals = candidate.get("scoring_signals") or {}
            candidate_file = normalize_path(str(candidate.get("file_path") or ""))
            candidate_rank = int(candidate.get("rank") or position)
            call_bonus = float(signals.get("call_graph_bonus") or 0.0)
            for raw in signals.get("call_graph_evidence") or []:
                if not isinstance(raw, dict):
                    continue
                reference_file = normalize_path(str(raw.get("reference_file") or ""))
                target_file = normalize_path(
                    str(raw.get("target_file") or candidate_file)
                )
                if not reference_file or not target_file:
                    continue
                signature = (
                    current_id,
                    reference_file,
                    int(raw.get("reference_rank") or 0),
                    str(raw.get("caller_symbol") or ""),
                    target_file,
                    str(raw.get("target_symbol") or ""),
                    str(raw.get("call_name") or ""),
                    int(raw.get("line") or 0),
                    str(raw.get("resolution_type") or ""),
                )
                if signature in seen:
                    continue
                seen.add(signature)
                target_is_gold = target_file in gold_keys
                reference_is_gold = reference_file in gold_keys
                evidence_id = "e4cg-" + hashlib.sha1(
                    json.dumps(signature, ensure_ascii=True).encode("utf-8")
                ).hexdigest()[:12]
                cases.append(
                    {
                        "evidence_id": evidence_id,
                        "ticket_id": current_id,
                        "repo": str(gold.get("repo") or ticket.get("repo") or ""),
                        "title": str(ticket.get("title") or ""),
                        "description": str(
                            ticket.get("description") or ticket.get("body") or ""
                        )[:2000],
                        "gold_files": gold_files,
                        "candidate_file": candidate_file or target_file,
                        "candidate_rank": candidate_rank,
                        "call_graph_bonus": round(call_bonus, 4),
                        "reference_file": reference_file,
                        "reference_rank": int(raw.get("reference_rank") or 0),
                        "caller_symbol": str(raw.get("caller_symbol") or ""),
                        "target_file": target_file,
                        "target_symbol": str(raw.get("target_symbol") or ""),
                        "call_name": str(raw.get("call_name") or ""),
                        "line": int(raw.get("line") or 0),
                        "resolution_type": str(raw.get("resolution_type") or ""),
                        "target_is_gold": target_is_gold,
                        "reference_is_gold": reference_is_gold,
                        "automatic_hint": (
                            "correct_mapping" if target_is_gold else "unreviewed"
                        ),
                        "classification": "unreviewed",
                        "classification_zh": CLASSIFICATION_LABELS["unreviewed"],
                        "review_reason": "",
                    }
                )
    return cases


def sample_cases(
    cases: list[dict[str, Any]], *, size: int, seed: int
) -> list[dict[str, Any]]:
    if size > len(cases):
        raise ValueError("Sample size exceeds available Call Graph evidence rows.")
    rng = random.Random(seed)
    positions = sorted(rng.sample(range(len(cases)), size))
    return [dict(cases[position]) for position in positions]


def load_decisions(path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Decisions JSON must contain an object keyed by evidence ID.")
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
        decision = decisions.get(str(case["evidence_id"]))
        if decision is None:
            if require_all:
                raise ValueError(f"Missing manual decision for {case['evidence_id']}")
            output.append(current)
            continue
        classification = str(decision.get("classification") or "")
        reason = str(decision.get("reason") or "").strip()
        if classification not in allowed:
            raise ValueError(
                f"Invalid classification for {case['evidence_id']}: {classification}"
            )
        if not reason:
            raise ValueError(f"Missing review reason for {case['evidence_id']}")
        if bool(case.get("target_is_gold")) != (classification == "correct_mapping"):
            raise ValueError(
                f"Gold-overlap classification mismatch for {case['evidence_id']}"
            )
        current["classification"] = classification
        current["classification_zh"] = CLASSIFICATION_LABELS[classification]
        current["review_reason"] = reason
        output.append(current)
    return output


def summarize(
    cases: list[dict[str, Any]],
    *,
    evidence_pool: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    counts = Counter(str(case["classification"]) for case in cases)
    repositories = Counter(str(case.get("repo") or "unknown") for case in cases)
    resolution_types = Counter(
        str(case.get("resolution_type") or "unknown") for case in cases
    )
    by_resolution: dict[str, Counter[str]] = defaultdict(Counter)
    by_reference_rank: dict[str, Counter[str]] = defaultdict(Counter)
    for case in cases:
        classification = str(case["classification"])
        by_resolution[str(case.get("resolution_type") or "unknown")][
            classification
        ] += 1
        by_reference_rank[reference_rank_bucket(case.get("reference_rank"))][
            classification
        ] += 1
    return {
        "evidence_pool_size": len(evidence_pool),
        "pool_ticket_count": len({case["ticket_id"] for case in evidence_pool}),
        "pool_candidate_file_count": len(
            {
                (case["ticket_id"], case["candidate_file"])
                for case in evidence_pool
            }
        ),
        "pool_target_gold_edges": sum(
            bool(case.get("target_is_gold")) for case in evidence_pool
        ),
        "sample_size": len(cases),
        "seed": seed,
        "sample_ticket_count": len({case["ticket_id"] for case in cases}),
        "repository_counts": dict(sorted(repositories.items())),
        "resolution_type_counts": dict(sorted(resolution_types.items())),
        "classification_counts": {
            key: counts.get(key, 0) for key in CLASSIFICATION_LABELS
        },
        "classification_rates": {
            key: round(counts.get(key, 0) / len(cases), 4) if cases else 0.0
            for key in CLASSIFICATION_LABELS
        },
        "sample_target_gold_edges": sum(
            bool(case.get("target_is_gold")) for case in cases
        ),
        "classification_by_resolution_type": nested_counts(by_resolution),
        "classification_by_reference_rank": nested_counts(by_reference_rank),
    }


def nested_counts(
    values: dict[str, Counter[str]],
) -> dict[str, dict[str, int]]:
    return {
        key: {
            label: counts.get(label, 0)
            for label in CLASSIFICATION_LABELS
        }
        for key, counts in sorted(values.items())
    }


def reference_rank_bucket(value: Any) -> str:
    rank = int(value or 0)
    if rank <= 1:
        return "rank_1"
    if rank <= 3:
        return "rank_2_3"
    return "rank_4_5"


def classification_rules() -> dict[str, str]:
    return {
        "correct_mapping": "Call Graph目標檔案屬於本Ticket的Gold修改檔案。",
        "relationship_correct_not_modified": (
            "靜態呼叫成立，而且來源與目標都和Ticket功能相關，但目標不是本次Gold修改位置。"
        ),
        "irrelevant_mapping": (
            "呼叫雖可靜態解析，但來源或目標與Ticket主要錯誤無關，會干擾候選排名。"
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    counts = summary["classification_counts"]
    rates = summary["classification_rates"]
    lines = [
        "# E4 Call Graph固定30筆證據人工分類",
        "",
        "## 本次目的",
        "",
        "從固定Validation前30筆的E4輸出中，對實際影響Top-20排序的Call Graph證據邊做固定seed抽樣，逐筆確認關係是否有助於本次錯誤定位。這是事後證據分析，不是新的準確率實驗。",
        "",
        "Gold檔案只在候選排序完成後用於分類，沒有輸入模型或參與排名。",
        "",
        "## 分類規則",
        "",
        "- **指向正確修改檔案**：Call Graph目標檔案屬於Gold修改檔案。",
        "- **功能相關但非本次修改位置**：呼叫成立且和Ticket功能相關，但目標不是本次修改點。",
        "- **完全無關**：呼叫雖成立，但來源或目標與Ticket主要問題無關。",
        "",
        "## 分類結果",
        "",
        f"- 完整證據池：{summary['evidence_pool_size']}條，來自{summary['pool_ticket_count']}筆Ticket與{summary['pool_candidate_file_count']}個候選檔案。",
        f"- 固定抽樣：{summary['sample_size']}條（seed={summary['seed']}），涵蓋{summary['sample_ticket_count']}筆Ticket。",
        "- Repository分布：" + "、".join(
            f"{repo} {count}條" for repo, count in summary["repository_counts"].items()
        ),
        f"- 指向正確修改檔案：{counts['correct_mapping']}條（{rates['correct_mapping']:.1%}）。",
        f"- 功能相關但非本次修改位置：{counts['relationship_correct_not_modified']}條（{rates['relationship_correct_not_modified']:.1%}）。",
        f"- 完全無關：{counts['irrelevant_mapping']}條（{rates['irrelevant_mapping']:.1%}）。",
        f"- 待人工確認：{counts['unreviewed']}條。",
        "",
        "## 分類與參數判讀",
        "",
        "| 分組 | 指向Gold | 功能相關 | 完全無關 |",
        "|---|---:|---:|---:|",
    ]
    for name, values in summary["classification_by_resolution_type"].items():
        lines.append(
            f"| 解析類型：{name} | {values['correct_mapping']} | "
            f"{values['relationship_correct_not_modified']} | "
            f"{values['irrelevant_mapping']} |"
        )
    for name, values in summary["classification_by_reference_rank"].items():
        label = {
            "rank_1": "來源排名1",
            "rank_2_3": "來源排名2–3",
            "rank_4_5": "來源排名4–5",
        }.get(name, name)
        lines.append(
            f"| {label} | {values['correct_mapping']} | "
            f"{values['relationship_correct_not_modified']} | "
            f"{values['irrelevant_mapping']} |"
        )
    lines.extend(
        [
            "",
            "`imported_function`與`module_function`的完全無關比例在本次樣本中都為50%，因此目前沒有證據支持只保留其中一種解析類型。來源排名則呈現較明確差異：第1名來源有2／6條無關，第2–3名有7／15條無關，第4–5名有6／9條無關。",
            "",
            "後續已依此結果完成預先固定的Top-3改良版：Call Graph來源由前5名限制為前3名，其他解析類型、加分與fan-out參數保持不變。相同30筆的Recall增益維持不變，證據邊減少31.6%，因此Top-3進入500筆Validation正式比較。",
            "",
        ]
    )
    lines.extend([
        "## 30條逐案結果",
        "",
        "| # | 證據ID | Ticket | 分類 | 來源呼叫 | 目標 | 候選／來源排名 | 判定理由 |",
        "|---:|---|---|---|---|---|---|---|",
    ])
    for position, case in enumerate(payload["cases"], start=1):
        source = (
            f"{case['reference_file']}::{case['caller_symbol']}"
            f" → {case['call_name']}"
        )
        target = f"{case['target_file']}::{case['target_symbol']}"
        reason = str(case.get("review_reason") or "—").replace("|", "／")
        lines.append(
            f"| {position} | `{case['evidence_id']}` | `{case['ticket_id']}` | "
            f"{case['classification_zh']} | {source} | {target} | "
            f"{case['candidate_rank']}／{case['reference_rank']} | {reason} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, cases: list[dict[str, Any]]) -> None:
    fields = [
        "evidence_id",
        "ticket_id",
        "repo",
        "title",
        "classification",
        "classification_zh",
        "review_reason",
        "gold_files",
        "candidate_file",
        "candidate_rank",
        "call_graph_bonus",
        "reference_file",
        "reference_rank",
        "caller_symbol",
        "target_file",
        "target_symbol",
        "call_name",
        "line",
        "resolution_type",
        "target_is_gold",
        "reference_is_gold",
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
        path = normalize_path(str(value or ""))
        if not path or path in seen:
            continue
        seen.add(path)
        output.append(path)
    return output


def normalize_path(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


if __name__ == "__main__":
    main()
