"""Host-only Continuous Sliding Pull Queue v3; workers return JSON, one writer publishes.

No workers run on import. Wave 1 = audio across tiers 1/2, then remaining tier 1;
Wave 2 = remaining tier 2; tier3 = remaining tier 3 with attested English.
Index order is the source DMS order, not word frequency.
"""
import argparse
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import uuid

try:
    from .phase2_enrichment import (PROJECT, OVERLAY_DIR, apply_overlay, load_overlays,
                                    pos_class, required_sense_selectors, validate_overlay, write_json)
    from .phase2_quality_gates import (APOSTROPHES, HYPHENS, gate1, gate2, gate3, gate4,
                                       protected_record, validate_dataset)
    from .sync_enriched_to_shards import sync
except ImportError:
    from phase2_enrichment import (PROJECT, OVERLAY_DIR, apply_overlay, load_overlays,
                                  pos_class, required_sense_selectors, validate_overlay, write_json)
    from phase2_quality_gates import (APOSTROPHES, HYPHENS, gate1, gate2, gate3, gate4,
                                     protected_record, validate_dataset)
    from sync_enriched_to_shards import sync

DATA = PROJECT / 'app/static/data'
AUDIT = PROJECT / 'data/audit'
QUARANTINE = AUDIT / 'quarantine_words.json'
RETRY_TIMEOUT = 360
# Initial attempt plus three retries; quarantine when failed retry count > 2.
MAX_RETRIES = 3
PROVENANCE = {'definition_origin': 'authored_pedagogical',
              'source': 'phase2_enrichment', 'review_status': 'phase2_reviewed'}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class SourceStore:
    """Immutable source snapshot shared by threads; no shard writes in workers."""
    def __init__(self, data=DATA):
        data = Path(data)
        self.manifest = read_json(data / 'manifest.json')
        self.index = read_json(data / 'index_lite.json')
        self.indices = {i['exact_key']: i for i in self.index}
        self.entries = {e['id']: e for meta in self.manifest['shards']
                        for e in read_json(data / meta['file'])}
        self.lookup = read_json(data / 'wordforms_lookup.json')

    def packet(self, key):
        return assemble_packet(self.entries[key], self.indices[key])


@lru_cache(maxsize=1)
def source_store():
    return SourceStore()


def assemble_packet(entry, index=None):
    """Compact evidence only. Never derive roots or rewrite English selectors."""
    index = index or {}
    selectors = required_sense_selectors(entry)
    roots = list(dict.fromkeys(r for a in entry['lexeme_analyses'] for r in (a.get('roots') or [])))
    return {'exact_key': entry['id'], 'word': entry['headword']['word'],
            'tier': entry['headword']['tier'], 'stratum': entry['etymology']['stratum'],
            'roots': roots, 'teaching_pos_default': next((s['pos'] for s in selectors if s['pos']), 'unspecified'),
            'sense_selectors': selectors}


def candidate_queue(index, enriched=(), quarantined=(), wave='all', entries=None):
    """Deduplicate by exact key; preserve index order within each priority group."""
    if str(wave) not in ('1', '2', 'all', 'tier3'):
        raise ValueError('wave must be 1, 2, all or tier3')
    excluded = set(enriched) | set(quarantined)
    tier3 = str(wave) == 'tier3'
    eligible = [i for i in index if i['exact_key'] not in excluded
                and not i.get('is_enriched') and (i['tier'] == 3 if tier3 else i['tier'] in (1, 2))]
    if tier3:
        seen = set()
        return [i for i in eligible if has_english_evidence(i, entries)
                and i['exact_key'] not in seen and not seen.add(i['exact_key'])]
    audio = [i for i in eligible if i.get('has_audio')]
    core = [i for i in eligible if i['tier'] == 1 and not i.get('has_audio')]
    rich = [i for i in eligible if i['tier'] == 2 and not i.get('has_audio')]
    groups = rich if str(wave) == '2' else audio + core + (rich if wave == 'all' else [])
    seen, out = set(), []
    for item in groups:
        if item['exact_key'] not in seen:
            seen.add(item['exact_key'])
            out.append(item)
    return out


def has_english_evidence(index, entries=None):
    selectors = (required_sense_selectors(entries[index['exact_key']]) if entries is not None
                 else [{'en_definition': s} for s in index.get('gloss_en', [])])
    return bool(selectors) and all(isinstance(s['en_definition'], str) and s['en_definition'].strip() for s in selectors)


