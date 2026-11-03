"""Host-only 80-word interleaved A/B: 4 words/420s versus 8 words/840s.

All 15 first-pass batches share a 15-worker executor. One 2-word/360s retry
pass follows. Raw per-batch measurements are retained so aggregates are auditable.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from statistics import mean, median
import time

try:
    from .run_phase2_sliding_queue import (AUDIT, OVERLAY_DIR, QUARANTINE, RETRY_TIMEOUT,
        candidate_queue, chunks, load_overlays, persist_entries, process_micro_batch,
        publish_and_validate, read_json, source_store, write_json)
except ImportError:
    from run_phase2_sliding_queue import (AUDIT, OVERLAY_DIR, QUARANTINE, RETRY_TIMEOUT,
        candidate_queue, chunks, load_overlays, persist_entries, process_micro_batch,
        publish_and_validate, read_json, source_store, write_json)

OUTPUT = OVERLAY_DIR / 'phase2_tier1_batch2_ab.json'
REPORT = AUDIT / 'phase2_ab_benchmark_report.json'
ARM_A = 'arm_a_4w_420s'
ARM_B = 'arm_b_8w_840s'


def average(values):
    return mean(values) if values else 0.0


def quality_metrics(entries):
    entries = list(entries)
    translations = [s for e in entries for s in [e['teaching_sense']] + e['sense_translations']]
    collocations = [c for e in entries for c in e['collocations']]
    dialogues = [e['dual_scenarios']['colloquial']['messages'] for e in entries]
    return {
        'measured_words': len(entries),
        'avg_json_chars_per_word': average([len(json.dumps(e, ensure_ascii=False, separators=(',', ':'))) for e in entries]),
        'avg_zh_def_chars': average([len(s['zh_definition']) for s in translations]),
        # Missing optional Maltese source-sense translations count as zero.
        'avg_mt_def_chars': average([len(s.get('mt_definition') or '') for s in translations]),
        'avg_collocation_chars': average([sum(len(c[k]) for k in ('mt', 'en', 'zh')) for c in collocations]),
        'avg_dialogue_turns': average([len(turns) for turns in dialogues]),
        'avg_dialogue_chars': average([sum(len(t[k]) for t in turns for k in ('mt_spoken', 'en', 'zh')) for turns in dialogues]),
        'avg_mnemonic_chars': average([len(e['cognitive_memory_aid']) for e in entries]),
    }


def distribution(packets):
    return {name: dict(sorted(Counter(str(p[field]) if field != 'sense_selectors' else str(len(p[field]))
                                     for p in packets).items()))
            for name, field in [('pos', 'teaching_pos_default'), ('sense_count', 'sense_selectors'), ('stratum', 'stratum')]}


def summarize_arm(packets, first_results, retry_results, final_entries):
    keys = {p['exact_key'] for p in packets}
    first = {k: e for r in first_results for k, e in r['validated_entries'].items() if k in keys}
    final = {k: final_entries[k] for k in keys if k in final_entries}
    durations = [r['elapsed_sec'] for r in first_results]
    attempts = first_results + retry_results
    wall = max(r['finished_monotonic'] for r in attempts) - min(r['started_monotonic'] for r in attempts)
    worker_sec = sum(r['elapsed_sec'] for r in attempts)
    input_chars = sum(r['input_chars'] for r in first_results)
    return {
        'selected': len(keys), 'completed': len(final), 'first_pass_validated': len(first),
        'first_pass_rate': len(first) / len(keys), 'first_pass_pct': 100 * len(first) / len(keys),
        'mean_sec': average(durations), 'median_sec': median(durations),
        'min_sec': min(durations), 'max_sec': max(durations),
        'total_wall_clock_sec': wall,
        'first_pass_wall_clock_sec': max(r['finished_monotonic'] for r in first_results) - min(r['started_monotonic'] for r in first_results),
        'worker_seconds_including_retries': worker_sec,
        'words_per_minute_wall_clock': len(final) * 60 / wall if wall > 0 else 0,
        'words_per_worker_minute': len(final) * 60 / worker_sec if worker_sec > 0 else 0,
        'input_chars_per_word': input_chars / len(keys),
        'input_tokens_per_word_estimate': sum(math.ceil(r['input_chars'] / 4) for r in first_results) / len(keys),
        'first_pass_quality': quality_metrics(first.values()),
        **quality_metrics(final.values()),
        'distribution': distribution(packets),
    }


def position_analysis(results):
    groups = {'positions_1_to_4': {'selected': 0, 'entries': []},
              'positions_5_to_8': {'selected': 0, 'entries': []}}
    for result in results:
        for key, position in result['positions'].items():
            group = groups['positions_1_to_4' if position <= 4 else 'positions_5_to_8']
            group['selected'] += 1
            if key in result['validated_entries']:
                group['entries'].append(result['validated_entries'][key])
    return {name: {'selected': group['selected'], 'first_pass_validated': len(group['entries']),
                   'first_pass_rate': len(group['entries']) / group['selected'] if group['selected'] else 0,
                   **quality_metrics(group['entries'])} for name, group in groups.items()}


def run_benchmark():
    store = source_store()
    overlays, _ = load_overlays()
    quarantine = read_json(QUARANTINE) if QUARANTINE.exists() else {}
    candidates = candidate_queue(store.index, overlays, quarantine, wave='1')[:80]
    if len(candidates) != 80:
        raise ValueError(f'Benchmark needs 80 unenriched Wave-1 words; found {len(candidates)}')
    packets = [store.packet(i['exact_key']) for i in candidates]
    arms = {ARM_A: packets[::2], ARM_B: packets[1::2]}
    order = [p['exact_key'] for p in packets]
    # Reruns append to this overlay file, preserving every previously published word.
    previous = read_json(OUTPUT) if OUTPUT.exists() else []
    persisted = {item['exact_key']: item for item in previous}
    persist_order = [item['exact_key'] for item in previous] + order
    completed, first_results, retry_results = {}, {ARM_A: [], ARM_B: []}, {ARM_A: [], ARM_B: []}
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {}
        for arm, size, timeout in [(ARM_A, 4, 420), (ARM_B, 8, 840)]:
            for n, batch in enumerate(chunks(arms[arm], size), 1):
                futures[executor.submit(process_micro_batch, f'ab_{arm}_{n:02d}', batch, timeout)] = arm
        for future in as_completed(futures):
            arm = futures[future]
            result = future.result()
            first_results[arm].append(result)
            completed.update(result['validated_entries'])
            persisted.update(result['validated_entries'])
            persist_entries(OUTPUT, persisted, persist_order)
            print(f"{result['batch_tag']}: {len(result['validated_entries'])}/{len(result['words'])} first pass in {result['elapsed_sec']:.1f}s"
                  + (f" | errors={result['errors']}" if result['errors'] else ""), flush=True)
        first_pass_finished = time.monotonic()
        retries = {}
        for arm, group in arms.items():
            misses = [p for p in group if p['exact_key'] not in completed]
            for n, batch in enumerate(chunks(misses, 2), 1):
                retries[executor.submit(process_micro_batch, f'ab_{arm}_retry_{n:02d}', batch, RETRY_TIMEOUT)] = arm
        for future in as_completed(retries):
            arm = retries[future]
            result = future.result()
            retry_results[arm].append(result)
            completed.update(result['validated_entries'])
            persisted.update(result['validated_entries'])
            persist_entries(OUTPUT, persisted, persist_order)
    finished = time.monotonic()
    first_results = {arm: sorted(rows, key=lambda r: r['batch_tag']) for arm, rows in first_results.items()}
    retry_results = {arm: sorted(rows, key=lambda r: r['batch_tag']) for arm, rows in retry_results.items()}
    report = {arm: summarize_arm(arms[arm], first_results[arm], retry_results[arm], completed) for arm in arms}
    a_chars, b_chars = report[ARM_A]['input_chars_per_word'], report[ARM_B]['input_chars_per_word']
    report[ARM_B]['input_chars_savings_pct_vs_arm_a'] = 100 * (1 - b_chars / a_chars) if a_chars else 0
    a_tokens = report[ARM_A]['input_tokens_per_word_estimate']
    report[ARM_B]['input_tokens_estimate_savings_pct_vs_arm_a'] = 100 * (1 - report[ARM_B]['input_tokens_per_word_estimate'] / a_tokens) if a_tokens else 0
    report.update(
        schema_version=1, model='gpt-6.1-sol', effort='high',
        selected_exact_keys=order, completed=len(completed), missing=[k for k in order if k not in completed],
        first_pass_wall_clock_sec=first_pass_finished - started, total_wall_clock_sec=finished - started,
        arm_b_intra_batch_position_analysis=position_analysis(first_results[ARM_B]),
        distributions_identical=report[ARM_A]['distribution'] == report[ARM_B]['distribution'],
        measurement_notes=[
            'Even/odd interleaving preserves the mandated queue selection; identical category distributions are measured, not assumed.',
            'Batch duration statistics are first-pass only; effective arm throughput includes its retry wall time and worker seconds.',
            'Intra-batch position quality uses only first-pass valid words, with failures in the pass-rate denominator; retries cannot hide dilution.',
            'Character counts use Unicode code points and compact JSON; definition lengths average teaching definitions plus attested sense translations, absent optional mt_definition counts as zero.',
            'Collocation length sums mt/en/zh per collocation; dialogue length sums mt_spoken/en/zh per word (no duplicate standard restoration).',
            'Input size measures the explicit stdin prompt only, excluding CLI/system instructions. Token estimates use ceil(input_chars/4); no model tokenizer or billing token count is claimed.',
            'Five gates are deterministic structure/evidence checks; independent native-language, browser and listening review remain separate.',
        ],
        batches={arm: {'first_pass': first_results[arm], 'retry': retry_results[arm]} for arm in arms},
    )
    # Keep evidence even if publication or full-dataset validation fails.
    report['dataset_passed'] = False
    write_json(REPORT, report, pretty=True)
    try:
        summary = publish_and_validate()
        report.update(dataset_passed=True, enriched_count=summary['enriched_count'])
    except Exception as error:
        report['publication_error'] = str(error)
        raise
    finally:
        write_json(REPORT, report, pretty=True)
    return report


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    report = run_benchmark()
    print(json.dumps({'completed': report['completed'], 'missing': report['missing'],
                      'dataset_passed': report['dataset_passed'], 'report': str(REPORT)}, ensure_ascii=False))
    return 0 if report['completed'] == 80 and report['dataset_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
