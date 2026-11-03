"""Offline Phase 0 audit. Python standard library only; raw sources are read-only.

Run: python -X utf8 scripts/phase0_inventory_audit.py
The two report names receive identical UTF-8 JSON. No network or database access.
"""
import argparse
import bz2
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import difflib
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import zlib

try:
    from .maltese_alphabet import (
        MALTESE_ALPHABET_30, MALTESE_UI_BUCKETS_30, get_letter_bucket_30,
        get_ui_letter_bucket, normalize_exact_search, normalize_nfc,
        strip_definite_article, tokenize_root_consonants,
    )
except ImportError:
    from maltese_alphabet import (
        MALTESE_ALPHABET_30, MALTESE_UI_BUCKETS_30, get_letter_bucket_30,
        get_ui_letter_bucket, normalize_exact_search, normalize_nfc,
        strip_definite_article, tokenize_root_consonants,
    )

PROJECT = Path(__file__).resolve().parents[1]
CLASSES = ('independent_lemma', 'pure_inflected_wordform',
           'orthographic_or_alt_variant', 'hybrid_lemma_and_wordform',
           'meta_or_affix_or_character')
LEMMA_CLASSES = {'independent_lemma', 'hybrid_lemma_and_wordform'}
EXPECTED_MDX_SHA = '93188e96ae19d540d50f952fd9fe0262900e3cca583145d44340428f3202808d'
REQUESTED_MDX_SHA = '93188e96ae19d540d50f952fd9fe0262900e3cca583145d4434042803202808d'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def coverage(count, total):
    return {'count': count, 'denominator': total,
            'rate': round(count / total, 6) if total else None}


class BinaryReader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError('Truncated MDX structure')
        out = self.data[self.pos:self.pos + size]
        self.pos += size
        return out

    def number(self, fmt='>Q'):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def done(self):
        if self.pos != len(self.data):
            raise ValueError('Unexpected bytes after MDX structure')


def decompress_mdx_block(block):
    """MDX 2 unencrypted blocks: raw (0) or zlib (2); reject LZO explicitly."""
    if len(block) < 8:
        raise ValueError('Truncated MDX compression header')
    kind = struct.unpack('<I', block[:4])[0]
    checksum = struct.unpack('>I', block[4:8])[0]
    if kind == 0:
        decoded = block[8:]
    elif kind == 2:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(block[8:]) + inflater.flush()
        if not inflater.eof or inflater.unused_data:
            raise ValueError('Invalid MDX zlib stream boundary')
    else:
        raise ValueError(f'Unsupported MDX compression {kind}; no third-party decoder used')
    if zlib.adler32(decoded) & 0xffffffff != checksum:
        raise ValueError('MDX Adler-32 mismatch')
    return decoded


def read_mdx(data):
    """Decode and validate this snapshot's UTF-8, unencrypted MDX 2.0 layout."""
    reader = BinaryReader(data)
    header = reader.take(reader.number('>I'))
    if reader.number('<I') != zlib.adler32(header) & 0xffffffff:
        raise ValueError('MDX header checksum mismatch')
    # Writers may terminate the UTF-16 XML with NUL/CR/LF.
    attrs = ET.fromstring(header.decode('utf-16le').strip('\x00\r\n ')).attrib
    if attrs.get('RequiredEngineVersion') != '2.0' or attrs.get('Encrypted', '0') != '0':
        raise ValueError('Only unencrypted MDX 2.0 is supported')
    if attrs.get('Encoding', '').upper().replace('-', '') != 'UTF8':
        raise ValueError('Only UTF-8 MDX keys are supported')
    packed_header = reader.take(40)
    blocks, entries, info_decoded_size, info_size, key_size = struct.unpack('>5Q', packed_header)
    if reader.number('>I') != zlib.adler32(packed_header) & 0xffffffff:
        raise ValueError('MDX key header checksum mismatch')
    info = decompress_mdx_block(reader.take(info_size))
    if len(info) != info_decoded_size:
        raise ValueError('MDX key info size mismatch')
    ir = BinaryReader(info)
    descriptors = []
    for _ in range(blocks):
        count = ir.number()
        for _ in range(2):
            length = ir.number('>H')
            ir.take(length)
            if ir.take(1) != b'\0':
                raise ValueError('MDX key boundary missing terminator')
        descriptors.append((count, ir.number(), ir.number()))
    ir.done()
    if sum(x[1] for x in descriptors) != key_size:
        raise ValueError('MDX key block total mismatch')
    keys = []
    for count, compressed, decompressed in descriptors:
        block = decompress_mdx_block(reader.take(compressed))
        if len(block) != decompressed:
            raise ValueError('MDX key block size mismatch')
        kr = BinaryReader(block)
        for _ in range(count):
            offset = kr.number()
            end = block.find(b'\0', kr.pos)
            if end < 0:
                raise ValueError('Unterminated MDX key')
            key = kr.take(end - kr.pos).decode('utf-8')
            kr.take(1)
            keys.append((offset, key))
        kr.done()
    if len(keys) != entries:
        raise ValueError('MDX key count mismatch')
    nblocks, nentries, table_size, record_size = struct.unpack('>4Q', reader.take(32))
    if nentries != entries or table_size != nblocks * 16:
        raise ValueError('MDX record index mismatch')
    record_descriptors = [struct.unpack('>2Q', reader.take(16)) for _ in range(nblocks)]
    if sum(c for c, d in record_descriptors) != record_size:
        raise ValueError('MDX record block total mismatch')
    records = []
    for compressed, decompressed in record_descriptors:
        decoded = decompress_mdx_block(reader.take(compressed))
        if len(decoded) != decompressed:
            raise ValueError('MDX record block size mismatch')
        records.append(decoded)
    reader.done()
    body = b''.join(records)
    offsets = [offset for offset, key in keys] + [len(body)]
    if offsets[0] != 0 or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Invalid MDX record offsets')
    result = []
    for i, (_, key) in enumerate(keys):
        result.append((key, body[offsets[i]:offsets[i + 1]].decode('utf-8').rstrip('\0')))
    return attrs, result


