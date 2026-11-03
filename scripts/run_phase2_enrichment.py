"""Controlled offline Phase 2 runner; external workers are opt-in, never API calls."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

try:
    from .phase2_enrichment import PROJECT, OVERLAY_DIR, load_overlays, write_json
    from .phase2_quality_gates import validate_dataset
    from .sync_enriched_to_shards import sync
except ImportError:
    from phase2_enrichment import PROJECT, OVERLAY_DIR, load_overlays, write_json
    from phase2_quality_gates import validate_dataset
    from sync_enriched_to_shards import sync


def prepare_batch(batch_size, data, overlay_dir, request_dir):
    if batch_size < 1:
        raise ValueError('--batch-size must be positive')
    overlays, _ = load_overlays(overlay_dir)
    index = json.loads((data / 'index_lite.json').read_text(encoding='utf-8'))
    # Stable source ordering, not a fabricated frequency ranking.
    chosen = [e for e in index if e['tier'] == 1 and e['exact_key'] not in overlays][:batch_size]
    chosen_keys = {e['exact_key'] for e in chosen}
    manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
    evidence = []
    for shard in manifest['shards']:
        if any(i['bucket'] == shard['bucket'] for i in chosen):
            evidence.extend(e for e in json.loads((data / shard['file']).read_text(encoding='utf-8')) if e['id'] in chosen_keys)
    request = {'selection_policy': 'unenriched Tier 1 in deterministic DMS order; no frequency claim',
               'batch_size': len(chosen), 'exact_keys': [e['exact_key'] for e in chosen],
               'source_evidence': evidence}
    request_path = request_dir / 'next_batch_request.json'
    write_json(request_path, request, pretty=True)
    return request_path, request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--sync', action='store_true')
    parser.add_argument('--batch-size', type=int, help='Prepare next Tier 1 request (no worker unless --dispatch)')
    parser.add_argument('--dispatch', action='store_true', help='Explicitly run one installed Codex CLI worker via UTF-8 stdin')
    parser.add_argument('--data', type=Path, default=PROJECT / 'app/static/data')
    parser.add_argument('--overlays', type=Path, default=OVERLAY_DIR)
    parser.add_argument('--request-dir', type=Path, default=PROJECT / '.tmp/phase2')
    args = parser.parse_args()
    if args.batch_size is not None and args.batch_size < 1:
        parser.error('--batch-size must be positive')
    if args.validate_only and (args.sync or args.dispatch or args.batch_size is not None):
        parser.error('--validate-only cannot mutate shards or dispatch a worker')
    if args.dispatch or args.batch_size is not None:
        request_path, request = prepare_batch(args.batch_size or 100, args.data, args.overlays, args.request_dir)
        if not request['batch_size']:
            print('No unenriched Tier 1 entries remain.')
            return 0
        prompt = (f'Read AGENTS.md, START.md, RULES.md, and {request_path}. '
                  f'Author exactly these {request["batch_size"]} source-attested entries as a new '
                  f'JSON batch in {args.overlays}; follow phase2_tier1_batch1.json schema. '
                  'Do not change existing batches, raw source files or protected evidence. '
                  'Translate every attested sense with exact POS/English selectors; preserve homographs. '
                  'Use authored pedagogical provenance. Do not launch further workers. '
                  'Do not sync, commit, start services or claim native linguistic acceptance.')
        if args.dispatch:
            executable = shutil.which('codex')
            if not executable:
                raise FileNotFoundError('Codex CLI is not installed on PATH; request material was saved without dispatch')
            subprocess.run([executable, '-a', 'never', 'exec', '-s', 'workspace-write',
                            '-m', 'gpt-6.1-sol', '-c', 'model_reasoning_effort="high"', '-'],
                           input=prompt, encoding='utf-8', cwd=PROJECT, check=True)
        print(json.dumps({'request': str(request_path), 'batch_size': request['batch_size'],
                          'dispatched': args.dispatch}, ensure_ascii=False))
        if not args.sync:
            return 0
    if args.sync:
        sync(args.data, PROJECT / 'data/seed/lemma_pool_summary.json', args.overlays)
    report = validate_dataset(args.data, args.overlays)
    write_json(PROJECT / 'data/audit/phase2_quality_gate_report.json', report, pretty=True)
    print(json.dumps({'passed': report['passed'], 'counts': report['counts']}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
