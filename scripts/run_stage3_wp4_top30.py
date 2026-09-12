"""Reproducible Top-30 pilot; preserves the original pilot and its outputs."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

import run_stage3_wp4_symbol_llm_pilot as pilot
from utils.json_schema import repair_json_object

OUT = Path('reports/fault_localization/stage3_wp4_top30_20260910')
OPTIONS = {'temperature': 0.0, 'top_p': 1.0, 'num_predict': 3072, 'num_ctx': 16384}


def request(endpoint, payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request('http://localhost:11434/api/' + endpoint,
                                 data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.load(response)


class RecordedClient:
    def __init__(self, ticket_id):
        self.ticket_id = ticket_id
        self.record = {}

    def generate_json_with_schema(self, prompt, schema):
        payload = {'model': 'codellama:7b-instruct', 'prompt': prompt,
                   'stream': False, 'format': schema, 'options': OPTIONS}
        start = time.monotonic()
        self.record = {'request': payload}
        try:
            body = request('generate', payload)
            self.record['response'] = body
            return repair_json_object(body['response'])
        except Exception as exc:
            self.record['error'] = str(exc)
            raise
        finally:
            self.record['elapsed_seconds'] = time.monotonic() - start
            (OUT / 'raw' / f'{self.ticket_id}.json').write_text(
                json.dumps(self.record, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    (OUT / 'raw').mkdir(parents=True, exist_ok=True)
    output = OUT / 'pilot_46tickets.jsonl'
    if output.exists():
        raise SystemExit('Output already exists; refusing to overwrite experiment.')
    paths = [pilot.DEFAULT_CANDIDATE_POOL, pilot.DEFAULT_SOURCE_TICKETS, pilot.DEFAULT_GOLD]
    manifest = {'shortlist_k': 30, 'top_k': 5, 'shuffle_seed': 20260908,
                'options': OPTIONS, 'timeout_seconds': 600,
                'max_code_chars': pilot.MAX_CODE_CHARS,
                'max_bug_report_chars': pilot.MAX_BUG_REPORT_CHARS,
                'models': request('tags'), 'ollama_version': request('version'),
                'input_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    sources = {r['ticket_id']: r for r in pilot.load_jsonl(pilot.DEFAULT_SOURCE_TICKETS)}
    gold = pilot.load_jsonl(pilot.DEFAULT_GOLD)
    outcomes = []
    cache = {}
    with output.open('x', encoding='utf-8') as handle:
        for row in pilot.load_jsonl(pilot.DEFAULT_CANDIDATE_POOL):
            ticket_id = row['ticket_id']
            answers = pilot.gold_items_for_ticket(gold, ticket_id)
            if not pilot.is_eligible(row, answers):
                continue
            index = pilot.index_path_for(row['repo'], row['base_commit'], pilot.DEFAULT_INDEX_DIR)
            if index not in cache:
                cache[index] = pilot.load_chunk_lookup(index)
            source = sources[ticket_id]
            client = RecordedClient(ticket_id)
            outcome = pilot.run_ticket(row, source.get('bug_report') or source.get('description') or '',
                                       answers, cache[index], client, shortlist_k=30, top_k=5, seed=20260908)
            outcomes.append(outcome)
            record = outcome.to_dict()
            record['elapsed_seconds'] = client.record.get('elapsed_seconds')
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
            handle.flush()
            summary = pilot.summarize(outcomes)
            summary['known_limitation'] = ('Conditional development pilot only. Recall@30 and Hit@5 '
                                           'are distinct metrics. Not independent holdout validation.')
            summary['run_manifest'] = manifest
            (OUT / 'pilot_46tickets_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
            body = client.record.get('response', {})
            print(f'{len(outcomes)}/46 {ticket_id} valid={outcome.llm_valid} '
                  f'time={record["elapsed_seconds"]:.1f}s prompt_tokens={body.get("prompt_eval_count")} '
                  f'done={body.get("done_reason")} fallback={outcome.fallback_reason}', flush=True)


if __name__ == '__main__':
    main()