def lexical_anomaly(word):
    text = normalize_nfc(word)
    if not any(c.isalpha() for c in text):
        return 'no_letters'
    if ';' in text or 'acc. to my' in text.lower():
        return 'editorial_comment_in_headword'
    if any(c.isdigit() for c in text):
        return 'digit_contamination'
    if any(not (c.isalpha() and 'LATIN' in unicodedata.name(c, '') or c in " '-.") for c in text):
        return 'unsupported_or_corrupt_character'
    return None


class EntryHTMLParser(HTMLParser):
    """Build a queryable tree from MDX HTML, including non-XML void elements."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.builder = ET.TreeBuilder()
        self.builder.start('wrapper', {})

    def handle_starttag(self, tag, attrs):
        self.builder.start(tag, dict(attrs))
        if tag in self.VOID:
            self.builder.end(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.builder.end(tag)

    def handle_endtag(self, tag):
        if tag not in self.VOID:
            self.builder.end(tag)

    def handle_data(self, data):
        self.builder.data(data)

    def tree(self):
        self.close()
        self.builder.end('wrapper')
        return self.builder.close()


def audit_gabra(raw):
    with zipfile.ZipFile(raw / 'GabraMalteseDict_MDX_v1.0.zip') as archive:
        members = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
    mdx_name = next(n for n in members if Path(n).name == 'Gabra.mdx')
    mdx = members[mdx_name]
    local = (raw / 'gabra-maltese-dictionary/dictionaries/mdx/Gabra.mdx').read_bytes()
    if mdx != local:
        raise ValueError('Release and repository Gabra.mdx differ')
    attrs, items = read_mdx(mdx)
    records, anomalies, counts = [], [], Counter()
    for key, html in items:
        parser = EntryHTMLParser()
        parser.feed(html)
        doc = parser.tree()
        entries = doc.findall(".//div[@class='gabra-entry']")
        if not entries:
            raise ValueError(f'MDX key without gabra-entry: {key!r}')
        counts[key] = len(entries)
        reason = lexical_anomaly(key)
        if reason:
            anomalies.append({'headword': key, 'reason': reason, 'records': len(entries),
                              'record_ids': [entry.get('id') for entry in entries]})
        for entry in entries:
            def field(name):
                el = entry.find(f".//*[@class='{name}']")
                return normalize_nfc(''.join(el.itertext())) if el is not None else ''
            root = re.sub(r'^(?:root|għerq)\s*:\s*', '', field('root'), flags=re.I)
            glosses = [normalize_nfc(''.join(li.itertext())) for li in entry.findall('.//ol/li')]
            records.append({'word': unicodedata.normalize('NFC', key), 'id': entry.get('id'),
                            'pos': field('pos'), 'phonetic': field('phonetic'), 'root': root,
                            'glosses': [g for g in glosses if g], 'clean': reason is None})
    clean = {r['word'] for r in records if r['clean']}
    roots = {tuple(tokenize_root_consonants(r['root'])) for r in records if r['root']}
    roots.discard(())
    by_word = defaultdict(list)
    for r in records:
        by_word[r['word']].append(r)
    def fields(subset, unique=False):
        denominator = len(clean) if unique else len(subset)
        out = {}
        for field in ('pos', 'phonetic', 'root', 'glosses'):
            hits = len({r['word'] for r in subset if r[field]}) if unique else sum(bool(r[field]) for r in subset)
            out[field] = coverage(hits, denominator)
        return out
    digest = sha256(mdx)
    report = {
        'mdx_format': attrs, 'mdx_bytes': len(mdx), 'mdx_sha256': digest,
        'release_repository_byte_identity': True,
        'matches_repository_validation_sha256': digest == EXPECTED_MDX_SHA,
        'matches_task_supplied_sha256': digest == REQUESTED_MDX_SHA,
        'task_supplied_sha256': REQUESTED_MDX_SHA,
        'checksum_note': 'Task digest has 0 where the locally measured and repository validation digests have f; no data altered.',
        'archive_members': {name: {'bytes': len(blob), 'sha256': sha256(blob)} for name, blob in members.items()},
        'total_records': len(records), 'unique_mdx_keys': len(items),
        'multi_entry_keys': sum(c > 1 for c in counts.values()),
        'anomalies': anomalies, 'excluded_headword_count': len(anomalies),
        'clean_lexical_headwords': len(clean), 'clean_headwords': sorted(clean),
        'anomaly_policy': 'Exclude no-letter keys, digits, editorial semicolon comments, and non-Latin/corrupt characters. Latin foreign spellings, multiword entries and acronyms retained; not manually verified lemmas.',
        'record_coverage': fields(records),
        'unique_clean_headword_coverage': fields([r for r in records if r['clean']], True),
        'pos_distribution_records': dict(sorted(Counter(r['pos'] or '<null>' for r in records).items())),
        'pos_distribution_clean_headwords': dict(sorted(Counter(p for w in clean for p in {r['pos'] or '<null>' for r in by_word[w]}).items())),
        'unique_roots': len(roots),
        'unique_root_radical_count_distribution': dict(sorted(Counter(len(r) for r in roots).items())),
        'record_root_radical_count_distribution': dict(sorted(Counter(len(tokenize_root_consonants(r['root'])) for r in records if r['root']).items())),
        'editorial_correction': {'source_id': '6357914a7f1ba0e22236b65a', 'headword': 'aħwa',
            'observed_in_mdx': any(r['id'] == '6357914a7f1ba0e22236b65a' and r['word'] == 'aħwa' for r in records),
            'status': 'local_packager_correction_not_verified_upstream',
            'evidence': 'gabra-maltese-dictionary/docs/data-notes.md; original whitespace-only heading, gloss brothers'},
        'fields_not_exported': {name: {'value': None, 'status': 'not_present_in_mdx_export'} for name in
            ('verb_form', 'plural_forms', 'hypothetical', 'pending', 'wordforms_4_5_million')},
        'upstream_bson_status': 'Unavailable locally; gabra-api is source code, not a database. Historical redirect to UM homepage recorded in docs/CODEX_HALLUCINATION_AUDIT.md; not rechecked online by this offline run.',
    }
    return report, records


def mt_head_values(row):
    return [str(t.get('args', {}).get('1', '')) for t in row.get('head_templates', []) if t.get('name') == 'mt-head']


def classify_kaikki_row(row):
    if row.get('pos') in ('character', 'suffix', 'prefix'):
        return 'meta_or_affix_or_character'
    heads = mt_head_values(row)
    template_form = any(h.endswith(' form') or h.endswith('-form') for h in heads)
    substantive = form = alt = False
    for sense in row.get('senses', []):
        tags = set(sense.get('tags', []))
        is_form = bool(sense.get('form_of')) or 'form-of' in tags
        is_alt = bool(sense.get('alt_of')) or bool(tags & {'alt-of', 'alternative', 'misspelling'})
        form |= is_form
        alt |= is_alt
        substantive |= bool(sense.get('glosses')) and not (is_form or is_alt or 'no-gloss' in tags)
    if substantive and form:
        return 'hybrid_lemma_and_wordform'
    if substantive:
        return 'independent_lemma'
    if alt or 'misspelling' in heads:
        return 'orthographic_or_alt_variant'
    if template_form or form:
        return 'pure_inflected_wordform'
    # Unresolved entries must not inflate the substantive lemma pool.
    return 'meta_or_affix_or_character'


def category_names(row):
    categories = list(row.get('categories', []))
    for sense in row.get('senses', []):
        categories.extend(sense.get('categories', []))
    return [c if isinstance(c, str) else c.get('name', '') for c in categories]


def canonical_root(value):
    if not isinstance(value, str):
        return None
    if any(c.isalpha() and 'LATIN' not in unicodedata.name(c, '') for c in value):
        return None  # Do not silently transliterate Arabic radicals.
    radicals = tokenize_root_consonants(value)
    if not 2 <= len(radicals) <= 5:
        return None
    if any(c not in set('bċdfġghħjklmnpqrstvw xżz'.replace(' ', '')) | {'għ'} for c in radicals):
        return None
    return '-'.join(radicals)


def extract_roots(row):
    found = defaultdict(set)
    for category in category_names(row):
        match = re.search(r'Maltese terms belonging to the root (.+)', category)
        if match:
            root = canonical_root(match[1])
            if root:
                found[root].add('category')
    for template in row.get('etymology_templates', []):
        name, args = template.get('name'), template.get('args', {})
        if name in ('mt-root', 'ar-root'):
            values = [str(args[k]) for k in ('1', '2', '3', '4', '5') if args.get(k)]
            value = values[0] if len(values) == 1 else '-'.join(v for v in values if v not in ('mt', 'ar'))
            root = canonical_root(value)
            if root:
                found[root].add(name)
    return {root: sorted(paths) for root, paths in sorted(found.items())}


def etymological_stratum(row):
    """Conservative direct-source classifier; no etymology invented from spelling."""
    groups = set()
    codes = {'ar': 'semitic', 'acm': 'semitic', 'sqr': 'semitic', 'jrb': 'semitic',
             'scn': 'romance_sicilian_italian', 'it': 'romance_sicilian_italian', 'en': 'english'}
    for template in row.get('etymology_templates', []):
        name, args = template.get('name', ''), template.get('args', {})
        code = None
        if name in ('bor', 'bor+', 'borrowed', 'inh', 'inh+', 'inherited', 'der', 'der+'):
            code = args.get('2')
        elif name == 'ety' and args.get('2') in (':bor', ':inh', ':der'):
            code = str(args.get('3', '')).split(':')[0]
        if code:
            groups.add(codes.get(code, 'other_or_hybrid'))
            # Later templates often describe the donor's ancestry, not Maltese's donor.
            break
    if not groups:
        text = row.get('etymology_text', '')
        match = re.search(r'(?:Borrowed|Inherited|Derived) from (Siculo-Arabic|Sicilian Arabic|Arabic|Sicilian|Italian|English)', text, re.I)
        if match:
            lang = match[1].lower()
            groups.add('semitic' if 'arabic' in lang else 'english' if lang == 'english' else 'romance_sicilian_italian')
        elif extract_roots(row):
            groups.add('semitic')
    return next(iter(groups)) if len(groups) == 1 else 'other_or_hybrid' if groups else 'unspecified'


def valid_surface(value):
    return (isinstance(value, str) and value not in ('', '-', '?', '—', 'no-table-tags')
            and not any(c in value for c in '#<>[]{}') and lexical_anomaly(value) is None)


def extract_morphology(row):
    verb_forms, number_forms = set(), defaultdict(set)
    labels = category_names(row) + row.get('tags', [])
    for sense in row.get('senses', []):
        labels += sense.get('tags', [])
    for template in row.get('head_templates', []):
        labels.append(template.get('expansion', ''))
        args = template.get('args', {})
        for key in ('form', 'forma', 'class'):
            if args.get(key):
                labels.append('form-' + str(args[key]))
        for key in ('p', 'coll', 'sing'):
            for value in str(args.get(key, '')).split(','):
                value = re.sub(r'<[^>]*>', '', value).strip()
                if valid_surface(value):
                    number_forms[key].add(value)
    for label in labels:
        for match in re.finditer(r'(?:[Ff]orma?[- ]+|[Ff]orm[- ]+)(VIII|VII|III|VI|IV|IX|II|V|X|I)(?![A-Za-z])', label):
            verb_forms.add(match[1])
    for form in row.get('forms', []):
        if valid_surface(form.get('form')) and not set(form.get('tags', [])) & {'table-tags', 'inflection-template'}:
            for tag in set(form.get('tags', [])) & {'plural', 'collective', 'singulative'}:
                number_forms[tag].add(form['form'])
    return {'verb_forms': sorted(verb_forms), 'number_forms': {k: sorted(v) for k, v in sorted(number_forms.items())}}


def read_kaikki(path):
    rows = []
    with path.open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f'Blank JSONL row at {line_number}')
            row = json.loads(line)
            if not isinstance(row.get('word'), str) or not row['word']:
                raise ValueError(f'Missing JSONL word at {line_number}')
            rows.append(row)
    return rows


def audit_kaikki(rows):
    classes, head_counts = Counter(), Counter()
    pos = {c: Counter() for c in CLASSES}
    fields, strata, root_paths, root_status = Counter(), Counter(), Counter(), Counter()
    classified, evidence = [], []
    verb_count = number_count = root_category_present = root_template_present = 0
    for row in rows:
        classification = classify_kaikki_row(row)
        classified.append(classification)
        classes[classification] += 1
        pos[classification][row.get('pos', '<null>')] += 1
        head_counts.update(mt_head_values(row))
        if classification not in LEMMA_CLASSES:
            continue
        roots, stratum = extract_roots(row), etymological_stratum(row)
        morphology = extract_morphology(row)
        ipa = sorted({s['ipa'] for s in row.get('sounds', []) if s.get('ipa')})
        strata[stratum] += 1
        for field in ('etymology_text', 'etymology_templates', 'head_templates', 'forms', 'sounds'):
            fields[field] += bool(row.get(field))
        fields['ipa'] += bool(ipa)
        root_category_present += any('Maltese terms belonging to the root ' in c for c in category_names(row))
        root_template_present += any(t.get('name') in ('mt-root', 'ar-root') for t in row.get('etymology_templates', []))
        for path in {p for paths in roots.values() for p in paths}:
            root_paths[path] += 1
        status = 'attested' if roots else 'not_applicable' if stratum in ('english', 'romance_sicilian_italian') else 'missing_or_unspecified'
        root_status[status] += 1
        verb_count += bool(morphology['verb_forms'])
        number_count += bool(morphology['number_forms'])
        evidence.append({'word': unicodedata.normalize('NFC', row['word']), 'pos': row.get('pos'),
                         'etymology_number': row.get('etymology_number'), 'classification': classification,
                         'roots': roots, 'root_status': status, 'stratum': stratum,
                         'ipa': ipa, 'morphology': morphology,
                         'has_etymology': bool(row.get('etymology_text') or row.get('etymology_templates'))})
    total_lemmas = len(evidence)
    independent_count = classes['independent_lemma']
    # Separately expose the strictly independent subset as requested; hybrids retained in pool.
    independent_evidence = [e for e in evidence if e['classification'] == 'independent_lemma']
    independent_fields = Counter()
    for row, c in zip(rows, classified):
        if c == 'independent_lemma':
            for field in ('etymology_text', 'etymology_templates', 'head_templates', 'forms', 'sounds'):
                independent_fields[field] += bool(row.get(field))
            independent_fields['ipa'] += any(s.get('ipa') for s in row.get('sounds', []))
    report = {
        'total_jsonl_lines': len(rows), 'unique_words': len({r['word'] for r in rows}),
        'unique_word_pos_pairs': len({(r['word'], r.get('pos')) for r in rows}),
        'unique_word_pos_etymology_tuples': len({(r['word'], r.get('pos'), r.get('etymology_number')) for r in rows}),
        'classification': {c: classes[c] for c in CLASSES},
        'classification_policy': 'Sense-level substantive glosses exclude form_of, alt_of, misspelling and no-gloss. mt-head * form plus no-gloss is inflected. Hybrids retained; unresolved/no-gloss non-forms excluded and reported as meta.',
        'unresolved_nonlexical_rows': sum(c == 'meta_or_affix_or_character' and r.get('pos') not in ('character', 'prefix', 'suffix') for r, c in zip(rows, classified)),
        'mt_head_arg1_distribution': dict(sorted(head_counts.items())),
        'pos_distribution_by_class': {c: dict(sorted(v.items())) for c, v in pos.items()},
        'independent_lemma_field_presence': {f: coverage(n, independent_count) for f, n in sorted(independent_fields.items())},
        'lemma_including_hybrids_field_presence': {f: coverage(n, total_lemmas) for f, n in sorted(fields.items())},
        'independent_lemma_root_extraction': coverage(sum(bool(e['roots']) for e in independent_evidence), independent_count),
        'independent_lemma_strata': dict(sorted(Counter(e['stratum'] for e in independent_evidence).items())),
        'root_extraction': {'coverage': coverage(sum(bool(e['roots']) for e in evidence), total_lemmas),
            'category_candidate_rows': root_category_present, 'template_candidate_rows': root_template_present,
            'successful_rows_by_path': dict(sorted(root_paths.items())),
            'status': dict(sorted(root_status.items())),
            'note': 'Only explicit Latin-script radicals; Arabic-script ar-root needs evidenced transliteration and is not guessed. Root attestation and donor stratum are separate axes.'},
        'strata_including_hybrids': dict(sorted(strata.items())),
        'morphology_extraction': {'verb_form_rows': coverage(verb_count, total_lemmas),
                                 'number_form_rows': coverage(number_count, total_lemmas),
                                 'evidence': evidence},
    }
    return report, classified, evidence


def read_wikipron(path):
    words = defaultdict(set)
    total = 0
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            word, ipa = line.rstrip('\r\n').split('\t', 1)
            words[normalize_exact_search(word)].add(ipa)
            total += 1
    return total, words


def read_camilleri(directory):
    mapping, empty, files, forms = defaultdict(set), [], [], 0
    for path in sorted(directory.rglob('*.csv')):
        relative = path.relative_to(directory).as_posix()
        files.append(relative)
        count = 0
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                value = (row.get('Surface form') or '').strip()
                if valid_surface(value):
                    mapping[normalize_exact_search(value)].add(normalize_exact_search(path.stem))
                    count += 1
        forms += count
        if not count:
            empty.append(relative)
    lemmas = {normalize_exact_search(Path(p).stem) for p in files}
    return {'csv_files': len(files), 'file_list': files, 'non_empty_csv_files': len(files) - len(empty),
            'empty_csv_files': empty, 'total_non_null_surface_forms': forms,
            'unique_surface_forms': len(mapping), 'unique_verb_lemmas': len(lemmas),
            'scope_note': 'Recursive CSV count includes data/new revisions; distinct lemma stems counted separately. Null - cells excluded.'}, mapping, lemmas


def reconcile_sets(gabra, lemma, all_words, form_variant):
    both = gabra & lemma
    only_forms = (gabra - lemma) & form_variant
    absent = gabra - all_words
    other = gabra - both - only_forms - absent
    ka_only = lemma - gabra
    return {'gabra_and_kaikki_independent_lemma': len(both),
            'gabra_kaikki_only_wordform_or_variant': len(only_forms),
            'gabra_absent_from_kaikki': len(absent),
            'gabra_kaikki_only_meta_or_other': len(other),
            'kaikki_independent_lemma_absent_from_gabra': len(ka_only),
            'combined_master_lemma_count': len(gabra | lemma),
            'headword_partitions': {'both': sorted(both), 'gabra_only_wordform_or_variant': sorted(only_forms),
                'gabra_absent': sorted(absent), 'gabra_only_meta_or_other': sorted(other), 'kaikki_only_lemma': sorted(ka_only)}}


def cross_reconcile(gabra_records, rows, classified, evidence, wikipron):
    gabra = {r['word'] for r in gabra_records if r['clean']}
    lemma = {e['word'] for e in evidence if lexical_anomaly(e['word']) is None}
    all_words = {unicodedata.normalize('NFC', r['word']) for r in rows}
    form_variant = {unicodedata.normalize('NFC', r['word']) for r, c in zip(rows, classified)
                    if c in ('pure_inflected_wordform', 'orthographic_or_alt_variant')}
    exact = reconcile_sets(gabra, lemma, all_words, form_variant)
    norm = lambda values: {normalize_exact_search(w) for w in values}
    normalized = reconcile_sets(norm(gabra), norm(lemma), norm(all_words), norm(form_variant))
    master = gabra | lemma
    both_exact = gabra & lemma
    gb, kk = defaultdict(list), defaultdict(list)
    for r in gabra_records:
        if r['clean']:
            gb[normalize_exact_search(r['word'])].append(r)
    for e in evidence:
        kk[normalize_exact_search(e['word'])].append(e)
    details, letters, buckets, statuses, strata_counts = [], Counter(), Counter(), Counter(), Counter()
    roots_count = ipa_count = loan_count = ie_count = tier1 = 0
    for word in sorted(master):
        key = normalize_exact_search(word)
        gr, kr = gb[key], kk[key]
        roots = sorted({root for e in kr for root in e['roots']} |
                       {root for r in gr if r['root'] for root in [canonical_root(r['root'])] if root})
        strata = sorted({e['stratum'] for e in kr})
        loan = bool(set(strata) & {'english', 'romance_sicilian_italian'})
        ipa_sources = [name for name, exists in (
            ('gabra', any(r['phonetic'] for r in gr)), ('kaikki', any(e['ipa'] for e in kr)),
            ('wikipron', bool(wikipron.get(key)))) if exists]
        status = 'attested' if roots else 'not_applicable' if loan and all(s in ('english', 'romance_sicilian_italian') for s in strata) else 'missing_or_unspecified'
        roots_count += bool(roots)
        ipa_count += bool(ipa_sources)
        loan_count += loan
        statuses[status] += 1
        strata_counts.update(strata or ['unspecified'])
        ui = get_ui_letter_bucket(word)
        letters[get_letter_bucket_30(word)] += 1
        buckets[ui['bucket']] += 1
        ie_count += ui['sub_prefix'] == 'ie'
        morph = any(e['morphology']['verb_forms'] or e['morphology']['number_forms'] for e in kr)
        complete = word in both_exact and bool(ipa_sources) and morph and any(e['has_etymology'] for e in kr)
        tier1 += complete
        details.append({'word': word, 'sources_exact': [s for s, present in (('gabra', word in gabra), ('kaikki_lemma', word in lemma)) if present],
                        'roots_normalized_join': roots, 'root_status': status, 'strata': strata or ['unspecified'],
                        'ipa_sources_normalized_join': ipa_sources, 'tier1_enrichment_candidate': complete})
    return {
        'exact_nfc': exact, 'normalized': normalized,
        'normalization_policy': 'NFC only for exact; lowercase, apostrophe/dash canonicalization and whitespace collapse for normalized. Accents and Maltese distinct letters retained; no ASCII conflation.',
        'kaikki_excluded_noise_lemma_words': sorted({e['word'] for e in evidence} - lemma),
        'master_inventory': {'total_unique_lemma_headwords': len(master),
            'root_coverage': coverage(roots_count, len(master)), 'root_status': dict(sorted(statuses.items())),
            'attested_loanword_ratio': coverage(loan_count, len(master)),
            'loanword_ratio_note': 'Evidence-based lower bound, not a population estimate; unclassified Gabra-only words remain unknown. A lexical root can coexist with a loanword stratum.',
            'stratum_headword_counts_nonexclusive': dict(sorted(strata_counts.items())),
            'ipa_coverage': coverage(ipa_count, len(master)),
            'letter_distribution_30_plus_hash': {l: letters[l] for l in MALTESE_ALPHABET_30 + ('#',)},
            'ui_bucket_distribution': {l: buckets[l] for l in MALTESE_UI_BUCKETS_30}, 'ie_sub_prefix_count': ie_count,
            'enrichment_join_policy': 'Coverage joins use exact-search normalization, retaining case-distinct spellings in exact master count. This can share evidence across capitalization variants; not sense disambiguation.',
            'lemmas': details},
        'capacity_recommendation': {
            'tier1': {'count': tier1, 'label': 'Cross-source enrichment candidates',
                'criteria': 'Exact headword in both pools plus IPA, some attested morphology and etymology; not full morphology or editorially verified content.',
                'full_morphology_verified_count': None, 'status': 'manual_linguistic_review_required'},
            'tier2': {'count': len(master), 'label': 'Full deduplicated attested candidate lemma pool',
                'status': 'not_a_promised_publication_size'},
            'source_independence': 'Kaikki and WikiPron share Wiktionary origin. Source presence is not editorial verification.'},
    }, master


def build_lookup(gabra_records, rows, classified, camilleri):
    lookup = defaultdict(set)
    for r in gabra_records:
        if r['clean']:
            key = normalize_exact_search(r['word'])
            lookup[key].add(key)
    for surface, candidates in camilleri.items():
        lookup[surface].update(candidates)
    unresolved_forms = 0
    for row, classification in zip(rows, classified):
        if classification == 'meta_or_affix_or_character':
            continue
        word = normalize_exact_search(row['word'])
        targets = set()
        for sense in row.get('senses', []):
            for field in ('form_of', 'alt_of'):
                targets.update(normalize_exact_search(x['word']) for x in sense.get(field, []) if valid_surface(x.get('word')))
        for template in row.get('head_templates', []):
            args = template.get('args', {})
            if template.get('name') == 'mt-head' and (str(args.get('1', '')).endswith(' form') or args.get('1') == 'misspelling'):
                if valid_surface(args.get('2')):
                    targets.add(normalize_exact_search(args['2']))
        if classification in LEMMA_CLASSES:
            targets.add(word)
        if not targets:
            unresolved_forms += 1
        if valid_surface(row['word']):
            lookup[word].update(targets)
        for form in row.get('forms', []):
            if valid_surface(form.get('form')) and not set(form.get('tags', [])) & {'table-tags', 'inflection-template'}:
                lookup[normalize_exact_search(form['form'])].update(targets)
    return lookup, unresolved_forms


def lookup_candidates(word, lookup):
    """Union original and one syntactic prefix removal; no invented stems."""
    key = normalize_exact_search(word)
    keys = {key}
    stripped, prefix = strip_definite_article(key, include_fused_prepositions=True)
    if prefix:
        keys.add(stripped)
    for prefix in ("m'", "x'", "b'", "f'", "t'", "l'"):
        if key.startswith(prefix) and len(key) > len(prefix):
            keys.add(key[len(prefix):])
    return set().union(*(lookup.get(k, set()) for k in keys))


def read_conllu(path):
    sentences = 0
    tokens, syntactic_words = [], []
    missing_lemma = missing_features = 0
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if line.startswith('# sent_id'):
                sentences += 1
            if line.startswith('#') or not line.strip():
                continue
            cols = line.rstrip('\r\n').split('\t')
            if len(cols) != 10:
                raise ValueError(f'Invalid CoNLL-U row in {path}')
            if '.' in cols[0]:
                continue
            if '-' in cols[0]:
                tokens.append(cols[1])
                continue
            syntactic_words.append(cols[1])
            missing_lemma += cols[2] == '_'
            missing_features += cols[5] == '_'
            # Surface tokens exclude component rows covered by a multiword token.
    # Derive surface token list using explicit MWT integer spans.
    tokens = []
    covered_until = 0
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line:
            covered_until = 0
        elif not line.startswith('#'):
            cols = line.split('\t')
            if '-' in cols[0]:
                covered_until = int(cols[0].split('-')[1])
                tokens.append(cols[1])
            elif cols[0].isdigit() and int(cols[0]) > covered_until:
                tokens.append(cols[1])
    return {'sentences': sentences, 'surface_tokens': len(tokens), 'syntactic_words': len(syntactic_words),
            'missing_lemma': missing_lemma, 'missing_features': missing_features}, tokens, syntactic_words


def evaluate_coverage(tokens, lookup):
    counts = Counter(normalize_exact_search(w) for w in tokens)
    candidates = {w: lookup_candidates(w, lookup) for w in counts}
    matched = sum(n for w, n in counts.items() if candidates[w])
    ambiguous = sum(n for w, n in counts.items() if len(candidates[w]) > 1)
    return {'tokens': len(tokens), 'unique_word_types': len(counts),
            'token_coverage': coverage(matched, len(tokens)),
            'unique_word_type_coverage': coverage(sum(bool(c) for c in candidates.values()), len(counts)),
            'token_oov_rate': coverage(len(tokens) - matched, len(tokens)),
            'unique_word_type_oov_rate': coverage(sum(not c for c in candidates.values()), len(counts)),
            'homograph_ambiguity_all_tokens': coverage(ambiguous, len(tokens)),
            'homograph_ambiguity_matched_tokens': coverage(ambiguous, matched),
            'homograph_ambiguity_types': coverage(sum(len(c) > 1 for c in candidates.values()), len(counts)),
            'oov_top_50': [{'word': w, 'count': n} for w, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])) if not candidates[w]][:50],
            'ambiguity_examples': [{'word': w, 'candidates': sorted(c)} for w, c in sorted(candidates.items()) if len(c) > 1][:30],
            'interpretation': 'Dictionary lookup coverage, not lemma accuracy. Same-spelling POS/etymology homographs collapse; ambiguity is a lower bound. No gold lemmas/features; disambiguation accuracy unavailable.'}


def normalize_ipa(text):
    text = unicodedata.normalize('NFC', text).lower()
    for a, b in (('t͡ʃ', 'tʃ'), ('d͡ʒ', 'dʒ'), ('t͡s', 'ts'), ('ʧ', 'tʃ'), ('ʤ', 'dʒ'), ('ʦ', 'ts')):
        text = text.replace(a, b)
    text = text.translate(str.maketrans('ɪɛɔʊɐəɑħɡ', 'ieouaaahg'))
    return ''.join(c for c in text if c not in '/[] .ˈˌː:ˑ\t\n\r')


def benchmark_g2p(raw, gabra_records, rows, wikipron, sample_size=500):
    path = raw / 'MASRI/masri/transcribe/g2p/maltese_g2p.py'
    spec = importlib.util.spec_from_file_location('phase0_local_masri_g2p', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Direct file load avoids package/num2words dependencies.
    gold = defaultdict(set)
    gabra_words = {normalize_exact_search(r['word']) for r in gabra_records if r['clean'] and r['phonetic']}
    for word, values in wikipron.items():
        gold[word].update(values)
    for row in rows:
        gold[normalize_exact_search(row['word'])].update(s['ipa'] for s in row.get('sounds', []) if s.get('ipa'))
    eligible = sorted(w for w in gabra_words & gold.keys() if gold[w] and ' ' not in w)
    sample = sorted(eligible, key=lambda w: (sha256(w.encode('utf-8')), w))[:sample_size]
    exact = normalized = 0
    divergences, results = Counter(), []
    for word in sample:
        try:
            predicted = module.g2p_cw_rules(word)
            error = None
        except Exception as exc:
            predicted, error = '', type(exc).__name__ + ': ' + str(exc)
        references = sorted(gold[word])
        # Remove presentation delimiters/TSV segment spaces for the exact-symbol comparison.
        surface = lambda value: re.sub(r'[\s/\[\]]', '', value)
        em = not error and any(surface(predicted) == surface(g) for g in references)
        nm = not error and normalize_ipa(predicted) in {normalize_ipa(g) for g in references}
        exact += em
        normalized += nm
        if not nm and not error:
            p = normalize_ipa(predicted)
            g = min((normalize_ipa(g) for g in references), key=lambda g: (-difflib.SequenceMatcher(None, p, g).ratio(), g))
            for op, a, b, c, d in difflib.SequenceMatcher(None, p, g).get_opcodes():
                if op != 'equal':
                    divergences[p[a:b] + ' → ' + g[c:d]] += 1
        results.append({'word': word, 'predicted': predicted, 'reference_ipa': references,
                        'exact_match': em, 'normalized_match': nm, 'error': error})
    return {'source': path.relative_to(raw).as_posix(), 'source_sha256': sha256(path.read_bytes()),
            'function': 'g2p_cw_rules', 'license': 'MASRI Non-Commercial License',
            'use': 'Local evaluation only; NC implementation is not copied into production or used to populate master IPA.',
            'sample_method': 'First N by SHA-256(word UTF-8), tie word; Gabra phonetic present AND WikiPron/Kaikki IPA; single-word headwords.',
            'eligible_words': len(eligible), 'sample_size': len(sample),
            'exact_match': coverage(exact, len(sample)), 'normalized_ipa_match': coverage(normalized, len(sample)),
            'errors': sum(bool(r['error']) for r in results),
            'normalization': 'Exact removes wrappers and segment whitespace only; tolerant folds ɪ/i, ɛ/e, ɔ/o, ʊ/u, ɐ/ə/ɑ/a, ħ/h, ɡ/g, affricate ligatures/ties, stress, syllable and length marks. This lossy equivalence is not phonetic accuracy.',
            'reference_limit': 'WikiPron and Kaikki are related Wiktionary snapshots; any listed pronunciation may match. Gabra phonetic selects sample but is not scored as a third independent gold standard.',
            'common_normalized_divergences': [{'predicted_to_reference': k, 'count': n} for k, n in divergences.most_common(25)],
            'sample_results': results}


def source_license(name):
    if name == 'gabra-maltese-dictionary' or name.startswith('Gabra'):
        return 'Data: CC BY 3.0 per bundled attribution/MDX header; packaging code: GPL-3.0', 'Bundled snapshot license/date not independently certified; current upstream CC BY 4.0 does not silently relicense this artifact.'
    if name == 'gabra-api':
        return 'MIT (repository code); database license separate', 'Source/schema only, no upstream BSON archive locally. Historical UM redirect: docs/CODEX_HALLUCINATION_AUDIT.md.'
    if name == 'MASRI':
        return 'Non-Commercial License (bundled PDF)', 'Restricted NC source; benchmark only; no production code or generated IPA imported.'
    if name == 'maltese-verb-inflections':
        return 'MIT (bundled LICENSE)', 'Small manually checked CSV suite with empty files; not 186 full TSV paradigms.'
    if name.startswith('kaikki') or name.startswith('mlt_latn'):
        return 'CC BY-SA 4.0 (Wiktionary data; project documented attribution)', 'Kaikki and WikiPron share Wiktionary origin; not independent pronunciation evidence. WikiPron code Apache-2.0 is distinct.'
    if name.startswith('mt_mudt'):
        return 'CC BY-SA 4.0 (project documented UD attribution)', 'Lemmas: not available; Features: not available; verified from CoNLL-U columns.'
    if name.startswith('mlt_sentences'):
        return 'Tatoeba default CC BY 2.0 FR / possible CC0; per-sentence license not included', 'Export has no per-sentence license manifest; redistribution needs attribution/manifest verification. Not necessarily parallel English pairs.'
    return 'Not established from local license manifest', 'Reference artifact only; no redistribution permission inferred.'


def inventory_sources(raw):
    inventory = []
    for path in sorted(raw.iterdir()):
        license_name, notes = source_license(path.name)
        item = {'path': path.relative_to(raw).as_posix(), 'license': license_name, 'notes': notes}
        if path.is_file():
            blob = path.read_bytes()
            item.update(kind='file', bytes=len(blob), sha256=sha256(blob))
        elif path.is_dir():
            manifest = []
            digest = hashlib.sha256()
            for file in sorted(p for p in path.rglob('*') if p.is_file() and '.git' not in p.relative_to(path).parts and '__pycache__' not in p.parts):
                blob = file.read_bytes()
                rel = file.relative_to(path).as_posix()
                file_hash = sha256(blob)
                manifest.append({'path': rel, 'bytes': len(blob), 'sha256': file_hash})
                digest.update((rel + '\0' + str(len(blob)) + '\0' + file_hash + '\n').encode('utf-8'))
            git = subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=False)
            item.update(kind='repository' if (path / '.git').exists() else 'directory',
                        bytes=sum(f['bytes'] for f in manifest), sha256=digest.hexdigest(),
                        git_head=git.stdout.strip() if git.returncode == 0 else None,
                        checksum_method='SHA256 of sorted UTF-8 path NUL decimal-size NUL file-SHA256 LF; excludes .git and __pycache__; bytes=sum manifest payloads', files=manifest)
        inventory.append(item)
    return inventory


def generate_report(raw, sample_size=500):
    raw = Path(raw)
    gabra_report, gabra_records = audit_gabra(raw)
    rows = read_kaikki(raw / 'kaikki.org-dictionary-Maltese.jsonl')
    kaikki_report, classified, evidence = audit_kaikki(rows)
    wiki_total, wiki = read_wikipron(raw / 'mlt_latn_broad.tsv')
    filtered_total, filtered = read_wikipron(raw / 'mlt_latn_broad_filtered.tsv')
    cam_report, cam_map, cam_lemmas = read_camilleri(raw / 'maltese-verb-inflections')
    reconciliation, master = cross_reconcile(gabra_records, rows, classified, evidence, wiki)
    gb_ipa = {normalize_exact_search(r['word']) for r in gabra_records if r['phonetic'] and r['clean']}
    kk_ipa = {normalize_exact_search(r['word']) for r in rows if any(s.get('ipa') for s in r.get('sounds', []))}
    gb_words = {normalize_exact_search(r['word']) for r in gabra_records if r['clean']}
    kk_lemmas = {normalize_exact_search(e['word']) for e in evidence}
    cam_report['lemma_overlap'] = {'gabra': len(cam_lemmas & gb_words), 'kaikki_lemma': len(cam_lemmas & kk_lemmas),
                                  'both': len(cam_lemmas & gb_words & kk_lemmas)}
    lookup, unresolved = build_lookup(gabra_records, rows, classified, cam_map)
    ud_parts, ud_tokens, ud_words = {}, [], []
    for split in ('train', 'dev', 'test'):
        stats, tokens, words = read_conllu(raw / f'mt_mudt-ud-{split}.conllu')
        ud_parts[split] = stats
        ud_tokens.extend(tokens)
        ud_words.extend(words)
    lexical_tokens = [t for t in ud_tokens if any(c.isalpha() for c in t)]
    with bz2.open(raw / 'mlt_sentences.tsv.bz2', 'rt', encoding='utf-8') as stream:
        sentences = [row for row in csv.reader(stream, delimiter='\t') if len(row) >= 3 and row[1] == 'mlt']
    sentence_tokens = [w for row in sentences for w in re.findall(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", row[2], flags=re.UNICODE)]
    master_lookup = {normalize_exact_search(w): {normalize_exact_search(w)} for w in master}
    g2p = benchmark_g2p(raw, gabra_records, rows, wiki, sample_size)
    source_inventory = inventory_sources(raw)
    summary = {'gabra_clean_lexical_headwords': gabra_report['clean_lexical_headwords'],
               'kaikki_row_classification': kaikki_report['classification'],
               'exact_master_lemma_count': len(master),
               'normalized_master_lemma_count': reconciliation['normalized']['combined_master_lemma_count'],
               'master_root_coverage': reconciliation['master_inventory']['root_coverage'],
               'master_ipa_coverage': reconciliation['master_inventory']['ipa_coverage'],
               'g2p_normalized_match': g2p['normalized_ipa_match'],
               'publication_size': None,
               'limitations': ['MDX lacks verb forms, plural paradigms, status flags and upstream 4.5M wordforms.',
                    'Kaikki mt-head no-gloss forms excluded from lemma pool; hybrids retained.',
                    'No gold UD lemmas: lookup coverage is not lemmatization accuracy.',
                    'Gabra digest differs from task text; observed digest agrees with bundled validation.',
                    'Loanword strata and root extraction are conservative evidence-based candidates, not editorial verification.']}
    return {
        'metadata': {'generated_at': datetime.now(timezone.utc).isoformat(),
            'script_path': 'scripts/phase0_inventory_audit.py', 'schema_version': '1.0.0',
            'raw_directory': raw.resolve().as_posix(), 'execution': 'offline_stdlib_only',
            'executive_summary': summary,
            'external_reference_status': {'dizzjunarju_mt': {'public_entries_historically_verified': 81,
                'evidence': 'docs/PROJECT_HANDOFF.md section 1 and docs/CODEX_HALLUCINATION_AUDIT.md',
                'status': 'historical_project_verification_not_live_measurement', 'bulk_scraping': 'excluded'},
                'dms200_reference': 'https://kunsilltalmalti.gov.mt/wp-content/uploads/2022/12/2009-10-14-MSA-Specification-for-Maltese-locale-abbozz-finali-1.pdf'}},
        'source_files_inventory': source_inventory, 'gabra_audit': gabra_report,
        'kaikki_audit': kaikki_report, 'cross_source_reconciliation': reconciliation,
        'auxiliary_sources_and_benchmarks': {
            'wikipron': {'broad': {'total_entries': wiki_total, 'unique_words': len(wiki),
                    'overlap_kaikki_ipa_words': len(wiki.keys() & kk_ipa), 'overlap_gabra_phonetic_words': len(wiki.keys() & gb_ipa)},
                'filtered': {'total_entries': filtered_total, 'unique_words': len(filtered),
                    'overlap_kaikki_ipa_words': len(filtered.keys() & kk_ipa), 'overlap_gabra_phonetic_words': len(filtered.keys() & gb_ipa)},
                'independence': 'Both WikiPron and Kaikki extracted from Wiktionary; normalization is exact-search, not ASCII.'},
            'camilleri': cam_report, 'masri_g2p': g2p,
            'ud_maltese_mudt': {'splits': ud_parts,
                'sentences': sum(s['sentences'] for s in ud_parts.values()),
                'tokens': len(ud_tokens), 'syntactic_words': len(ud_words),
                'lemma_missing': coverage(sum(s['missing_lemma'] for s in ud_parts.values()), len(ud_words)),
                'features_missing': coverage(sum(s['missing_features'] for s in ud_parts.values()), len(ud_words)),
                'lookup_surface_forms': len(lookup), 'wordform_rows_without_resolved_lemma': unresolved,
                'all_surface_tokens_evaluation': evaluate_coverage(ud_tokens, lookup),
                'lexical_surface_tokens_evaluation': evaluate_coverage(lexical_tokens, lookup),
                'syntactic_words_evaluation': evaluate_coverage(ud_words, lookup),
                'evaluation_limit': 'All-token denominator includes punctuation/numbers; lexical denominator requires an alphabetic character. MWT surface tokens and integer-ID syntactic words reported separately; no supervised accuracy claim.'},
            'tatoeba': {'maltese_sentences': len(sentences), 'tokenization': 'Unicode letter words with internal apostrophes/hyphens',
                'master_lemma_overlap': evaluate_coverage(sentence_tokens, master_lookup)}},
    }


def write_reports(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + '\n').encode('utf-8')
    for name in ('lexeme_inventory_report.json', 'phase0_source_inventory.json'):
        temporary = output / (name + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(output / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, default=PROJECT / 'data/raw')
    parser.add_argument('--output-dir', type=Path, default=PROJECT / 'data/audit')
    parser.add_argument('--g2p-sample-size', type=int, default=500)
    args = parser.parse_args()
    if args.g2p_sample_size < 1:
        parser.error('--g2p-sample-size must be positive')
    report = generate_report(args.raw_dir, args.g2p_sample_size)
    write_reports(report, args.output_dir)
    print(json.dumps(report['metadata']['executive_summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
