"""Deterministic learner view. Source senses and analysis identities are never edited.

String equality is deliberately conservative: punctuation is meaningful, and an
ambiguous same-source analysis match prevents cross-source fusion altogether.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import re
import unicodedata


def pos_class(pos):
    pos = (pos or '').strip().lower()
    return {'n.': 'noun', 'n.m.': 'noun', 'n.f.': 'noun', 'adj.': 'adj',
            'adjective': 'adj', 'adverb': 'adv', 'num.': 'num', 'numeral': 'num',
            'v.': 'verb', 'v': 'verb', 'adp': 'prep', 'preposition': 'prep',
            'pronoun': 'pron', 'conjunction': 'conj', 'sconj': 'conj', 'cconj': 'conj',
            'interjection': 'intj', 'particle': 'part', 'article': 'art',
            'name': 'propn'}.get(pos, pos)


def normalized_gloss(text):
    return ' '.join(unicodedata.normalize('NFC', text or '').split()).casefold()


def teaching_sense(entry):
    # Legacy storage remains readable by existing overlays and audit consumers.
    return next((s for s in entry['senses'] if s.get('id') == 'teaching'), None)


def entry_collocations(entry):
    return [c for s in entry['senses'] for c in (s.get('collocations') or [])]


def compatible_analyses(analyses):
    """Missing evidence is not a conflict; conflicting attested evidence is."""
    for i, a in enumerate(analyses):
        for b in analyses[i + 1:]:
            if a['source'] == b['source']:
                return False
            ar, br = set(a.get('roots') or []), set(b.get('roots') or [])
            if ar and br and ar != br:
                return False
            for field in ('gender', 'collectivity', 'stratum'):
                av, bv = a.get(field), b.get(field)
                if av and bv and 'unspecified' not in (av, bv) and av != bv:
                    return False
    return True


def teaching_matches(teaching, group):
    if pos_class(teaching.get('pos')) != group['pos']:
        return False
    en = normalized_gloss(teaching.get('en_definition'))
    if any(en == normalized_gloss(d['en_definition']) for d in group['source_definitions']):
        return True
    # Existing Chinese translations provide a second semantic anchor for long
    # teaching sentences, e.g. abaku's counting-tool explanation vs "abacus".
    zh = teaching.get('zh_definition') or ''
    for value in group['translations']:
        other = value.get('zh_definition') or ''
        if zh and other and (zh.strip('。； ') in other or other.strip('。； ') in zh):
            return True
        pairs = lambda t: set(re.findall(r'(?=([\u4e00-\u9fff]{2}))', t))
        if len(pairs(zh) & pairs(other)) >= 2:
            return True
    return False


def display_layer(entry):
    records, buckets = [], defaultdict(list)
    analyses = entry['lexeme_analyses']
    for analysis in analyses:
        for sense in analysis['senses']:
            records.append((analysis, sense))
    # Preserve unusual flattened-only evidence too, without multiplying the
    # flattened aliases of distinct same-source analysis senses.
    linked = {(a['source'], s.get('pos'), s['en_definition']) for a, s in records}
    for s in entry['senses']:
        if s.get('id') != 'teaching' and (s['source'], s.get('pos'), s['en_definition']) not in linked:
            records.append((None, s))
    for n, (a, s) in enumerate(records):
        buckets[(pos_class(s.get('pos')), normalized_gloss(s['en_definition']))].append(n)
    merged, consumed = [], set()
    for n, (a, s) in enumerate(records):
        if n in consumed:
            continue
        candidates = buckets[(pos_class(s.get('pos')), normalized_gloss(s['en_definition']))]
        source_counts = Counter(records[j][1]['source'] for j in candidates)
        safe = (len(candidates) > 1 and all(v == 1 for v in source_counts.values())
                and all(records[j][0] is not None for j in candidates)
                and compatible_analyses([records[j][0] for j in candidates]))
        members = candidates if safe else [n]
        consumed.update(members)
        group = {'id': f'display-{len(merged) + 1}', 'pos': pos_class(s.get('pos')),
                 'en_definition': s['en_definition'], 'zh_definition': None, 'mt_definition': None,
                 'sources': [], 'analysis_ids': [], 'sense_ids': [],
                 'source_definitions': [], 'translations': [],
                 'definition_origin': 'licensed_source', 'review_status': 'source_attested'}
        for j in members:
            analysis, sense = records[j]
            group['sources'].append(sense['source'])
            if analysis:
                group['analysis_ids'].append(analysis['id'])
            group['sense_ids'].append(sense['id'])
            group['source_definitions'].append({k: sense.get(k) for k in
                ('id', 'pos', 'en_definition', 'source', 'definition_origin')})
            if any(sense.get(k) for k in ('zh_definition', 'mt_definition', 'en_explanation')):
                group['translations'].append({**{k: sense.get(k) for k in
                    ('zh_definition', 'mt_definition', 'en_explanation')},
                    'sense_id': sense['id'], 'provenance': deepcopy(sense.get('translation_provenance'))})
            for k in ('zh_definition', 'mt_definition', 'en_explanation', 'translation_provenance'):
                if sense.get(k) and not group.get(k):
                    group[k] = deepcopy(sense[k])
        group['sources'] = list(dict.fromkeys(group['sources']))
        group['analysis_ids'] = list(dict.fromkeys(group['analysis_ids']))
        merged.append(group)
    teaching, guide = teaching_sense(entry), None
    if teaching:
        matches = [g for g in merged if teaching_matches(teaching, g)]
        if len(merged) == 1 and len(matches) == 1:
            group = merged[0]
            group['teaching'] = deepcopy(teaching)
            group['teaching_mode'] = 'fused'
            # Keep an existing per-sense English refinement ahead of the general
            # teaching English. All original glosses remain in source_definitions.
            group['en_explanation'] = group.get('en_explanation') or teaching['en_definition']
            group['mt_definition'] = group.get('mt_definition') or teaching.get('mt_definition')
            group['zh_definition'] = max([v for v in (group.get('zh_definition'), teaching.get('zh_definition')) if v], key=len)
        elif len(merged) > 1 and any(not g.get('mt_definition') for g in merged):
            positions = {g['pos'] for g in merged}
            roots = {tuple(a.get('roots') or []) for a in analyses if a.get('roots')}
            ambiguous = len(positions) > 1 or len(roots) > 1 or any(
                len({a['id'] for a in analyses if a['source'] == source}) > 1
                for source in {a['source'] for a in analyses})
            if ambiguous:
                # Only a unique semantic match may receive the teaching card.
                # dar's "house" attaches to its noun group, never either verb.
                if len(matches) == 1:
                    matches[0]['teaching'] = deepcopy(teaching)
                    matches[0]['teaching_mode'] = 'bound'
            elif pos_class(teaching.get('pos')) in positions:
                guide = {**deepcopy(teaching), 'analysis_ids': list(dict.fromkeys(
                    aid for g in merged for aid in g['analysis_ids']))}
    return merged, guide


def refresh_display(entry):
    entry['display_senses'], entry['sense_guide'] = display_layer(entry)