def queue_readiness(store, enriched=(), quarantined=(), wave='tier3'):
    pending = [i for i in store.index if i['tier'] == 3 and i['exact_key'] not in enriched and not i.get('is_enriched')]
    blocked = [i['exact_key'] for i in pending if not has_english_evidence(i, store.entries)]
    return {'wave': wave, 'selected': len(candidate_queue(store.index, enriched, quarantined, wave, store.entries)),
            'tier3_without_english': len(blocked), 'blocked_keys': blocked,
            'blocked_reason': 'No attested English selector; obtain source evidence before enrichment.'}


SCHEMA_PROMPT = """纯语言学词条合成子任务（普通语言数据生成，非软件工程任务；无需触发 engineering-workflow，无需读取 USER_COLLABORATION_PROFILE.md / START.md / RULES.md，严禁调用任何 shell 工具，直接一次输出 JSON）。
Author Maltese–Chinese–English pedagogical overlays using ONLY these packets.
Return a JSON list, one object per exact_key, in packet order; no prose, tools,
filesystem changes, browsing, subprocesses or further workers. All words receive
equal detail, including the last word. Never invent roots, patterns or historical claims.
Each object has EXACTLY: exact_key, gloss_zh, teaching_sense, sense_translations,
collocations, dual_scenarios, cognitive_memory_aid.
teaching_sense: {pos, en_definition, zh_definition, mt_definition}; use the supplied
teaching_pos_default, give a useful trilingual teaching definition.
sense_translations: copy EVERY supplied sense_selectors object, copying pos AND
en_definition VERBATIM, then add ALL THREE non-empty fields for EACH sense:
zh_definition (precise Chinese), mt_definition (a full Maltese definition), and
en_explanation (a complete Collins-style English explanatory sentence, at least
six words with sentence punctuation; never just repeat the short source gloss).
Do not replace en_definition with en_explanation. Preserve homograph and POS boundaries.
collocations: at least two DISTINCT useful {mt,en,zh} objects.
dual_scenarios: {formal:{mt,en,zh},colloquial:{mt,en,zh,messages:[...]}}.
formal is a pedagogical written example; colloquial is a natural pedagogical dialogue.
colloquial mt/en/zh contain the FULL dialogue on a SINGLE line (no newlines). messages has at least two turns,
each {speaker,mt_spoken,mt_standard,zh,en}, all non-empty strings. speaker must give
a name and social role in CHINESE, e.g. Maja (朋友), Mark (顾客), Omm (母亲).
mt_standard may equal mt_spoken if already standard. Optional grammar_note explains
standard contractions such as m'għandix, x'inhu or fused prepositions; do not label
these nonstandard. cognitive_memory_aid: helpful Chinese learner mnemonic >=8 chars,
clearly pedagogical, without unsupported etymology. Do not compress later entries.
Use NFC and ASCII apostrophes in Maltese. Fixed authored provenance is added by
the controller. Do not return source evidence or change selectors.
Ground Truth Packets:
"""


def build_prompt(packets):
    return SCHEMA_PROMPT + json.dumps(packets, ensure_ascii=False, separators=(',', ':'))


def normalize_overlay(value, field=''):
    """Normalize authored Maltese punctuation, never turn question marks into quotes.

    Repair a corrupted '?' apostrophe only between letters in a Maltese field;
    terminal question punctuation and verbatim English selectors remain untouched.
    """
    if isinstance(value, str):
        value = unicodedata.normalize('NFC', value)
        if any(unicodedata.category(c) in ('Cc', 'Cf') for c in value):
            value = ''.join(' ' if unicodedata.category(c) == 'Cc' else ''
                            if unicodedata.category(c) == 'Cf' else c for c in value)
        if field in ('exact_key', 'mt', 'mt_definition', 'mt_spoken', 'mt_standard'):
            value = value.translate(str.maketrans({**{c: "'" for c in APOSTROPHES},
                                                  **{c: '-' for c in HYPHENS}}))
            value = re.sub(r'(?<=[^\W\d_])\?(?=[^\W\d_])', "'", value)
        return value
    if isinstance(value, list):
        return [normalize_overlay(v, field) for v in value]
    if isinstance(value, dict):
        return {k: normalize_overlay(v, k) for k, v in value.items()}
    return value


