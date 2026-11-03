"""Isolated audit helper tests and read-only validation of Phase 0 reports."""
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import struct
import unittest
import zlib

from scripts.maltese_alphabet import (
    MALTESE_ALPHABET_30, MALTESE_UI_BUCKETS_30, get_letter_bucket_30,
    get_ui_letter_bucket, normalize_exact_search,
)
from scripts.phase0_inventory_audit import (
    CLASSES, EntryHTMLParser, canonical_root, classify_kaikki_row,
    decompress_mdx_block, etymological_stratum, extract_morphology,
    extract_roots, lexical_anomaly, normalize_ipa,
)


class MDXBlockTests(unittest.TestCase):
    @staticmethod
    def block(payload, kind=0):
        encoded = zlib.compress(payload) if kind == 2 else payload
        return struct.pack('<I', kind) + struct.pack('>I', zlib.adler32(payload)) + encoded

    def test_raw_and_zlib_blocks(self):
        for payload in (b'', 'Għajn\x00Ġabra'.encode('utf-8')):
            for kind in (0, 2):
                with self.subTest(payload=payload, kind=kind):
                    self.assertEqual(decompress_mdx_block(self.block(payload, kind)), payload)

    def test_truncated_header(self):
        for size in range(8):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, 'Truncated'):
                decompress_mdx_block(b'\0' * size)

    def test_unsupported_compression(self):
        for kind in (1, 3):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Unsupported'):
                decompress_mdx_block(self.block(b'data', kind))

    def test_checksum_mismatch(self):
        for kind in (0, 2):
            block = self.block(b'data', kind)
            corrupted = block[:4] + struct.pack('>I', 0) + block[8:]
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Adler-32'):
                decompress_mdx_block(corrupted)

    def test_zlib_stream_boundaries(self):
        block = self.block(b'data', 2)
        for malformed in (block[:-1], block + b'extra', block + zlib.compress(b'second')):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, 'boundary'):
                decompress_mdx_block(malformed)

    def test_corrupt_zlib_payload(self):
        with self.assertRaises(zlib.error):
            decompress_mdx_block(self.block(b'data', 2)[:8] + b'not zlib')


class LexicalAndHTMLTests(unittest.TestCase):
    def test_clean_headwords(self):
        for word in ('għajn', 'Ġabra', "m’għandix", 'il–ktieb', 'kafè', 'kelma oħra', 'Dr.'):
            with self.subTest(word=word):
                self.assertIsNone(lexical_anomaly(word))

    def test_lexical_anomalies(self):
        cases = {'': 'no_letters', '123': 'no_letters', '#': 'no_letters',
                 'kelma; note': 'editorial_comment_in_headword',
                 'kelma ACC. TO MY notes': 'editorial_comment_in_headword',
                 'kelma2': 'digit_contamination', 'kelma☃': 'unsupported_or_corrupt_character',
                 'كلمة': 'unsupported_or_corrupt_character'}
        for word, reason in cases.items():
            with self.subTest(word=word):
                self.assertEqual(lexical_anomaly(word), reason)

    def test_html_tree_entities_void_and_self_closing_tags(self):
        parser = EntryHTMLParser()
        parser.feed('<div id="entry"><span class="word">Għajn &amp; ')
        parser.feed('ilma</span><br>text<br/><img src="x"><hr></hr><b/></div>')
        tree = parser.tree()
        self.assertEqual(tree.tag, 'wrapper')
        entry = tree.find('./div')
        self.assertEqual(entry.get('id'), 'entry')
        self.assertEqual(entry.find('./span').get('class'), 'word')
        self.assertEqual(entry.find('./span').text, 'Għajn & ilma')
        self.assertEqual([child.tag for child in entry], ['span', 'br', 'br', 'img', 'hr', 'b'])
        self.assertEqual(''.join(entry.itertext()), 'Għajn & ilmatext')
        self.assertEqual(entry.find('./img').get('src'), 'x')

    def test_html_empty_fragment(self):
        self.assertEqual(list(EntryHTMLParser().tree()), [])


