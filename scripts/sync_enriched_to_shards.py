"""Fast deterministic overlay sync without reparsing the raw dictionaries."""
import argparse
import hashlib
import json
from pathlib import Path

try:
    from .phase2_enrichment import (PROJECT, OVERLAY_DIR, load_overlays, apply_overlays,
                                    enrichment_summary, write_json)
except ImportError:
    from phase2_enrichment import (PROJECT, OVERLAY_DIR, load_overlays, apply_overlays,
                                  enrichment_summary, write_json)


def sync(data=PROJECT / 'app/static/data', summary_path=PROJECT / 'data/seed/lemma_pool_summary.json',
         overlay_dir=OVERLAY_DIR):
    data, summary_path = Path(data), Path(summary_path)
    if data.resolve().is_relative_to((PROJECT / 'data/raw').resolve()) or summary_path.resolve().is_relative_to((PROJECT / 'data/raw').resolve()):
        raise ValueError('Cannot write into raw source directory')
    read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
    manifest, lite, summary = read(data / 'manifest.json'), read(data / 'index_lite.json'), read(summary_path)
    if summary['version'] != manifest['version']:
        raise ValueError('Summary/manifest mismatch; run full build first')
    for meta in manifest['shards'] + [manifest['index_lite'], manifest['wordforms_lookup']]:
        payload = (data / meta['file']).read_bytes()
        if len(payload) != meta['bytes'] or hashlib.sha256(payload).hexdigest() != meta['sha256']:
            raise ValueError(f'Input integrity failure: {meta["file"]}; run full build')
    baseline_path = data / 'phase2_baseline.json'
    if not baseline_path.exists():
        raise ValueError('Phase 2 baseline missing; run build_phase1_shards.py once')
    shards = [(meta, read(data / meta['file'])) for meta in manifest['shards']]
    entries = [e for _, shard in shards for e in shard]
    overlays, digests = load_overlays(overlay_dir)
    baseline = apply_overlays(entries, lite, overlays, read(baseline_path))
    enrichment_summary(summary, lite, digests)
    lookup = read(data / 'wordforms_lookup.json')
    lookup['version'] = summary['version']
    # All validation above happens before writing any published file.
    write_json(baseline_path, baseline)
    for meta, shard in shards:
        meta.update(write_json(data / meta['file'], shard))
    manifest['index_lite'].update(write_json(data / 'index_lite.json', lite))
    manifest['wordforms_lookup'].update(write_json(data / 'wordforms_lookup.json', lookup))
    manifest.update({k: v for k, v in summary.items() if k != 'samples'})
    write_json(summary_path, summary, pretty=True)
    write_json(data / 'manifest.json', manifest, pretty=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=PROJECT / 'app/static/data')
    parser.add_argument('--summary', type=Path, default=PROJECT / 'data/seed/lemma_pool_summary.json')
    parser.add_argument('--overlays', type=Path, default=OVERLAY_DIR)
    args = parser.parse_args()
    summary = sync(args.data, args.summary, args.overlays)
    print(json.dumps({k: summary[k] for k in ('version', 'enriched_count', 'unenriched_count', 'showcase_count')}))


if __name__ == '__main__':
    main()
