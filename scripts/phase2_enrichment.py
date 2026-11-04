"""Strict additive overlays shared by the full compiler and incremental sync.

Sense selectors use (source POS, exact English definition), never a lemma-wide
Chinese replacement. Licensed English and analysis/source-record boundaries stay intact.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

try:
    from .sense_display import pos_class, refresh_display
except ImportError:
    from sense_display import pos_class, refresh_display

PROJECT = Path(__file__).resolve().parents[1]
OVERLAY_DIR = PROJECT / 'data/enriched'
BASE_VERSION = 'malti-phase2-2026-11-04-display1'
ALLOWED = {'exact_key', 'gloss_zh', 'teaching_sense', 'sense_translations',
           'collocations', 'dual_scenarios', 'cognitive_memory_aid'}


def selector_pos(pos):
    """Stable Phase 2 evidence key, distinct from the broader DISPLAY POS class.

    Existing name/propn (and other alias) selectors can have different authored
    translations. Changing their identity would silently rebind old evidence.
    """
    value = (pos or '').lower()
    return {'n.': 'noun', 'n.m.': 'noun', 'n.f.': 'noun', 'adj.': 'adj',
            'num.': 'num', 'v.': 'verb', 'v': 'verb', 'adp': 'prep'}.get(value, value)


def load_overlays(directory=OVERLAY_DIR):
    overlays, digests = {}, {}
    for path in sorted(Path(directory).glob('*.json'), key=lambda p: p.name):
        raw = path.read_bytes()
        digests[path.name] = hashlib.sha256(raw).hexdigest()
        batch = json.loads(raw)
        if not isinstance(batch, list):
            raise ValueError(f'{path.name}: expected a list of entries')
        for item in batch:
            if not isinstance(item, dict) or set(item) - ALLOWED:
                raise ValueError(f'{path.name}: forbidden overlay fields')
            key = item.get('exact_key')
            if not isinstance(key, str) or not key or key in overlays:
                raise ValueError(f'{path.name}: missing or duplicate exact_key: {key}')
            validate_overlay(item)
            overlays[key] = item
    return overlays, digests


def required_sense_selectors(entry):
    """Keep source order and exact English, deduplicating stable selector POS/English."""
    selectors = {}
    for sense in [s for a in entry['lexeme_analyses'] for s in a['senses']] + entry['senses']:
        if sense.get('id') == 'teaching':
            continue
        pair = (selector_pos(sense['pos']), sense['en_definition'])
        selectors.setdefault(pair, {'pos': pair[0], 'en_definition': pair[1]})
    return list(selectors.values())


def anti_dilution_errors(collocations, contexts, aid, senses=()):
    """Shared overlay/published-content floor; never synthesizes missing content."""
    errors = []
    text = lambda v: isinstance(v, str) and bool(v.strip())
    if not isinstance(senses, (list, tuple)) or any(not isinstance(s, dict) or not text(s.get('zh_definition')) for s in senses):
        errors.append('Every attested sense needs a non-empty zh_definition')
    if (not isinstance(collocations, list) or len(collocations) < 2
            or any(not isinstance(c, dict) or not all(text(c.get(k)) for k in ('mt', 'en', 'zh'))
                   for c in collocations)):
        errors.append('At least two distinct trilingual collocations required')
    elif len({' '.join(c['mt'].split()).casefold() for c in collocations}) < 2:
        errors.append('Collocations must be distinct')
    colloquial = contexts.get('colloquial') if isinstance(contexts, dict) else None
    messages = colloquial.get('messages') if isinstance(colloquial, dict) else None
    if (not isinstance(messages, list) or len(messages) < 2
            or any(not isinstance(m, dict) or not all(text(m.get(k))
                   for k in ('speaker', 'mt_spoken', 'mt_standard', 'zh', 'en')) for m in messages)):
        errors.append('Colloquial messages require at least two complete conversational turns')
    if isinstance(colloquial, dict) and 'grammar_note' in colloquial and not isinstance(colloquial['grammar_note'], str):
        errors.append('grammar_note must be a string')
    if not text(aid) or len(aid.strip()) < 8:
        errors.append('cognitive_memory_aid must contain at least 8 characters')
    return errors


def validate_overlay(item, entry=None):
    """Fail closed before applying/publishing an incomplete worker batch."""
    if not isinstance(item, dict):
        raise ValueError('Overlay must be an object')
    if set(item) != ALLOWED:
        raise ValueError(f'{item.get("exact_key")}: incomplete overlay contract')
    if not all(isinstance(item[k], str) and item[k].strip()
               for k in ('exact_key', 'gloss_zh', 'cognitive_memory_aid')):
        raise ValueError('Missing overlay text')
    errors = anti_dilution_errors(item['collocations'], item['dual_scenarios'],
                                 item['cognitive_memory_aid'], item.get('sense_translations') or [])
    if errors:
        raise ValueError('; '.join(errors))
    teaching = item['teaching_sense']
    if not isinstance(teaching, dict) or not all(isinstance(teaching.get(k), str) and teaching[k].strip()
               for k in ('pos', 'en_definition', 'zh_definition', 'mt_definition')):
        raise ValueError('Incomplete trilingual teaching sense')
    if (teaching.get('definition_origin'), teaching.get('source'), teaching.get('review_status')) != ('authored_pedagogical', 'phase2_enrichment', 'phase2_reviewed'):
        raise ValueError('Invalid teaching provenance')
    collocations = item['collocations']
    if not isinstance(collocations, list) or len(collocations) < 2:
        raise ValueError('At least two collocations required')
    contexts = item['dual_scenarios']
    if contexts.get('review_status') != 'phase2_reviewed':
        raise ValueError('Invalid scenario review status')
    for obj, source_type in [(c, 'pedagogical_example') for c in collocations] + [
            (contexts.get('formal', {}), 'pedagogical_example'),
            (contexts.get('colloquial', {}), 'pedagogical_dialogue')]:
        if not isinstance(obj, dict) or not all(isinstance(obj.get(k), str) and obj[k].strip() for k in ('mt', 'en', 'zh')):
            raise ValueError('Incomplete trilingual example')
        if obj.get('source_type') != source_type:
            raise ValueError('Invalid example provenance')
    if any(c.get('review_status') != 'phase2_reviewed' for c in collocations):
        raise ValueError('Invalid collocation review status')
    if len({c['mt'] for c in collocations}) < 2:
        raise ValueError('Collocations must be distinct')
    translations = translations_for(item)
    if entry is not None:
        expected = {(s['pos'], s['en_definition']) for s in required_sense_selectors(entry)}
        if set(translations) != expected:
            raise ValueError('sense_translations must cover every exact attested POS/English selector')
    try:
        from .phase2_quality_gates import gate1
    except ImportError:
        from phase2_quality_gates import gate1
    errors = gate1([], [item])
    if errors:
        raise ValueError(f'{item["exact_key"]}: {errors[0]}')


def dataset_version(digests):
    return BASE_VERSION + '-' + hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()[:12]


def translations_for(item):
    out = {}
    rows = item.get('sense_translations', [])
    if not isinstance(rows, list) or not rows:
        raise ValueError('sense_translations must be a list of exact POS/English selectors')
    for row in rows:
        # Some attested source records genuinely omit POS (e.g. le); selector_pos
        # maps that selector to ''. Do not invent a POS or reject that evidence.
        if (not isinstance(row, dict) or row.get('pos') is not None and not isinstance(row['pos'], str)
                or not isinstance(row.get('en_definition'), str) or not row['en_definition'].strip()):
            raise ValueError('Invalid POS/English sense selector')
        if set(row) - {'pos', 'en_definition', 'zh_definition', 'mt_definition', 'en_explanation',
                       'definition_origin', 'source', 'review_status'}:
            raise ValueError('Forbidden sense translation field')
        selector = (selector_pos(row.get('pos')), row.get('en_definition'))
        if selector in out:
            raise ValueError(f'Duplicate sense selector: {selector}')
        if not isinstance(row.get('zh_definition'), str) or not row['zh_definition'].strip():
            raise ValueError(f'Missing Chinese translation: {selector}')
        if 'mt_definition' in row and (not isinstance(row['mt_definition'], str) or not row['mt_definition'].strip()):
            raise ValueError(f'Empty optional Maltese definition: {selector}')
        if 'en_explanation' in row and (not isinstance(row['en_explanation'], str) or not row['en_explanation'].strip()):
            raise ValueError(f'Empty optional English explanation: {selector}')
        for field, expected in [('definition_origin', 'authored_pedagogical'),
                                ('source', 'phase2_enrichment'), ('review_status', 'phase2_reviewed')]:
            if field in row and row[field] != expected:
                raise ValueError(f'Invalid translation provenance: {selector}')
        out[selector] = row
    return out


def apply_overlay(entry, index, item):
    validate_overlay(item, entry)
    # Recreate derived fields last, including when a previously unenriched
    # published entry already has them. Stable key order is part of byte-level
    # equivalence between a full build and remove/reapply via fast sync.
    entry.pop('display_senses', None)
    entry.pop('sense_guide', None)
    try:
        from .phase2_quality_gates import compute_definite_article
    except ImportError:
        from phase2_quality_gates import compute_definite_article
    key = entry['id']
    if item['exact_key'] != key or index['exact_key'] != key:
        raise ValueError('Overlay key mismatch')
    teaching = deepcopy(item['teaching_sense'])
    if set(teaching) - {'pos', 'en_definition', 'zh_definition', 'mt_definition',
                        'definition_origin', 'source', 'review_status'}:
        raise ValueError(f'{key}: forbidden teaching fields')
    teaching.update(id='teaching', collocations=deepcopy(item['collocations']))
    translations = translations_for(item)
    used = set()
    def translate(sense):
        selector = (selector_pos(sense['pos']), sense['en_definition'])
        if selector in translations:
            row = translations[selector]
            used.add(selector)
            for field in ('zh_definition', 'mt_definition', 'en_explanation'):
                if field in row:
                    sense[field] = row[field]
            # Preserve the original English's licensed_source provenance.
            sense['translation_provenance'] = {
                'definition_origin': 'authored_pedagogical', 'source': 'phase2_enrichment',
                'review_status': 'phase2_reviewed'}
    entry['senses'] = [s for s in entry['senses'] if s['id'] != 'teaching']
    for sense in entry['senses']:
        translate(sense)
    entry['senses'].insert(0, teaching)
    for analysis in entry['lexeme_analyses']:
        for sense in analysis['senses']:
            if (selector_pos(sense['pos']), sense['en_definition']) not in translations:
                raise ValueError(f'{key}: untranslated attested analysis sense: {sense["id"]}')
            translate(sense)
        analysis['definite_article'] = compute_definite_article(entry['headword']['word'], analysis['pos'])
    if used != set(translations):
        raise ValueError(f'{key}: unattested sense selectors: {set(translations) - used}')
    entry['dual_scenarios'] = deepcopy(item['dual_scenarios'])
    entry['etymology']['cognitive_memory_aid'] = item['cognitive_memory_aid']
    entry['etymology']['cognitive_memory_aid_provenance'] = {
        'source_type': 'authored_pedagogical', 'source': 'phase2_enrichment',
        'review_status': 'phase2_reviewed'}
    nominal = next((a['pos'] for a in entry['lexeme_analyses']
                    if compute_definite_article(key, a['pos'])), None)
    entry['inflection_and_clitics']['definite_article'] = compute_definite_article(key, nominal)
    entry['enrichment_status'] = 'phase2_reviewed'
    index.update(gloss_zh=item['gloss_zh'], is_showcase=True, is_enriched=True)
    refresh_display(entry)


def apply_overlays(entries, lite, overlays, baseline=None):
    """Restore previously enriched records before applying current overlays.

    The generated baseline cache supports removal/editing without a raw rebuild.
    It is derived output, never an alternative source dictionary.
    """
    baseline = deepcopy(baseline or {})
    by_id, indices = {e['id']: e for e in entries}, {e['id']: e for e in lite}
    missing = set(overlays) - set(by_id)
    if missing:
        raise ValueError(f'Overlay keys absent from pool: {sorted(missing)}')
    try:
        from .phase2_quality_gates import protected_record
    except ImportError:
        from phase2_quality_gates import protected_record
    for key, original in baseline.items():
        if key not in by_id or protected_record(by_id[key]) != protected_record(original['entry']):
            raise ValueError(f'{key}: baseline source evidence mismatch; run full build')
        index_evidence = lambda item: {k: v for k, v in item.items()
                                      if k not in ('gloss_zh', 'is_showcase', 'is_enriched')}
        if index_evidence(indices[key]) != index_evidence(original['index']):
            raise ValueError(f'{key}: baseline index evidence mismatch; run full build')
        by_id[key].clear(); by_id[key].update(deepcopy(original['entry']))
        indices[key].clear(); indices[key].update(deepcopy(original['index']))
    for key, item in overlays.items():
        if key not in baseline:
            original = deepcopy(by_id[key])
            # Baselines are source snapshots, not a cache of derived learner
            # views. This also makes remove/reapply and full-build/sync identical.
            original.pop('display_senses', None)
            original.pop('sense_guide', None)
            baseline[key] = {'entry': original, 'index': deepcopy(indices[key])}
        apply_overlay(by_id[key], indices[key], item)
    for entry in entries:
        refresh_display(entry)
    return {key: baseline[key] for key in sorted(overlays)}


def enrichment_summary(summary, lite, digests):
    enriched = sum(bool(e.get('is_enriched')) for e in lite)
    summary.update(version=dataset_version(digests), enriched_count=enriched,
                   unenriched_count=len(lite) - enriched,
                   showcase_count=sum(e['is_showcase'] for e in lite),
                   enrichment_files_sha256=digests,
                   samples=[e for e in lite if e['is_showcase']])
    summary['notes'] = [n for n in summary['notes'] if 'await linguistic review' not in n]
    summary['notes'].append('Phase 2 reviewed means editorial review of authored teaching material; independent linguistic and listening acceptance is separate.')
    summary['notes'] = list(dict.fromkeys(summary['notes']))


def write_json(path, value, pretty=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2 if pretty else None,
                         separators=None if pretty else (',', ':')) + '\n'
    pending = path.with_suffix(path.suffix + '.tmp')
    pending.write_text(payload, encoding='utf-8', newline='\n')
    pending.replace(path)
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
