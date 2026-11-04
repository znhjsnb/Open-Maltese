"""Deterministic Phase 2 structural/evidence gates (not a linguistic oracle).

Run after build/sync. Exit 1 on any gate failure; no timestamps or random samples.
The report deliberately separates machine checks from human content acceptance.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

try:
    from .sense_display import display_layer, teaching_sense, entry_collocations
except ImportError:
    from sense_display import display_layer, teaching_sense, entry_collocations

try:
    from .phase2_enrichment import (PROJECT, OVERLAY_DIR, load_overlays, pos_class,
                                    translations_for, write_json, anti_dilution_errors, selector_pos)
except ImportError:
    from phase2_enrichment import (PROJECT, OVERLAY_DIR, load_overlays, pos_class,
                                  translations_for, write_json, anti_dilution_errors, selector_pos)

NOMINAL_POS = {'noun', 'n.', 'n.m.', 'n.f.', 'adj', 'adj.', 'num', 'num.'}
SUN = 'ċdnrstxżz'
SIBILANTS = 'sxżz'
ARTICLE_SOURCE = 'docs/MASTER_PLAN_V2.md#gate-3'
APOSTROPHES = '‘’‛ʼ＇′`´'
HYPHENS = '‐‑‒–−'


def compute_definite_article(word, pos):
    """Canonical citation-context article; adjectives/numerals used nominally.

    This bounded engine does not claim to decide arbitrary connected speech.
    In particular għ/h can take l-i- after a preceding consonant.
    """
    if pos_class(pos) not in {'noun', 'adj', 'num'}:
        return None
    word = unicodedata.normalize('NFC', word).strip().lower()
    if not word or not word[0].isalpha():
        raise ValueError('Article requires a nonempty alphabetic word')
    rest = word[1:]
    next_grapheme = 'għ' if rest.startswith('għ') else rest[:1]
    consonant = next_grapheme and next_grapheme not in ('a', 'e', 'i', 'o', 'u', 'għ', 'h') and next_grapheme.isalpha()
    # Lexical exception fixed by the project's audited reference, not a rule
    # that inserts i before every consonant cluster (żmien is iż-żmien).
    if word[0] in SIBILANTS and consonant and word != 'żmien':
        prefix, rule = 'l-i', 'vokali_tal_lehen'
    elif word[0] in 'aeiou' or word.startswith(('għ', 'h')):
        prefix, rule = 'l-', 'vowel_or_silent_gh_h'
    elif word[0] in SUN:
        prefix, rule = 'i' + word[0] + '-', 'sun_assimilation'
    else:
        prefix, rule = 'il-', 'moon_consonant'
    note = 'Canonical citation context; preceding vowels may elide article i.'
    if word.startswith(('għ', 'h')):
        note += ' għ-/h- words may take contextual l-i- after consonants.'
    return {'form': prefix + word, 'prefix': prefix, 'rule': rule,
            'context': 'citation', 'note': note,
            'source_type': 'grammar_reference', 'source': ARTICLE_SOURCE}


def validate_definite_article(word, article_obj):
    if not isinstance(article_obj, dict):
        return False
    expected = compute_definite_article(word, 'noun')
    return (article_obj.get('form') == expected['form']
            and article_obj.get('prefix') == expected['prefix']
            and article_obj.get('source_type') == 'grammar_reference'
            and article_obj.get('source') == ARTICLE_SOURCE
            and article_obj.get('context', 'citation') == 'citation')


def strings(value, path=''):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield path + '.<key>', key
            yield from strings(item, path + '.' + key)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from strings(item, f'{path}[{i}]')


def gate1(entries, overlays, assets=None):
    errors = []
    for path, text in strings({'entries': entries, 'overlays': overlays, 'assets': assets}):
        if text != unicodedata.normalize('NFC', text):
            errors.append(path + ': non-NFC')
        if any(unicodedata.category(c) in ('Cc', 'Cf') for c in text):
            errors.append(path + ': control/format character')
        if re.search(r'\?{4,}|\b(?:TODO|TBD)\b|\ufffd', text):
            errors.append(path + ': placeholder or replacement character')
        # Orthographic punctuation in Maltese fields and selectors only;
        # English quotations and dialogue em dashes remain ordinary punctuation.
        if path.endswith(('.mt', '.mt_definition', '.mt_spoken', '.mt_standard', '.exact_key')):
            if any(c in text for c in APOSTROPHES + HYPHENS):
                errors.append(path + ': unnormalised Maltese punctuation')
            if re.search(r'[\u0300-\u036f]', text):
                errors.append(path + ': unsupported combining letter')
    return errors


def protected_record(entry):
    """Evidence fields excluding only the explicitly allowed authored additions."""
    source_sense = lambda s: {k: v for k, v in s.items() if k not in
        ('zh_definition', 'mt_definition', 'en_explanation', 'translation_provenance')}
    analyses = []
    for a in entry['lexeme_analyses']:
        analyses.append({k: v for k, v in a.items() if k not in ('senses', 'definite_article')})
        analyses[-1]['senses'] = [source_sense(s) for s in a['senses']]
    return {'headword': entry['headword'], 'morphology': entry['morphology'],
            'analyses': analyses, 'stratum': entry['etymology']['stratum'],
            'source_senses': [source_sense(s) for s in entry['senses'] if s.get('id') != 'teaching'],
            'source_chain': entry['etymology']['source_chain'],
            'attested_forms': entry['inflection_and_clitics']['attested_forms']}


def gate2(entries, overlays, baseline):
    errors = []
    for e in entries:
        key, morph = e['id'], e['morphology']
        senses, guide = display_layer(e)
        if e.get('display_senses') != senses or e.get('sense_guide') != guide:
            errors.append(key + ': stale or invalid display sense bindings')
        if key in baseline and protected_record(e) != protected_record(baseline[key]['entry']):
            errors.append(key + ': protected source evidence changed')
        roots = morph.get('root_consonants')
        if roots and not any(r.get('root') == roots and r.get('sources') for r in morph.get('root_evidence', [])):
            errors.append(key + ': root without source evidence')
        if e['etymology']['stratum'] in ('romance_sicilian_italian', 'english') and roots:
            if morph.get('pattern_type') != 'hybrid_assimilated':
                errors.append(key + ': loan root without attested hybrid analysis')
        if key == 'skola' and 'skejjel' in (morph.get('plural_forms') or []):
            if morph['pattern_type'] != 'hybrid_assimilated':
                errors.append(key + ': skola/skejjel hybrid lost')
        if morph.get('verb_form') and morph['verb_form'] not in morph.get('verb_forms_attested', []):
            errors.append(key + ': unattested verb form')
        if key not in overlays:
            continue
        expected = translations_for(overlays[key])
        for a in e['lexeme_analyses']:
            for s in a['senses']:
                selector = (selector_pos(s['pos']), s['en_definition'])
                row = expected.get(selector)
                if not row or s.get('zh_definition') != row['zh_definition']:
                    errors.append(key + ':' + s['id'] + ': missing or cross-sense Chinese translation')
                if row and any(s.get(field) != row.get(field) for field in ('mt_definition', 'en_explanation')):
                    errors.append(key + ':' + s['id'] + ': cross-sense refinement mismatch')
        for s in e['senses']:
            if s['id'] != 'teaching':
                row = expected.get((selector_pos(s['pos']), s['en_definition']))
                if not row or s.get('zh_definition') != row['zh_definition']:
                    errors.append(key + ':' + s['id'] + ': flattened sense mismatch')
                if row and any(s.get(field) != row.get(field) for field in ('mt_definition', 'en_explanation')):
                    errors.append(key + ':' + s['id'] + ': flattened refinement mismatch')
        # Fixed minimal regression anchors are independent of overlay content.
        if key == 'dar':
            anchors = {'house': '房', 'home': '家', 'room': '房', 'family': '家',
                       'to turn': '转', 'to reside': '居', 'to dwell': '居'}
            for a in e['lexeme_analyses']:
                for s in a['senses']:
                    token = anchors.get(s['en_definition'])
                    if token and token not in (s.get('zh_definition') or ''):
                        errors.append('dar:' + s['id'] + ': homograph sense contamination')
    return errors


def gate3(entries, overlays, lookup):
    errors = []
    forms, tags = lookup.get('forms', {}), lookup.get('tags', [])
    for e in entries:
        key, word = e['id'], e['headword']['word']
        # Every enriched nominal analysis must have its own validated article.
        for a in e['lexeme_analyses']:
            article = a.get('definite_article')
            nominal = pos_class(a.get('pos')) in {'noun', 'adj', 'num'}
            if nominal and not validate_definite_article(word, article):
                errors.append(key + ':' + a['id'] + ': invalid/missing nominal article')
            elif article and (not nominal or not validate_definite_article(word, article)):
                errors.append(key + ':' + a['id'] + ': invalid article')
        top = e['inflection_and_clitics'].get('definite_article')
        has_nominal = any(pos_class(a.get('pos')) in {'noun', 'adj', 'num'} for a in e['lexeme_analyses'])
        if has_nominal and not validate_definite_article(word, top):
            errors.append(key + ': invalid/missing top-level nominal article')
        elif top and (not has_nominal or not validate_definite_article(word, top)):
            errors.append(key + ': invalid top-level article')
        containers = [e['inflection_and_clitics']] + e['lexeme_analyses']
        for container in containers:
            for clitic in container.get('pronomi_mehmuzin') or []:
                candidates = forms.get(clitic['form'].lower(), [])
                if not any(link[0] == key and clitic.get('source') in tags[link[1]]
                           and not tags[link[1]].startswith('grammar_reference') for link in candidates):
                    errors.append(key + ': unattested attached pronoun: ' + clitic['form'])
    return errors


def gate4(entries, overlays, manifest, check_audio_totals=True):
    errors = []
    licenses = {'gabra': 'CC BY 3.0', 'kaikki': 'CC BY-SA 4.0',
                'wikipron': 'CC BY-SA 4.0 data', 'camilleri': 'MIT'}
    sources = manifest.get('sources', {})
    for source, license in licenses.items():
        if sources.get(source, {}).get('license') != license:
            errors.append(source + ': incorrect license')
    if 'CC BY 4.0' not in sources.get('gabra', {}).get('license_note', ''):
        errors.append('gabra: missing upstream license distinction')
    for path, value in strings(sources):
        if re.search(r'masri|dizzjunarju\.mt|BY-NC', value, re.I):
            errors.append(path + ': excluded/unlicensed source')
    audio_count = 0
    for e in entries:
        key = e['id']
        h = e['headword']
        if key in overlays or e.get('enrichment_status') == 'phase2_reviewed':
            collocations = entry_collocations(e)
            errors.extend(key + ': ' + error for error in anti_dilution_errors(
                collocations, e.get('dual_scenarios'), e['etymology'].get('cognitive_memory_aid'),
                [s for a in e['lexeme_analyses'] for s in a['senses']]))
        if set(h['source_presence']) - set(licenses):
            errors.append(key + ': unapproved source')
        if h.get('audio_url'):
            audio_count += 1
            if not (h.get('audio_commons_url') or '').startswith('https://commons.wikimedia.org/wiki/File:'):
                errors.append(key + ': missing Commons attribution link')
        for path, value in strings(e):
            if path.endswith(('.source', '.source_file', '.source_type')) and re.search(r'masri|dizzjunarju|BY-NC', value, re.I):
                errors.append(key + path + ': forbidden source')
        for s in e['senses'] + [s for a in e['lexeme_analyses'] for s in a['senses']]:
            if s.get('zh_definition') or s.get('mt_definition') or s.get('en_explanation'):
                origin = s.get('translation_provenance', {}).get('definition_origin', s.get('definition_origin'))
                if origin != 'authored_pedagogical':
                    errors.append(key + ': unlabelled authored definition')
            for c in s.get('collocations') or []:
                if c.get('source_type') != 'pedagogical_example':
                    errors.append(key + ': unlabelled collocation')
        if e.get('dual_scenarios'):
            for name, origin in [('formal', 'pedagogical_example'), ('colloquial', 'pedagogical_dialogue')]:
                if e['dual_scenarios'].get(name, {}).get('source_type') != origin:
                    errors.append(key + ': unlabelled scenario')
        if key in overlays:
            item = overlays[key]
            teaching = item.get('teaching_sense', {})
            published = teaching_sense(e) or {}
            if any(published.get(k) != v for k, v in teaching.items()) or published.get('collocations') != item.get('collocations'):
                errors.append(key + ': published teaching material differs from overlay')
            if e['dual_scenarios'] != item.get('dual_scenarios'):
                errors.append(key + ': published scenarios differ from overlay')
            if (teaching.get('definition_origin'), teaching.get('source'), teaching.get('review_status')) != ('authored_pedagogical', 'phase2_enrichment', 'phase2_reviewed'):
                errors.append(key + ': invalid teaching provenance')
            if len(item.get('collocations', [])) < 2:
                errors.append(key + ': fewer than two collocations')
            for c in item.get('collocations', []):
                if c.get('source_type') != 'pedagogical_example' or c.get('review_status') != 'phase2_reviewed':
                    errors.append(key + ': invalid collocation provenance')
            for obj in [teaching] + item.get('collocations', []) + [item.get('dual_scenarios', {}).get(n, {}) for n in ('formal', 'colloquial')]:
                fields = ('en_definition', 'zh_definition', 'mt_definition') if obj is teaching else ('mt', 'en', 'zh')
                if not all(isinstance(obj.get(k), str) and obj[k].strip() for k in fields):
                    errors.append(key + ': incomplete trilingual material')
            aid = e['etymology'].get('cognitive_memory_aid')
            if not aid or e['etymology'].get('cognitive_memory_aid_provenance', {}).get('source_type') != 'authored_pedagogical':
                errors.append(key + ': missing/unlabelled mnemonic')
            if aid != item.get('cognitive_memory_aid'):
                errors.append(key + ': published mnemonic differs from overlay')
            teaching_text = json.dumps(item, ensure_ascii=False)
            # Historical context can be explicit in a licensed definition, not
            # just in an etymology. Authored teaching text is never evidence.
            historical = '\n'.join([e['etymology'].get('etymology_text_en') or ''] + [
                s['en_definition'] for a in e['lexeme_analyses'] for s in a['senses']
                if s.get('definition_origin') == 'licensed_source'])
            for claim, evidence in [('骑士团时期', r'knights|hospitaller|order of saint john'), ('英国海军时期', r'british navy|royal navy'),
                                    ('阿拉伯统治时期', r'arab rule|arab period'), ('阿拉伯时期', r'arab rule|arab period'),
                                    ('英国殖民时期', r'british|colonial'), ('中世纪时期', r'medieval|middle ages')]:
                if claim in teaching_text and not re.search(evidence, historical, re.I):
                    errors.append(key + ': unsupported historical story')
    if check_audio_totals and audio_count != 597:
        errors.append(f'Expected 597 audio entries, got {audio_count}')
    if check_audio_totals and manifest.get('audio_count') != 597:
        errors.append('Manifest audio count must equal 597')
    return errors


def gate5(entries, index, lookup, manifest, overlays):
    errors = []
    keys = [e['id'] for e in entries]
    tiers = dict(Counter(str(e['tier']) for e in index))
    enriched = sum(bool(e.get('is_enriched')) for e in index)
    checks = {
        'lemmas': len(keys) == len(set(keys)) == len(index) == manifest.get('total_lemmas') == 24045,
        'index_keys': set(keys) == {e['exact_key'] for e in index},
        'tiers': tiers == {'1': 5051, '2': 11414, '3': 7580} == manifest.get('tier_counts'),
        'surface_forms': len(lookup.get('forms', {})) == manifest.get('wordform_surface_count') == 124488,
        'enriched': enriched == len(overlays) == manifest.get('enriched_count'),
        'enriched_keys': {e['id'] for e in entries if e.get('enrichment_status') == 'phase2_reviewed'} == {i['id'] for i in index if i.get('is_enriched')} == set(overlays),
        'remaining': manifest.get('unenriched_count') == 24045 - enriched,
        'showcase': sum(bool(e['is_showcase']) for e in index) == manifest.get('showcase_count'),
        'version': lookup.get('version') == manifest.get('version'),
    }
    errors.extend('Conservation failed: ' + name for name, passed in checks.items() if not passed)
    return errors


def content_samples(entries, index):
    indexed = {i['id']: i for i in index}
    strata = defaultdict(list)
    for e in entries:
        i = indexed[e['id']]
        strata[f"tier_{i['tier']}/{e['etymology']['stratum']}/{'enriched' if i.get('is_enriched') else 'unenriched'}"].append(e)
    samples = []
    for label, group in sorted(strata.items()):
        for e in sorted(group, key=lambda e: hashlib.sha256(e['id'].encode()).hexdigest())[:3]:
            samples.append({'stratum': label, 'exact_key': e['id'],
                'analysis_pos': [a['pos'] for a in e['lexeme_analyses']],
                'senses': [{k: s.get(k) for k in ('pos', 'en_definition', 'zh_definition', 'mt_definition', 'definition_origin')} for s in e['senses'][:3]],
                'definite_article': e['inflection_and_clitics']['definite_article'],
                'dual_scenarios': e['dual_scenarios'],
                'cognitive_memory_aid': e['etymology']['cognitive_memory_aid']})
    return samples


def validate_dataset(data_dir=PROJECT / 'app/static/data', overlay_dir=OVERLAY_DIR):
    data_dir = Path(data_dir)
    read = lambda name: json.loads((data_dir / name).read_text(encoding='utf-8'))
    manifest, index, lookup = read('manifest.json'), read('index_lite.json'), read('wordforms_lookup.json')
    entries = [e for shard in manifest['shards'] for e in read(shard['file'])]
    overlays, digests = load_overlays(overlay_dir)
    baseline = read('phase2_baseline.json')
    names = ['orthography_and_nfc', 'diachronic_synchronic_honesty', 'definite_article_and_clitics',
             'provenance_and_copyright', 'conservation_and_sampling']
    results = [gate1(entries, overlays, {'index': index, 'lookup': lookup, 'manifest': manifest}), gate2(entries, overlays, baseline),
               gate3(entries, overlays, lookup), gate4(entries, overlays, manifest),
               gate5(entries, index, lookup, manifest, overlays)]
    # Manifest integrity and overlay freshness are part of conservation, not silently assumed.
    for meta in manifest['shards'] + [manifest['index_lite'], manifest['wordforms_lookup']]:
        raw = (data_dir / meta['file']).read_bytes()
        if len(raw) != meta['bytes'] or hashlib.sha256(raw).hexdigest() != meta['sha256']:
            results[4].append(meta['file'] + ': digest mismatch')
    if digests != manifest.get('enrichment_files_sha256'):
        results[4].append('Overlays changed since last build/sync')
    return {'schema_version': 1, 'dataset_version': manifest['version'],
        'passed': not any(results),
        'gates': {name: {'passed': not errors, 'error_count': len(errors), 'errors': sorted(errors)}
                  for name, errors in zip(names, results)},
        'counts': {k: manifest.get(k) for k in ('total_lemmas', 'tier_counts', 'enriched_count', 'unenriched_count', 'showcase_count', 'wordform_surface_count', 'audio_count')},
        'stratified_content_samples': content_samples(entries, index),
        'limitations': ['Deterministic structural and evidence checks cannot certify idiomaticity or historical truth.',
                       'phase2_reviewed denotes authored editorial review, not independent native-speaker approval.',
                       'Browser, audio/listening and human linguistic acceptance are separate checks.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=PROJECT / 'app/static/data')
    parser.add_argument('--overlays', type=Path, default=OVERLAY_DIR)
    parser.add_argument('--report', type=Path, default=PROJECT / 'data/audit/phase2_quality_gate_report.json')
    args = parser.parse_args()
    report = validate_dataset(args.data, args.overlays)
    write_json(args.report, report, pretty=True)
    print(json.dumps({'passed': report['passed'], 'gates': {n: g['error_count'] for n, g in report['gates'].items()}}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