class KaikkiClassificationTests(unittest.TestCase):
    def test_mt_head_form_with_no_gloss(self):
        row = {'pos': 'verb', 'head_templates': [{'name': 'mt-head', 'args': {'1': 'verb form'}}],
               'senses': [{'tags': ['no-gloss']}]}
        self.assertEqual(classify_kaikki_row(row), 'pure_inflected_wordform')
        row['senses'][0]['glosses'] = ['placeholder']
        self.assertEqual(classify_kaikki_row(row), 'pure_inflected_wordform')

    def test_substantive_sense(self):
        row = {'pos': 'noun', 'senses': [{'glosses': ['book']}]}
        self.assertEqual(classify_kaikki_row(row), 'independent_lemma')

    def test_hybrid_and_pure_form_by_tags_or_targets(self):
        for form_sense in ({'tags': ['form-of'], 'glosses': ['plural of book']},
                           {'form_of': [{'word': 'ktieb'}], 'glosses': ['plural of book']}):
            with self.subTest(form_sense=form_sense):
                self.assertEqual(classify_kaikki_row({'senses': [form_sense]}), 'pure_inflected_wordform')
                self.assertEqual(classify_kaikki_row({'senses': [form_sense, {'glosses': ['a substantive meaning']}]}),
                                 'hybrid_lemma_and_wordform')

    def test_alternative_variants(self):
        for sense in ({'tags': ['alt-of'], 'glosses': ['alternative spelling']},
                      {'alt_of': [{'word': 'għajn'}]}, {'tags': ['misspelling']}):
            with self.subTest(sense=sense):
                self.assertEqual(classify_kaikki_row({'senses': [sense]}), 'orthographic_or_alt_variant')
        self.assertEqual(classify_kaikki_row({'head_templates': [{'name': 'mt-head', 'args': {'1': 'misspelling'}}]}),
                         'orthographic_or_alt_variant')

    def test_meta_and_unresolved_entries(self):
        for pos in ('character', 'suffix', 'prefix'):
            with self.subTest(pos=pos):
                self.assertEqual(classify_kaikki_row({'pos': pos, 'senses': [{'glosses': ['meaning']}]}),
                                 'meta_or_affix_or_character')
        for row in ({}, {'senses': [{'tags': ['no-gloss'], 'glosses': ['placeholder']}]}):
            with self.subTest(row=row):
                self.assertEqual(classify_kaikki_row(row), 'meta_or_affix_or_character')


