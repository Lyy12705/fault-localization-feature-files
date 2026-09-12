"""Audit and compare the saved Top-30 run against the earlier Top-10 run."""
import json
import math
import statistics
from pathlib import Path

from analyze_stage3_wp4_pilot import bootstrap_mean_ci

ROOT = Path('reports/fault_localization')
OUT = ROOT / 'stage3_wp4_top30_20260910'


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main():
    new = rows(OUT / 'pilot_46tickets.jsonl')
    old = {r['ticket_id']: r for r in rows(ROOT / 'stage3_wp4_pilot/pilot_46tickets.jsonl')}
    pool = {r['ticket_id']: r for r in rows(ROOT / 'stage3_deterministic_g2_dev_v1/b1_coverage_aware_v1_predictions.jsonl')}
    assert len(new) == len(old) == 46
    assert {r['ticket_id'] for r in new} == set(old)
    assert all(r['baseline_eval'] == old[r['ticket_id']]['baseline_eval'] for r in new)
    audit = {'same_46_tickets': True, 'baseline_evaluations_identical': True, 'candidate_counts': [],
             'missing_code_counts': [], 'max_prompt_plus_output_tokens': 0,
             'response_done_reasons': {}, 'new_vs_old_hit_at': {}}
    for row in new:
        raw = json.loads((OUT / 'raw' / (row['ticket_id'] + '.json')).read_text(encoding='utf-8'))
        candidates = json.loads(raw['request']['prompt'].split('Candidates:\n', 1)[1])
        expected = pool[row['ticket_id']]['stage3_candidate_symbols'][:30]
        assert len(candidates) == len(expected)
        assert sorted((c['file_path'], c['qualified_name'], c['symbol_kind']) for c in candidates) == sorted(
            (c['file_path'], c.get('symbol_qualified_name') or c.get('symbol_name', ''), c.get('symbol_kind', ''))
            for c in expected)
        assert all(set(c) == {'candidate_id', 'file_path', 'symbol_kind', 'qualified_name',
                              'start_line', 'end_line', 'code'} for c in candidates)
        audit['candidate_counts'].append(len(candidates))
        audit['missing_code_counts'].append(sum(not c['code'] for c in candidates))
        response = raw.get('response', {})
        audit['max_prompt_plus_output_tokens'] = max(audit['max_prompt_plus_output_tokens'],
            response.get('prompt_eval_count', 0) + response.get('eval_count', 0))
        reason = response.get('done_reason', 'error')
        audit['response_done_reasons'][reason] = audit['response_done_reasons'].get(reason, 0) + 1
    times = sorted(r['elapsed_seconds'] for r in new)
    audit['latency_seconds'] = {'mean': statistics.mean(times), 'median': statistics.median(times),
                               'p95_nearest_rank': times[math.ceil(.95 * len(times)) - 1],
                               'max': max(times), 'sum': sum(times)}
    for k in ('1', '3', '5'):
        deltas = [r['llm_eval']['exact']['hit_at'][k] - old[r['ticket_id']]['llm_eval']['exact']['hit_at'][k]
                  for r in new]
        audit['new_vs_old_hit_at'][k] = {'improved': sum(d > 0 for d in deltas),
             'worsened': sum(d < 0 for d in deltas), 'mean_delta': statistics.mean(deltas),
             'delta_95ci': bootstrap_mean_ci(deltas)}
    (OUT / 'audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