def add_provenance(item):
    item['teaching_sense'].update(PROVENANCE)
    for sense in item['sense_translations']:
        sense.update(PROVENANCE)
    for c in item['collocations']:
        c.update(source_type='pedagogical_example', source='phase2_enrichment',
                 review_status='phase2_reviewed')
    contexts = item['dual_scenarios']
    contexts['review_status'] = 'phase2_reviewed'
    for name, kind in [('formal', 'pedagogical_example'), ('colloquial', 'pedagogical_dialogue')]:
        contexts[name].update(source_type=kind, source='phase2_enrichment', review_status='phase2_reviewed')
    return item


def parse_output(raw):
    raw = raw.strip().lstrip('\ufeff')
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*\n?', '', raw, count=1)
        raw = re.sub(r'\s*```$', '', raw)
    value = json.loads(raw)
    if isinstance(value, dict):
        if 'exact_key' in value:
            value = [value]
        elif isinstance(value.get('entries'), list):
            value = value['entries']
        else:
            value = [dict(v, exact_key=v.get('exact_key', k)) if isinstance(v, dict) else v
                     for k, v in value.items()]
    if not isinstance(value, list):
        raise ValueError('Worker JSON must be an object or list')
    return value


def validate_candidate(item, packet, store):
    """Run per-word structural/evidence gates on copies before partial commit."""
    key = packet['exact_key']
    original, index = store.entries[key], deepcopy(store.indices[key])
    if packet != assemble_packet(original, index):
        raise ValueError('Ground truth packet differs from source snapshot')
    validate_worker_refinements(item)
    validate_overlay(item, original)
    entry = deepcopy(original)
    apply_overlay(entry, index, item)
    errors = (gate1([entry], [item])
              + gate2([entry], {key: item}, {key: {'entry': original}})
              + gate3([entry], {key: item}, store.lookup)
              + gate4([entry], {key: item}, store.manifest, check_audio_totals=False))
    # Gate 5 per-word conservation; the full 24,045-word ledger is checked at sync.
    if (entry['id'] != key or index['exact_key'] != key
            or index['tier'] != original['headword']['tier']
            or len(entry['lexeme_analyses']) != len(original['lexeme_analyses'])
            or protected_record(entry) != protected_record(original)):
        errors.append('Per-word conservation failed')
    if errors:
        raise ValueError('; '.join(errors))
    return item


def validate_worker_refinements(item):
    """Stricter contract for NEW output; existing overlays stay fully compatible.

    This is a completeness floor, not an assertion of linguistic quality.
    """
    for row in item.get('sense_translations', []):
        en = row.get('en_explanation')
        if (not isinstance(row.get('mt_definition'), str) or not row['mt_definition'].strip()
                or not isinstance(en, str) or len(en.split()) < 6
                or not re.search(r'[.!?][\"\u201d\u2019\x27)]*$', en.strip())
                or en.strip().casefold() == row.get('en_definition', '').strip().casefold()):
            raise ValueError('New worker senses require zh_definition, mt_definition and a complete en_explanation sentence')