class RootAndEtymologyTests(unittest.TestCase):
    def test_canonical_roots_preserve_digraphs(self):
        for value, expected in [('GĦ–L–M', 'għ-l-m'), ('b-għ-d', 'b-għ-d'),
                                ('għ-r-għ-x', 'għ-r-għ-x'), ('t-r-ġ-m', 't-r-ġ-m'),
                                ('K T B', 'k-t-b')]:
            with self.subTest(value=value):
                self.assertEqual(canonical_root(value), expected)

    def test_invalid_roots_are_not_invented_or_transliterated(self):
        for value in (None, 12, '', 'a-e-i', 'b', 'b-c-d', 'b-y-d', 'b-d-f-g-h-j', 'ك-ت-ب'):
            with self.subTest(value=value):
                self.assertIsNone(canonical_root(value))

    def test_root_evidence_paths_are_merged(self):
        row = {'categories': ['Maltese terms belonging to the root għ-l-m'],
               'senses': [{'categories': [{'name': 'Maltese terms belonging to the root b-għ-d'}]}],
               'etymology_templates': [
                   {'name': 'mt-root', 'args': {'1': 'għ', '2': 'l', '3': 'm'}},
                   {'name': 'mt-root', 'args': {'1': 'għ-l-m'}},
                   {'name': 'ar-root', 'args': {'1': 'mt', '2': 'b', '3': 'għ', '4': 'd'}},
                   {'name': 'ar-root', 'args': {'1': 'ك-ت-ب'}},
               ]}
        self.assertEqual(extract_roots(row), {'b-għ-d': ['ar-root', 'category'],
                                             'għ-l-m': ['category', 'mt-root']})
        self.assertEqual(extract_roots({'word': 'kiteb'}), {})

    def test_etymology_direct_donor_codes(self):
        for code, expected in [('ar', 'semitic'), ('scn', 'romance_sicilian_italian'),
                               ('it', 'romance_sicilian_italian'), ('en', 'english'),
                               ('fr', 'other_or_hybrid')]:
            with self.subTest(code=code):
                row = {'etymology_templates': [{'name': 'bor', 'args': {'1': 'mt', '2': code}}]}
                self.assertEqual(etymological_stratum(row), expected)

    def test_etymology_uses_direct_donor_before_ancestry(self):
        row = {'etymology_templates': [{'name': 'bor', 'args': {'1': 'mt', '2': 'it'}},
                                      {'name': 'inh', 'args': {'1': 'it', '2': 'ar'}}]}
        self.assertEqual(etymological_stratum(row), 'romance_sicilian_italian')
        row['etymology_templates'] = [{'name': 'ety', 'args': {'2': ':bor', '3': 'en:word'}}]
        self.assertEqual(etymological_stratum(row), 'english')

    def test_etymology_text_and_attested_root_fallback(self):
        for text, expected in [('Inherited from Siculo-Arabic', 'semitic'),
                               ('Borrowed from Sicilian', 'romance_sicilian_italian'),
                               ('Derived from English', 'english')]:
            with self.subTest(text=text):
                self.assertEqual(etymological_stratum({'etymology_text': text}), expected)
        self.assertEqual(etymological_stratum({'etymology_templates': [{'name': 'mt-root', 'args': {'1': 'k-t-b'}}]}),
                         'unspecified')
        self.assertEqual(etymological_stratum({'word': 'kiteb'}), 'unspecified')


class MorphologyAndIPATests(unittest.TestCase):
    def test_empty_morphology_does_not_invent_forms(self):
        self.assertEqual(extract_morphology({}), {'verb_forms': [], 'number_forms': {}})

    def test_explicit_verb_forms_from_categories_tags_and_templates(self):
        row = {'categories': ['Maltese form-II verbs'], 'tags': ['Form IV'],
               'senses': [{'tags': ['Forma IX']}],
               'head_templates': [{'expansion': 'Forma VIII', 'args': {'form': 'III'}}]}
        self.assertEqual(extract_morphology(row)['verb_forms'], ['II', 'III', 'IV', 'IX', 'VIII'])
        self.assertEqual(extract_morphology({'tags': ['Form INVALID', 'Form XIV']})['verb_forms'], [])

    def test_number_forms_filter_placeholders_and_deduplicate(self):
        row = {'pos': 'noun', 'head_templates': [{'args': {'p': '<b>kotba</b>, kotba, -, ?',
                                          'coll': 'tuffieħ', 'sing': 'tuffieħa'}}],
               'forms': [{'form': 'kotba', 'tags': ['plural']},
                         {'form': 'kotba', 'tags': ['plural']},
                         {'form': 'tuffieħ', 'tags': ['collective']},
                         {'form': 'tuffieħa', 'tags': ['singulative']},
                         {'form': '-', 'tags': ['plural']},
                         {'form': '[bad]', 'tags': ['plural']},
                         {'form': 'header', 'tags': ['plural', 'table-tags']},
                         {'form': 'template', 'tags': ['plural', 'inflection-template']}]}
        self.assertEqual(extract_morphology(row), {
            'verb_forms': [], 'number_forms': {'coll': ['tuffieħ'], 'collective': ['tuffieħ'],
                'p': ['kotba'], 'plural': ['kotba'], 'sing': ['tuffieħa'], 'singulative': ['tuffieħa']}})

    def test_ipa_wrappers_stress_spacing_and_length(self):
        self.assertEqual(normalize_ipa('/ˈkɪ.tɛːb/'), 'kiteb')
        self.assertEqual(normalize_ipa('[ ˌK I : T E ˑ B ]\t\n'), 'kiteb')
        self.assertEqual(normalize_ipa(''), '')

    def test_lexical_number_excludes_finite_and_pronominal_forms(self):
        bad = ['first-person', 'second-person', 'third-person', 'imperfect', 'perfect',
               'imperative', 'negative', 'possessive', 'object', 'indirect-object', 'direct-object']
        for pos in ('noun', 'adj', 'participle', 'num'):
            for tag in bad:
                row = {'pos': pos, 'forms': [{'form': 'kotba', 'tags': ['plural', tag]}]}
                self.assertEqual(extract_morphology(row)['number_forms'], {})
        for pos in ('verb', 'prep'):
            row = {'pos': pos, 'head_templates': [{'args': {'p': 'ktibna'}}],
                   'forms': [{'form': 'jiktbu', 'tags': ['plural']}]}
            self.assertEqual(extract_morphology(row)['number_forms'], {})
            row['forms'].append({'form': 'miktubin', 'tags': ['plural', 'participle']})
            self.assertEqual(extract_morphology(row)['number_forms'], {'plural': ['miktubin']})

    def test_ipa_affricates_and_lossy_symbol_equivalence(self):
        for variants, expected in [(('t͡ʃ', 'ʧ', 'tʃ'), 'tʃ'),
                                   (('d͡ʒ', 'ʤ', 'dʒ'), 'dʒ'),
                                   (('t͡s', 'ʦ', 'ts'), 'ts')]:
            for variant in variants:
                with self.subTest(variant=variant):
                    self.assertEqual(normalize_ipa(variant), expected)
        self.assertEqual(normalize_ipa('ɪɛɔʊɐəɑħɡ'), 'ieouaaahg')


class GeneratedReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit_dir = Path(__file__).resolve().parents[1] / 'data' / 'audit'
        cls.report_path = cls.audit_dir / 'lexeme_inventory_report.json'
        cls.alias_path = cls.audit_dir / 'phase0_source_inventory.json'
        # Missing or malformed reports fail the integration suite; never skip them.
        cls.report_bytes = cls.report_path.read_bytes()
        cls.alias_bytes = cls.alias_path.read_bytes()
        cls.report = json.loads(cls.report_bytes.decode('utf-8'))

    def test_report_files_exist_and_are_byte_identical(self):
        self.assertTrue(self.report_path.is_file())
        self.assertTrue(self.alias_path.is_file())
        self.assertEqual(self.report_bytes, self.alias_bytes)

    def test_all_six_sections_are_populated(self):
        sections = {'metadata', 'source_files_inventory', 'gabra_audit', 'kaikki_audit',
                    'cross_source_reconciliation', 'auxiliary_sources_and_benchmarks'}
        self.assertTrue(sections <= self.report.keys())
        for section in sections:
            with self.subTest(section=section):
                self.assertTrue(self.report[section])

    def test_gabra_conservation(self):
        gabra = self.report['gabra_audit']
        self.assertEqual(gabra['total_records'], 21083)
        self.assertEqual(gabra['unique_mdx_keys'], 19831)
        self.assertEqual(gabra['clean_lexical_headwords'] + gabra['excluded_headword_count'], 19831)
        self.assertEqual(len(set(gabra['clean_headwords'])), gabra['clean_lexical_headwords'])
        self.assertEqual(len(gabra['anomalies']), gabra['excluded_headword_count'])

    def test_kaikki_classification_conservation(self):
        kaikki = self.report['kaikki_audit']
        self.assertEqual(kaikki['total_jsonl_lines'], 80790)
        self.assertEqual(set(kaikki['classification']), set(CLASSES))
        self.assertEqual(sum(kaikki['classification'].values()), 80790)
        for category, count in kaikki['classification'].items():
            with self.subTest(category=category):
                self.assertGreaterEqual(count, 0)
                self.assertEqual(sum(kaikki['pos_distribution_by_class'][category].values()), count)

    def test_reconciliation_partitions_and_union_sizes(self):
        reconciliation = self.report['cross_source_reconciliation']
        clean = set(self.report['gabra_audit']['clean_headwords'])
        evidence = self.report['kaikki_audit']['morphology_extraction']['evidence']
        lemma = {e['word'] for e in evidence if lexical_anomaly(e['word']) is None}
        counts_by_partition = {
            'both': 'gabra_and_kaikki_independent_lemma',
            'gabra_only_wordform_or_variant': 'gabra_kaikki_only_wordform_or_variant',
            'gabra_absent': 'gabra_absent_from_kaikki',
            'gabra_only_meta_or_other': 'gabra_kaikki_only_meta_or_other',
            'kaikki_only_lemma': 'kaikki_independent_lemma_absent_from_gabra',
        }
        for mode, expected in [('exact_nfc', 24345), ('normalized', 24045)]:
            with self.subTest(mode=mode):
                gabra_words, lemma_words = clean, lemma
                if mode == 'normalized':
                    gabra_words = {normalize_exact_search(w) for w in clean}
                    lemma_words = {normalize_exact_search(w) for w in lemma}
                result = reconciliation[mode]
                partitions = {k: set(v) for k, v in result['headword_partitions'].items()}
                self.assertEqual(set(partitions), set(counts_by_partition))
                for key, count_key in counts_by_partition.items():
                    self.assertEqual(len(result['headword_partitions'][key]), len(partitions[key]))
                    self.assertEqual(len(partitions[key]), result[count_key])
                for a, b in combinations(partitions, 2):
                    self.assertFalse(partitions[a] & partitions[b], (mode, a, b))
                gabra_partition_keys = set(partitions) - {'kaikki_only_lemma'}
                self.assertEqual(sum(result[counts_by_partition[k]] for k in gabra_partition_keys),
                                 len(gabra_words))
                self.assertEqual(set().union(*(partitions[k] for k in gabra_partition_keys)), gabra_words)
                self.assertEqual(partitions['both'], gabra_words & lemma_words)
                self.assertEqual(partitions['kaikki_only_lemma'], lemma_words - gabra_words)
                self.assertEqual(set().union(*partitions.values()), gabra_words | lemma_words)
                self.assertEqual(result['combined_master_lemma_count'], len(gabra_words | lemma_words))
                self.assertEqual(result['combined_master_lemma_count'], expected)

    def test_master_inventory_and_bucket_conservation(self):
        reconciliation = self.report['cross_source_reconciliation']
        inventory = reconciliation['master_inventory']
        words = [entry['word'] for entry in inventory['lemmas']]
        total = inventory['total_unique_lemma_headwords']
        self.assertEqual(total, 24345)
        self.assertEqual(len(words), total)
        self.assertEqual(len(set(words)), total)
        exact_partitions = reconciliation['exact_nfc']['headword_partitions']
        self.assertEqual(set(words), set().union(*(set(v) for v in exact_partitions.values())))
        for field, buckets, expected in (
            ('letter_distribution_30_plus_hash', MALTESE_ALPHABET_30 + ('#',),
             Counter(get_letter_bucket_30(w) for w in words)),
            ('ui_bucket_distribution', MALTESE_UI_BUCKETS_30,
             Counter(get_ui_letter_bucket(w)['bucket'] for w in words)),
        ):
            with self.subTest(field=field):
                distribution = inventory[field]
                self.assertEqual(set(distribution), set(buckets))
                self.assertEqual(sum(distribution.values()), total)
                self.assertEqual(distribution, {bucket: expected[bucket] for bucket in buckets})
        self.assertEqual(inventory['ie_sub_prefix_count'],
                         sum(get_ui_letter_bucket(w)['sub_prefix'] == 'ie' for w in words))


if __name__ == '__main__':
    unittest.main()
