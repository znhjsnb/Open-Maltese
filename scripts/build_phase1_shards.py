"""Deterministic, offline Phase 1 compiler. Python 3 standard library only.

Raw inputs and Phase 0 reports are never modified. Run from any directory:
python -X utf8 scripts/build_phase1_shards.py
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlparse

try:
    from . import phase0_inventory_audit as audit
    from .maltese_alphabet import (MALTESE_UI_BUCKETS_30, maltese_sort_key,
        get_ui_letter_bucket, normalize_exact_search, normalize_ascii_tolerant,
        normalize_nfc, tokenize_root_consonants)
    from .phase1_showcase import SHOWCASE, COLLOCATIONS, GRAMMAR_LOOKUPS, scenarios
except ImportError:
    import phase0_inventory_audit as audit
    from maltese_alphabet import (MALTESE_UI_BUCKETS_30, maltese_sort_key,
        get_ui_letter_bucket, normalize_exact_search, normalize_ascii_tolerant,
        normalize_nfc, tokenize_root_consonants)
    from phase1_showcase import SHOWCASE, COLLOCATIONS, GRAMMAR_LOOKUPS, scenarios

PROJECT = Path(__file__).resolve().parents[1]
VERSION = 'malti-phase1-2026-11-03-r2'
BUCKET_FILES = {b: f"shards/shard_{ {'GĦ':'GH', 'Ċ':'C_DOT', 'Ġ':'G_DOT', 'Ħ':'H_BAR', 'Ż':'Z_DOT', '#':'HASH'}.get(b, b)}.json"
                for b in MALTESE_UI_BUCKETS_30}
SOURCES = {
    'gabra': {'label': 'Ġabra MDX snapshot', 'license': 'CC BY 3.0',
              'license_note': 'Bundled MDX: Camilleri 2013 Appendix D; packager Jingyuan Zheng aħwa correction. Upstream website now labels CC BY 4.0.',
              'url': 'https://mlrs.research.um.edu.mt/resources/gabra/'},
    'kaikki': {'label': 'Kaikki / English Wiktionary', 'license': 'CC BY-SA 4.0',
               'url': 'https://kaikki.org/dictionary/Maltese/'},
    'wikipron': {'label': 'WikiPron (Wiktionary-derived IPA)', 'license': 'CC BY-SA 4.0 data',
                 'url': 'https://github.com/CUNY-CL/wikipron'},
    'camilleri': {'label': 'John J. Camilleri verb inflections', 'license': 'MIT',
                  'url': 'https://github.com/johnjcamilleri/maltese-verb-inflections'},
}


def unique(values):
    return list(dict.fromkeys(v for v in values if v))


def usable_forms(row):
    return [f for f in row.get('forms', []) if audit.valid_surface(f.get('form'))
            and not set(f.get('tags', [])) & {'table-tags', 'inflection-template'}]


def targets(row):
    out = []
    def references(value):
        # Wiktionary's mt-head accepts comma-separated alternative lemmas.
        # Keep the whole string too, so real multiword lemmas remain available.
        values = [value] + re.split(r',\s*|\s+and\s+', value)
        return unique(normalize_exact_search(v) for v in values if audit.valid_surface(v))
    for sense in row.get('senses', []):
        for field in ('form_of', 'alt_of'):
            for ref in sense.get(field, []):
                if isinstance(ref.get('word'), str):
                    for target in references(ref['word']):
                        out.append((target, field + ': ' + ', '.join(sense.get('tags', []))))
    for t in row.get('head_templates', []):
        args = t.get('args', {})
        if t.get('name') == 'mt-head' and (str(args.get('1', '')).endswith(' form')
                                           or args.get('1') == 'misspelling'):
            if isinstance(args.get('2'), str):
                # Expansion repeats the surface and target lemma on ~70K rows.
                # Intern only its grammatical descriptions; both spellings are
                # already explicit in the lookup key and lemma reference.
                descriptions = re.findall(r'(?:^|\n)#\s*([^\n]*?)\s+of\b', t.get('expansion', ''))
                label = 'mt-head: ' + (' / '.join(unique(descriptions)) or args['1'])
                for target in references(args['2']):
                    out.append((target, label))
    return unique(out)


def resolve_edges(key, edges, pool, seen=None):
    """Resolve variant chains; never return absent lemmas or loop on cycles."""
    seen = set() if seen is None else seen
    if key in seen:
        return set()
    if key in pool:
        return {key}
    seen = seen | {key}
    return set().union(*(resolve_edges(k, edges, pool, seen) for k in edges.get(key, ())))


def lexeme_analysis(source, row, record_id, cam_paradigm=None):
    """Preserve source-record boundaries; no fields borrowed from a homograph."""
    gabra = source == 'gabra'
    roots = ([audit.canonical_root(row['root'])] if gabra else list(audit.extract_roots(row)))
    roots = [r for r in roots if r]
    morph = audit.extract_morphology(row) if not gabra else {'number_forms': {}, 'verb_forms': []}
    numbers = morph['number_forms']
    forms = usable_forms(row) if not gabra else []
    heads = [t.get('args', {}) for t in row.get('head_templates', []) if t.get('name') == 'mt-head']
    def form_for(*tags):
        return next((f['form'] for f in forms if set(tags) <= set(f.get('tags', []))
                     and not set(f.get('tags', [])) & {'negative', 'possessive', 'object', 'direct-object', 'indirect-object'}), None)
    pos = row.get('pos') or None
    is_verb = (pos or '').lower() in ('verb', 'v.', 'v')
    cam = (cam_paradigm or {}) if is_verb else {}
    verb_heads = [a for a in heads if a.get('1') == 'verb']
    def verb_arg(name):
        return next((str(a[name]) for a in verb_heads if audit.valid_surface(a.get(name))), None)
    paradigm = {'perfett_3sg_m': form_for('perfect', 'third-person', 'singular', 'masculine') or cam.get('perfett_3sg_m'),
                'imperfett_3sg_m': verb_arg('2') or form_for('imperfect', 'third-person', 'singular', 'masculine') or cam.get('imperfett_3sg_m'),
                'imperattiv_2sg': form_for('imperative', 'singular') or cam.get('imperattiv_2sg'),
                'past_participle': verb_arg('3') or form_for('participle', 'past'),
                'verbal_noun': verb_arg('vn') or verb_arg('5') or form_for('noun-from-verb')}
    genders = unique(a.get('g') for a in heads)
    gender = 'mf.' if any(g in ('mf', 'm-f', 'mfbysense') for g in genders) or {'m', 'f'} <= set(genders) else 'm.' if 'm' in genders else 'f.' if 'f' in genders else None
    if gabra:
        gender = 'f.' if re.search(r'\bf\.', pos or '') else 'm.' if re.search(r'\bm\.', pos or '') else None
    tags = set(row.get('tags', [])) | {t for s in row.get('senses', []) for t in s.get('tags', [])}
    definitions = row['glosses'] if gabra else [d for s in row.get('senses', [])
        if not s.get('form_of') and not s.get('alt_of') and not set(s.get('tags', [])) & {'form-of', 'alt-of', 'no-gloss'} for d in s.get('glosses', [])]
    senses = [{'id': f'{record_id}:s{i}', 'pos': pos, 'en_definition': d,
               'zh_definition': None, 'mt_definition': None, 'source': source,
               'definition_origin': 'licensed_source', 'review_status': 'source_attested', 'collocations': None}
              for i, d in enumerate(unique(definitions), 1)]
    stratum = 'unspecified' if gabra else audit.etymological_stratum(row)
    return {'id': record_id, 'source': source, 'source_record_id': row.get('id') if gabra else record_id,
            'pos': pos, 'etymology_number': row.get('etymology_number'), 'gender': gender,
            'collectivity': 'kollettiv' if 'collective' in tags else 'singulattiv' if 'singulative' in tags else None,
            'root_consonants': roots[0] if len(roots) == 1 else None, 'roots': roots,
            'root_status': 'attested' if roots else 'missing_or_unspecified', 'stratum': stratum,
            'pattern_type': 'hybrid_assimilated' if roots and stratum in ('romance_sicilian_italian', 'english', 'other_or_hybrid') else 'root_and_pattern' if roots else 'unspecified',
            'ipa': row.get('phonetic') or None if gabra else next((s['ipa'] for s in row.get('sounds', []) if s.get('ipa')), None),
            'verb_paradigm': paradigm if is_verb else None,
            'verb_forms_attested': morph['verb_forms'],
            'plural_forms': unique(numbers.get('p', []) + numbers.get('plural', [])) or None,
            'collective_forms': unique(numbers.get('coll', []) + numbers.get('collective', [])) or None,
            'singulative_forms': unique(numbers.get('sing', []) + numbers.get('singulative', [])) or None,
            'attested_form_count': len(forms),
            'attested_forms': [{'form': f['form'], 'tags': f.get('tags', []), 'source': source} for f in forms[:24]] or None,
            'etymology_text': row.get('etymology_text'), 'etymology_templates': row.get('etymology_templates') or None,
            'senses': senses}


def build(raw, output, seed_output):
    raw, output, seed_output = Path(raw), Path(output), Path(seed_output)
    if output.resolve().is_relative_to(raw.resolve()) or seed_output.resolve().is_relative_to(raw.resolve()):
        raise ValueError('Generated outputs must not be written into the raw source directory')
    gabra_report, records = audit.audit_gabra(raw, require_repository=False)
    rows = audit.read_kaikki(raw / 'kaikki.org-dictionary-Maltese.jsonl')
    _, wiki = audit.read_wikipron(raw / 'mlt_latn_broad.tsv')
    gabra, kaikki, names = defaultdict(list), defaultdict(list), {}
    classes = Counter()
    edges = defaultdict(set)
    classified = []
    for rec in records:
        if rec['clean']:
            key = normalize_exact_search(rec['word'])
            gabra[key].append(rec)
            names.setdefault(key, normalize_nfc(rec['word']))
    for row in rows:
        cls = audit.classify_kaikki_row(row)
        classified.append(cls)
        classes[cls] += 1
        key = normalize_exact_search(row['word'])
        edges[key].update(t for t, tag in targets(row))
        if cls in audit.LEMMA_CLASSES and audit.lexical_anomaly(row['word']) is None:
            kaikki[key].append(row)
            names.setdefault(key, normalize_nfc(row['word']))
    pool = set(gabra) | set(kaikki)
    if len(pool) != 24045:
        raise ValueError(f'Phase 0 conservation failed: expected 24045, got {len(pool)}')
    for key, lemma_rows in kaikki.items():
        for row in lemma_rows:
            for form in usable_forms(row):
                # Explicit forms tables bridge references to a participle or
                # variant that itself lacks an independent lemma entry.
                edges[normalize_exact_search(form['form'])].add(key)

    # The lite index aggregates discovery metadata; cards isolate source records.
    root_groups, root_map = defaultdict(list), {}
    for key in pool:
        roots = unique([audit.canonical_root(g['root']) for g in gabra[key]] +
                       [root for row in kaikki[key] for root in audit.extract_roots(row)])
        root_map[key] = roots
        for root in roots:
            root_groups[root].append(key)
    for root in root_groups:
        root_groups[root].sort(key=lambda k: maltese_sort_key(names[k]))

    lookup = defaultdict(lambda: defaultdict(set))
    highlights = defaultdict(list)
    clitics = defaultdict(list)
    cam_forms = defaultdict(list)
    cam_paradigms = defaultdict(dict)

    def add(surface, lemma, tag):
        if lemma in pool and audit.valid_surface(surface):
            surface = normalize_exact_search(surface)
            if surface != lemma:
                lookup[surface][lemma].add(tag)

    unresolved_rows = []
    for row, cls in zip(rows, classified):
        if cls == 'meta_or_affix_or_character':
            continue
        key = normalize_exact_search(row['word'])
        refs = targets(row)
        resolved = set()
        for target, tag in refs:
            found = resolve_edges(target, edges, pool)
            resolved.update(found)
            for lemma in found:
                add(row['word'], lemma, 'kaikki: ' + tag)
        if cls in audit.LEMMA_CLASSES:
            resolved.add(key)
        elif not resolved:
            unresolved_rows.append(row['word'])
        for form in usable_forms(row):
            for lemma in resolved:
                tags = form.get('tags', [])
                add(form['form'], lemma, 'kaikki: ' + ', '.join(tags))
                if key == lemma:
                    item = {'form': normalize_nfc(form['form']), 'tags': tags,
                            'source': 'kaikki', 'source_detail': form.get('source')}
                    highlights[lemma].append(item)

    cam_count = 0
    for path in sorted((raw / 'maltese-verb-inflections').rglob('*.csv')):
        key = normalize_exact_search(path.stem)
        if key not in pool:
            continue
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                form = (row.get('Surface form') or '').strip()
                if not audit.valid_surface(form):
                    continue
                cam_count += 1
                fields = {k: v for k, v in row.items() if k != 'Surface form' and v and v != '-'}
                add(form, key, 'camilleri: ' + ', '.join(f'{k}={v}' for k, v in fields.items()))
                item = {'form': normalize_nfc(form), 'features': fields, 'source': 'camilleri',
                        'source_file': path.relative_to(raw).as_posix()}
                if row.get('DO') == '-' and row.get('IO') == '-' and row.get('Polarity') == 'Pos':
                    aspect, subject = row.get('Aspect'), row.get('Subject')
                    label = ('perfett_3sg_m' if aspect == 'Perf' and subject == 'P3 Sg Masc'
                             else 'imperfett_3sg_m' if aspect == 'Impf' and subject == 'P3 Sg Masc'
                             else 'imperattiv_2sg' if aspect == 'Imp' and subject == 'P2 Sg' else None)
                    if label:
                        cam_paradigms[key].setdefault(label, normalize_nfc(form))
                if len(cam_forms[key]) < 12:
                    cam_forms[key].append(item)
                if (row.get('DO') not in (None, '', '-') or row.get('IO') not in (None, '', '-')) and len(clitics[key]) < 8:
                    clitics[key].append(item)
    for surface, (lemma, tag) in GRAMMAR_LOOKUPS.items():
        add(surface, lemma, 'grammar_reference docs/CODEX_HALLUCINATION_AUDIT.md: ' + tag)
    unresolved_rows = [w for w in unresolved_rows if normalize_exact_search(w) not in lookup]

    entries, lite = [], []
    for key in sorted(pool, key=lambda k: maltese_sort_key(names[k], mode='dms200')):
        gs, ks, word = gabra[key], kaikki[key], names[key]
        rich_gabra = any(audit.canonical_root(g['root']) and g['phonetic'] and g['glosses'] for g in gs)
        tier = 1 if gs and ks else 2 if ks or rich_gabra else 3
        source_presence = (['gabra'] if gs else []) + (['kaikki'] if ks else [])
        ipa = next((g['phonetic'] for g in gs if g['phonetic']), None)
        ipa_source = 'gabra' if ipa else None
        if not ipa:
            ipa = next((s['ipa'] for r in ks for s in r.get('sounds', []) if s.get('ipa')), None)
            ipa_source = 'kaikki' if ipa else None
        if not ipa and wiki.get(key):
            ipa, ipa_source = sorted(wiki[key])[0], 'wikipron'
        if ipa_source == 'wikipron':
            source_presence.append('wikipron')
        audio = next((s for r in ks for s in r.get('sounds', [])
                      if (s.get('mp3_url') or s.get('ogg_url') or '').startswith('https://upload.wikimedia.org/')), None)
        roots = root_map[key]
        strata = unique(audit.etymological_stratum(r) for r in ks)
        strata = [s for s in strata if s != 'unspecified']
        stratum = strata[0] if len(strata) == 1 else 'other_or_hybrid' if strata else 'unspecified'
        morphs = [audit.extract_morphology(r) for r in ks]
        numbers = defaultdict(list)
        for m in morphs:
            for name, values in m['number_forms'].items():
                numbers[name].extend(values)
        forms = highlights[key]
        def form_for(*tags):
            return next((f['form'] for f in forms if set(tags) <= set(f['tags'])), None)
        verb_args = [t.get('args', {}) for r in ks for t in r.get('head_templates', [])
                     if t.get('name') == 'mt-head' and t.get('args', {}).get('1') == 'verb']
        def arg(name):
            return next((str(a[name]) for a in verb_args if audit.valid_surface(a.get(name))), None)
        genders = unique(str(t.get('args', {}).get('g', '')) for r in ks for t in r.get('head_templates', []))
        gender = 'mf.' if any(x in ('mf', 'm-f', 'mfbysense') for x in genders) or {'m', 'f'} <= set(genders) else 'm.' if 'm' in genders else 'f.' if 'f' in genders else None
        tags = {t for r in ks for s in r.get('senses', []) for t in s.get('tags', [])}
        collectivity = 'kollettiv' if 'collective' in tags else 'singulattiv' if 'singulative' in tags else None
        senses = []
        seen_senses = set()
        for source, pos, definitions in ([('gabra', g['pos'], g['glosses']) for g in gs] +
                [('kaikki', r.get('pos'), s.get('glosses', [])) for r in ks for s in r.get('senses', [])
                 if not s.get('form_of') and not s.get('alt_of') and not set(s.get('tags', [])) & {'form-of', 'alt-of', 'no-gloss'}]):
            for definition in definitions:
                if (source, pos, definition) in seen_senses:
                    continue
                seen_senses.add((source, pos, definition))
                senses.append({'id': f's{len(senses)+1}', 'pos': pos or None,
                    'en_definition': definition, 'zh_definition': None, 'mt_definition': None,
                    'definition_origin': 'licensed_source', 'source': source, 'collocations': None})
        if key in SHOWCASE:
            # A separate teaching sense avoids attaching one translation to all
            # independent homographs and unrelated meanings.
            en, zh = SHOWCASE[key][:2]
            mt_phrase, en_phrase, zh_phrase = COLLOCATIONS[key]
            senses.insert(0, {'id': 'teaching', 'pos': None, 'en_definition': en,
                'zh_definition': zh, 'mt_definition': None, 'definition_origin': 'authored_pedagogical',
                'source': 'phase1_showcase', 'review_status': 'pending_linguistic_review',
                'collocations': [{'mt': mt_phrase, 'en': en_phrase, 'zh': zh_phrase,
                                  'source_type': 'pedagogical_example', 'review_status': 'pending_linguistic_review'}]})
        pos_list = unique([g['pos'] for g in gs] + [r.get('pos') for r in ks])
        verb_form = unique(v for m in morphs for v in m['verb_forms'])
        # Paradigm labels must not select negative forms whose Kaikki tags omit polarity.
        imperfect = arg('2') or form_for('imperfect', 'third-person', 'singular', 'masculine') or cam_paradigms[key].get('imperfett_3sg_m')
        pp = arg('3') or form_for('participle', 'past')
        vn = arg('vn') or arg('5') or form_for('noun-from-verb')
        plural = unique(numbers['p'] + numbers['plural'])
        family = unique(names[k] for root in roots for k in root_groups[root] if k != key)[:16]
        ety_text = unique(r.get('etymology_text') for r in ks)
        chain = []
        for r in ks:
            for t in r.get('etymology_templates', []):
                # Preserve structured arguments; corrupted expansion HTML isn't a source chain.
                if t.get('name') in ('ety', 'bor', 'bor+', 'inh', 'inh+', 'der', 'der+', 'cog', 'calque'):
                    item = {'template': t['name'], 'args': t.get('args', {}), 'source': 'kaikki'}
                    if item not in chain:
                        chain.append(item)
        synonyms, antonyms = [], []
        for r in ks:
            for container in [r] + r.get('senses', []):
                synonyms.extend(x.get('word') for x in container.get('synonyms', []))
                antonyms.extend(x.get('word') for x in container.get('antonyms', []))
        register = sorted(t for t in tags if t in ('archaic', 'obsolete', 'slang', 'formal', 'colloquial', 'vulgar', 'dated', 'rare'))
        cognates = [c for c in chain if c['template'] == 'cog']
        article = next(({'form': surface, 'prefix': surface.split('-')[0] + '-',
                         'note': tag, 'source_type': 'grammar_reference',
                         'source': 'docs/CODEX_HALLUCINATION_AUDIT.md'}
                        for surface, (lemma, tag) in GRAMMAR_LOOKUPS.items()
                        if lemma == key and 'definite article' in tag), None)
        entry = {'id': key, 'headword': {'word': word, 'tier': tier, 'gender': gender,
            'collectivity': collectivity, 'ipa': ipa, 'ipa_source': ipa_source,
            'ipa_scheme': 'source_transcription_preserved',
            'audio_url': (audio.get('mp3_url') or audio.get('ogg_url')) if audio else None,
            'audio_note': {'note': audio.get('note'), 'file': audio.get('audio'),
                'source': 'kaikki', 'license_note': 'See individual Wikimedia Commons file page.'} if audio else None,
            'source_presence': source_presence, 'editorial_status': 'source_attested'},
            'morphology': {'pattern_type': 'hybrid_assimilated' if roots and stratum in ('romance_sicilian_italian', 'english', 'other_or_hybrid') else 'root_and_pattern' if roots else 'unspecified',
                'root_consonants': roots[0] if roots else None,
                'root_radicals': tokenize_root_consonants(roots[0]) if roots else None,
                'root_evidence': [{'root': root, 'sources': unique(
                    ['gabra' for g in gs if audit.canonical_root(g['root']) == root] +
                    ['kaikki' for r in ks if root in audit.extract_roots(r)])} for root in roots],
                'verb_form': 'Forma ' + verb_form[0] if len(verb_form) == 1 else None,
                'verb_forms_attested': ['Forma ' + v for v in verb_form],
                'imperfect': imperfect, 'past_participle': pp, 'verbal_noun': vn,
                'plural_forms': plural or None, 'collective_form': next(iter(numbers['coll'] + numbers['collective']), None),
                'singulative_form': next(iter(numbers['sing'] + numbers['singulative']), None),
                'word_family': family or None},
            'senses': senses, 'dual_scenarios': scenarios(key),
            'inflection_and_clitics': {'perfett_3sg_m': form_for('perfect', 'third-person', 'singular', 'masculine') or cam_paradigms[key].get('perfett_3sg_m'),
                'imperfett_3sg_m': imperfect, 'imperattiv_2sg': form_for('imperative', 'singular') or cam_paradigms[key].get('imperattiv_2sg'),
                'plural': plural or None, 'attested_forms': (forms[:24] + cam_forms[key]) or None,
                'definite_article': article, 'pronomi_mehmuzin': clitics[key] or None},
            'pragmatics_and_cognates': {'register': register or None, 'synonyms': unique(synonyms) or None,
                'antonyms': unique(antonyms) or None, 'cognates_and_false_friends': cognates or None}
                if register or synonyms or antonyms or cognates else None,
            'etymology': {'stratum': stratum, 'etymology_text_en': '\n\n'.join(ety_text) or None,
                'source_chain': chain or None, 'cognitive_memory_aid': None}}
        analyses = [lexeme_analysis('gabra', g, f'gabra:{g["id"]}') for g in gs]
        analyses += [lexeme_analysis('kaikki', r, f'kaikki:{key}:{i}',
                     cam_paradigms[key] if sum(r.get('pos') == 'verb' for r in ks) == 1 else None)
                     for i, r in enumerate(ks)]
        entry['lexeme_analyses'] = analyses
        for analysis in analyses:
            analysis['word_family'] = unique(names[k] for root in analysis['roots']
                for k in root_groups[root] if k != key)[:16] or None
            analysis['definite_article'] = article if (analysis['pos'] or '').lower() in audit.NOMINAL_POS else None
            analysis['pronomi_mehmuzin'] = None
            if (analysis['source'] == 'kaikki' and analysis['pos'] == 'verb'
                    and sum(r.get('pos') == 'verb' for r in ks) == 1):
                analysis['attested_forms'] = (analysis['attested_forms'] or []) + cam_forms[key] or None
                analysis['pronomi_mehmuzin'] = clitics[key] or None
        entry['morphology']['root_status'] = 'attested' if roots else 'missing_or_unspecified'
        # Top-level discovery fields are retained for compatibility. A scalar
        # is published only when all non-null analyses agree on its value.
        def consensus(values):
            found = unique(values)
            return found[0] if len(found) == 1 else None
        entry['headword']['gender'] = consensus(a['gender'] for a in analyses)
        entry['headword']['collectivity'] = consensus(a['collectivity'] for a in analyses)
        for name in ('imperfect', 'past_participle', 'verbal_noun'):
            field = 'imperfett_3sg_m' if name == 'imperfect' else name
            entry['morphology'][name] = consensus((a['verb_paradigm'] or {}).get(field) for a in analyses)
        # Never advertise a plural from a different POS as this verb's plural.
        entry['morphology']['plural_forms'] = unique(p for a in analyses for p in a['plural_forms'] or []) or None
        entry['inflection_and_clitics']['plural'] = entry['morphology']['plural_forms']
        h = entry['headword']
        audio_file = (audio.get('audio') or unquote(urlparse(h['audio_url']).path.rsplit('/', 1)[-1])) if audio else None
        h['audio_file'] = audio_file
        h['audio_commons_url'] = 'https://commons.wikimedia.org/wiki/File:' + quote(audio_file.replace(' ', '_'), safe='') if audio_file else None
        entries.append(entry)
        lite.append({'id': key, 'word': word, 'exact_key': key, 'ascii_key': normalize_ascii_tolerant(word),
            **get_ui_letter_bucket(word), 'tier': tier, 'pos_list': pos_list, 'ipa': ipa,
            'root': roots[0] if roots else None, 'roots': roots, 'stratum': stratum,
            'strata': unique(a['stratum'] for a in analyses),
            'gloss_en': unique(s['en_definition'] for s in senses)[:3],
            'gloss_zh': SHOWCASE[key][1] if key in SHOWCASE else None,
            'has_audio': bool(audio), 'is_showcase': key in SHOWCASE, 'source_presence': source_presence})

    lookup_out = {surface: [{'lemma': lemma, 'tag': ' | '.join(sorted(tags))}
                           for lemma, tags in sorted(candidates.items())]
                  for surface, candidates in sorted(lookup.items())}
    tag_table = sorted({r['tag'] for candidates in lookup_out.values() for r in candidates})
    tag_ids = {tag: i for i, tag in enumerate(tag_table)}
    compact_lookup = {'version': VERSION, 'tags': tag_table,
        'forms': {surface: [[r['lemma'], tag_ids[r['tag']]] for r in candidates]
                  for surface, candidates in lookup_out.items()}}
    tiers = dict(sorted(Counter(str(e['tier']) for e in lite).items()))
    bucket_counts = {b: sum(e['bucket'] == b for e in lite) for b in MALTESE_UI_BUCKETS_30}
    prefixes = {b: dict(sorted(Counter(e['sub_prefix'] for e in lite if e['bucket'] == b and e['sub_prefix']).items(),
                               key=lambda kv: (kv[0] != 'ie', maltese_sort_key(kv[0])))) for b in MALTESE_UI_BUCKETS_30}
    summary = {'version': VERSION, 'total_lemmas': len(lite), 'tier_counts': tiers,
        'enrichment_target_count': tiers.get('1', 0) + tiers.get('2', 0),
        'bucket_counts': bucket_counts, 'audio_count': sum(e['has_audio'] for e in lite),
        'root_count': sum(bool(e['root']) for e in lite), 'unique_roots': len(root_groups),
        'stratum_counts': dict(sorted(Counter(e['stratum'] for e in lite).items())),
        'kaikki_row_classes': dict(classes), 'unresolved_reference_rows': len(unresolved_rows),
        'unresolved_reference_samples': sorted(set(unresolved_rows))[:16],
        'tier_policy': 'Tier 2 Gabra-only requires a single record with a valid attested root, phonetic and glosses.',
        'audio_source_rows': sum(any(s.get('mp3_url') or s.get('ogg_url') for s in r.get('sounds', [])) for r in rows),
        'wordform_surface_count': len(lookup_out), 'camilleri_rows_indexed': cam_count,
        'showcase_count': sum(e['id'] in SHOWCASE for e in lite),
        'samples': [e for e in lite if e['id'] in SHOWCASE],
        'notes': ['Counts are measured, not rounded target promises.',
            'Tier 1 denotes source presence, not independent verification.',
            'WikiPron and Kaikki both derive from Wiktionary.',
            'Grammar lookup exceptions are labelled grammar_reference, not corpus-attested.',
            'Teaching examples and translations await linguistic review.']}
    output.mkdir(parents=True, exist_ok=True)
    def write(path, value, pretty=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, ensure_ascii=False, indent=2 if pretty else None,
                             separators=None if pretty else (',', ':')) + '\n'
        pending = path.with_suffix(path.suffix + '.tmp')
        pending.write_text(payload, encoding='utf-8', newline='\n')
        pending.replace(path)
        return {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    shard_meta = []
    for bucket in MALTESE_UI_BUCKETS_30:
        content = [entry for entry, idx in zip(entries, lite) if idx['bucket'] == bucket]
        filename = BUCKET_FILES[bucket]
        digest = write(output / filename, content)
        shard_meta.append({'bucket': bucket, 'file': filename, 'count': len(content), **digest})
    index_meta = write(output / 'index_lite.json', lite)
    lookup_meta = write(output / 'wordforms_lookup.json', compact_lookup)
    manifest = {**{k: v for k, v in summary.items() if k != 'samples'},
        'MALTESE_UI_BUCKETS_30': list(MALTESE_UI_BUCKETS_30), 'shards': shard_meta,
        'sub_prefix_counts': prefixes,
        'root_index_summary': {'root_count': len(root_groups),
            'roots': {root: [names[k] for k in members] for root, members in sorted(root_groups.items())}},
        'index_lite': {'file': 'index_lite.json', **index_meta},
        'wordforms_lookup': {'file': 'wordforms_lookup.json', **lookup_meta},
        'sources': SOURCES,
        'raw_source_sha256': {path.relative_to(raw).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [raw / 'GabraMalteseDict_MDX_v1.0.zip', raw / 'kaikki.org-dictionary-Maltese.jsonl',
                         raw / 'mlt_latn_broad.tsv'] + sorted((raw / 'maltese-verb-inflections').rglob('*.csv'))},
        'gabra_mdx_sha256': gabra_report['mdx_sha256']}
    write(output / 'manifest.json', manifest, True)
    write(seed_output, summary, True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=PROJECT / 'data/raw')
    parser.add_argument('--output', type=Path, default=PROJECT / 'app/static/data')
    parser.add_argument('--summary', type=Path, default=PROJECT / 'data/seed/lemma_pool_summary.json')
    args = parser.parse_args()
    summary = build(args.raw, args.output, args.summary)
    print(json.dumps({k: summary[k] for k in ('version', 'total_lemmas', 'tier_counts',
        'audio_count', 'root_count', 'wordform_surface_count', 'showcase_count')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