def _invoke_worker(command, prompt, timeout_sec):
    """Kill the entire Windows worker tree on timeout, not just its CLI parent."""
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                          cwd=PROJECT, **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {})) as proc:
        try:
            stdout, stderr = proc.communicate(prompt, timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                               capture_output=True, check=False,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            proc.kill()
            proc.communicate()
            raise
        return proc.returncode, stdout, stderr


def process_micro_batch(batch_tag, packets, timeout_sec, model='gpt-6.1-sol', effort='high'):
    start = time.monotonic()
    prompt = build_prompt(packets)
    keys = [p['exact_key'] for p in packets]
    result = {'batch_tag': batch_tag, 'words': keys, 'validated_entries': {}, 'errors': {},
              'positions': {key: n for n, key in enumerate(keys, 1)},
              'input_chars': len(prompt), 'input_chars_per_word': len(prompt) / max(len(keys), 1),
              'timeout_sec': timeout_sec}
    try:
        if not keys or len(set(keys)) != len(keys):
            raise ValueError('Batch requires unique non-empty packets')
        executable = shutil.which('codex')
        if not executable:
            raise FileNotFoundError('Codex CLI is not on PATH')
        scratch = Path(tempfile.gettempdir()) / 'open-malti-phase2-workers'
        scratch.mkdir(parents=True, exist_ok=True)
        # Normal mkdir inherits the parent ACL. Python 3.13 tempfile.mkdtemp's
        # 0700 Windows ACL excludes the restricted sandbox identity.
        folder = scratch / ('batch-' + uuid.uuid4().hex)
        folder.mkdir()
        try:
            out_file = folder / 'output.json'
            command = [executable, '-a', 'never', 'exec', '-C', str(folder), '--skip-git-repo-check', '-s', 'read-only',
                       '-m', model, '-c', f'model_reasoning_effort="{effort}"',
                       '--ephemeral', '-o', str(out_file), '-']
            code, _, _ = _invoke_worker(command, prompt, timeout_sec)
            # Salvage a complete output file even when the CLI exits nonzero.
            if not out_file.exists():
                raise ValueError(f'Worker output missing (exit {code})')
            rows = parse_output(out_file.read_text(encoding='utf-8'))
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        grouped = {}
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get('exact_key'), str):
                row = normalize_overlay(row)
                grouped.setdefault(row['exact_key'], []).append(row)
        store = source_store()
        for packet in packets:
            key = packet['exact_key']
            try:
                matches = grouped.get(key, [])
                if len(matches) != 1:
                    raise ValueError('Missing output' if not matches else 'Duplicate output exact_key')
                item = add_provenance(matches[0])
                result['validated_entries'][key] = validate_candidate(item, packet, store)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                result['errors'][key] = str(error)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        result['errors'].update({key: str(error) for key in keys if key not in result['validated_entries']})
    result['elapsed_sec'] = time.monotonic() - start
    result['finished_monotonic'] = time.monotonic()
    result['started_monotonic'] = start
    result['status'] = 'partial' if result['validated_entries'] and result['errors'] else 'error' if result['errors'] else 'ok'
    return result


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def publish_and_validate():
    summary = sync()
    report = validate_dataset()
    write_json(AUDIT / 'phase2_quality_gate_report.json', report, pretty=True)
    if not report['passed']:
        raise ValueError('Published dataset failed five gates; see phase2_quality_gate_report.json')
    return summary


def compact_and_commit_milestone():
    qfiles = sorted(OVERLAY_DIR.glob('phase2_queue_*.json'))
    if not qfiles:
        return publish_and_validate()
    merged = {}
    for qf in qfiles:
        for item in read_json(qf):
            merged[item['exact_key']] = item
    existing = sorted(OVERLAY_DIR.glob('phase2_milestone_*.json'))
    num = len(existing) + 1
    while (OVERLAY_DIR / f'phase2_milestone_{num:03d}.json').exists():
        num += 1
    target = OVERLAY_DIR / f'phase2_milestone_{num:03d}.json'
    write_json(target, [merged[k] for k in sorted(merged)], pretty=True)
    for qf in qfiles:
        qf.unlink()
    summary = publish_and_validate()
    stage_paths = ['data/enriched', 'data/audit/phase2_quality_gate_report.json', 'data/seed/lemma_pool_summary.json']
    if QUARANTINE.exists():
        stage_paths.append('data/audit/quarantine_words.json')
    subprocess.run(['git', 'add', '--'] + stage_paths, cwd=PROJECT, check=True)
    msg = f"feat(phase2): milestone {num:03d} (+{len(merged)} words, total {summary['enriched_count']}/24045, 5-gate pass)"
    subprocess.run(['git', 'commit', '-m', msg], cwd=PROJECT, check=True)
    print(f"[MILESTONE {num:03d}] Committed +{len(merged)} words -> enriched_count={summary['enriched_count']}/24045", flush=True)
    return summary


def persist_entries(path, entries, order):
    if entries:
        write_json(path, [entries[k] for k in order if k in entries], pretty=True)


def run_queue(slots=25, batch_size=4, timeout=420, max_words=0, milestone_interval=100, wave='all', commit_every=0):
    if min(slots, batch_size, timeout, milestone_interval) < 1 or max_words < 0 or commit_every < 0:
        raise ValueError('Positive slots/batch-size/timeout/milestone and nonnegative max-words/commit-every required')
    store = source_store()
    overlays, _ = load_overlays(OVERLAY_DIR)
    quarantine = read_json(QUARANTINE) if QUARANTINE.exists() else {}
    chosen = candidate_queue(store.index, overlays, quarantine, wave, store.entries)
    if max_words:
        chosen = chosen[:max_words]
    order = [i['exact_key'] for i in chosen]
    pending = deque(chosen)
    retries, attempts, committed = deque(), {}, {}
    sequence, since_milestone, since_commit = 0, 0, 0
    # Stable name/content across restarts; valid entries already on disk are excluded.
    # Each file is a list of one entry, as required by the shared overlay loader.
    def save_batch(valid):
        for key, entry in valid.items():
            filename = 'phase2_queue_' + hashlib.sha256(key.encode('utf-8')).hexdigest() + '.json'
            write_json(OVERLAY_DIR / filename, [entry], pretty=True)

    with ThreadPoolExecutor(max_workers=slots) as executor:
        futures = {}
        def refill():
            nonlocal sequence
            while len(futures) < slots and (retries or pending):
                retry = bool(retries)
                packets = retries.popleft() if retry else [store.packet(pending.popleft()['exact_key'])
                    for _ in range(min(batch_size, len(pending)))]
                sequence += 1
                tag = f'queue_{sequence:06d}' + ('_retry' if retry else '')
                future = executor.submit(process_micro_batch, tag, packets,
                                         RETRY_TIMEOUT if retry else timeout)
                futures[future] = (tag, packets)
        refill()
        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in sorted(done, key=lambda f: futures[f][0]):
                tag, packets = futures.pop(future)
                result = future.result()
                valid = result['validated_entries']
                save_batch(valid)
                committed.update(valid)
                since_milestone += len(valid)
                since_commit += len(valid)
                failed = []
                for packet in packets:
                    key = packet['exact_key']
                    if key in valid:
                        continue
                    attempts[key] = attempts.get(key, 0) + 1
                    if attempts[key] > MAX_RETRIES:
                        quarantine[key] = {'attempts': attempts[key], 'retries': attempts[key] - 1,
                                           'error': result['errors'].get(key, 'Missing output')}
                        write_json(QUARANTINE, dict(sorted(quarantine.items())), pretty=True)
                    else:
                        failed.append(packet)
                retries.extend(chunks(failed, 2))
                print(f'{tag}: {len(valid)}/{len(packets)} validated; session={len(committed)}', flush=True)
            # Refill freed slots BEFORE potentially slow milestone publication.
            refill()
            if commit_every and since_commit >= commit_every:
                compact_and_commit_milestone()
                since_commit = 0
                since_milestone = 0
            elif since_milestone >= milestone_interval:
                publish_and_validate()
                since_milestone = 0
    summary = compact_and_commit_milestone() if (commit_every and since_commit > 0) else publish_and_validate()
    return {'selected': len(order), 'validated': len(committed),
            'quarantined': len(set(order) & set(quarantine)), 'enriched_count': summary['enriched_count']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concurrency', '--slots', dest='slots', type=int, default=25)
    parser.add_argument('--batch-size', type=int, default=4)
    parser.add_argument('--timeout', type=int, default=420)
    parser.add_argument('--max-words', type=int, default=0, help='0 exhausts the selected pool; retries do not count twice')
    parser.add_argument('--milestone-interval', type=int, default=100)
    parser.add_argument('--commit-every', type=int, default=0, help='Compact queue files into milestone JSON and git commit every N words')
    parser.add_argument('--wave', choices=['1', '2', 'all', 'tier3'], default='all')
    parser.add_argument('--dry-run', action='store_true', help='Report candidates and evidence gaps without workers or writes')
    args = parser.parse_args()
    if min(args.slots, args.batch_size, args.timeout, args.milestone_interval) < 1 or args.max_words < 0 or args.commit_every < 0:
        parser.error('counts/timeouts must be positive; --max-words/--commit-every may be 0')
    dry_run = vars(args).pop('dry_run')
    if dry_run:
        overlays, _ = load_overlays(OVERLAY_DIR)
        quarantine = read_json(QUARANTINE) if QUARANTINE.exists() else {}
        result = queue_readiness(source_store(), overlays, quarantine, args.wave)
        result.update(concurrency=args.slots, batch_size=args.batch_size, max_words=args.max_words)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    result = run_queue(**vars(args))
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result['quarantined'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
