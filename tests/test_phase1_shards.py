"""Phase 1 conservation, provenance, real compiler and HTTP integration tests."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from app.server import make_server
from scripts.build_phase1_shards import build, resolve_edges, targets
from scripts.maltese_alphabet import MALTESE_UI_BUCKETS_30, maltese_sort_key, normalize_exact_search
from scripts.phase0_inventory_audit import audit_gabra, canonical_root, classify_kaikki_row, lexical_anomaly, LEMMA_CLASSES, read_kaikki
from scripts.phase1_showcase import SHOWCASE
from scripts.phase2_enrichment import load_overlays, dataset_version
ENRICHED, OVERLAY_DIGESTS = load_overlays()

PROJECT = Path(__file__).resolve().parents[1]


class Phase1ShardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        artifacts = PROJECT / 'tests/artifacts'
        artifacts.mkdir(exist_ok=True)
        scratch = (artifacts / f'phase1-{uuid.uuid4().hex}').resolve()
        if not scratch.is_relative_to(artifacts.resolve()):
            raise ValueError('Temporary outputs must remain inside tests/artifacts')
        # Windows Python 3.13 tempfile uses a private 0700 ACL; restricted
        # tokens cannot reopen it. Normal inherited workspace ACLs are enough.
        scratch.mkdir()
        cls.addClassCleanup(shutil.rmtree, scratch)
        cls.output = scratch / 'data'
        cls.seed = scratch / 'summary.json'
        cls.summary = build(PROJECT / 'data/raw', cls.output, cls.seed)
        cls.manifest = json.loads((cls.output / 'manifest.json').read_text(encoding='utf-8'))
        cls.index = json.loads((cls.output / 'index_lite.json').read_text(encoding='utf-8'))
        cls.compact = json.loads((cls.output / 'wordforms_lookup.json').read_text(encoding='utf-8'))
        cls.lookup = {surface: [{'lemma': lemma, 'tag': cls.compact['tags'][tag]} for lemma, tag in links]
                      for surface, links in cls.compact['forms'].items()}
        cls.entries = [entry for shard in cls.manifest['shards']
                       for entry in json.loads((cls.output / shard['file']).read_text(encoding='utf-8'))]
        cls.by_word = {e['id']: e for e in cls.entries}

    def test_artifacts_and_content_digests(self):
        self.assertEqual(self.manifest['version'], dataset_version(OVERLAY_DIGESTS))
        self.assertEqual(json.loads(self.seed.read_text(encoding='utf-8')), self.summary)
        self.assertEqual(len(list((self.output / 'shards').glob('*.json'))), 30)
        for meta in self.manifest['shards'] + [self.manifest['index_lite'], self.manifest['wordforms_lookup']]:
            with self.subTest(file=meta['file']):
                self.assertTrue(meta['file'].isascii())
                payload = (self.output / meta['file']).read_bytes()
                self.assertEqual(len(payload), meta['bytes'])
                self.assertEqual(hashlib.sha256(payload).hexdigest(), meta['sha256'])

    def test_full_pool_and_tiers_conserve(self):
        self.assertEqual(len(self.index), 24045)
        self.assertEqual(len(self.entries), 24045)
        self.assertEqual(len(self.by_word), 24045)
        self.assertEqual(sum(self.manifest['tier_counts'].values()), 24045)
        self.assertEqual(Counter(str(e['tier']) for e in self.index), self.manifest['tier_counts'])
        self.assertEqual({e['id'] for e in self.index}, set(self.by_word))

    def test_tiers_follow_raw_source_evidence(self):
        _, gabra = audit_gabra(PROJECT / 'data/raw')
        gkeys = {normalize_exact_search(r['word']) for r in gabra if r['clean']}
        rich = {normalize_exact_search(r['word']) for r in gabra if r['clean'] and
                canonical_root(r['root']) and r['phonetic'] and r['glosses']}
        kkeys = {normalize_exact_search(r['word']) for r in read_kaikki(PROJECT / 'data/raw/kaikki.org-dictionary-Maltese.jsonl')
                 if classify_kaikki_row(r) in LEMMA_CLASSES and lexical_anomaly(r['word']) is None}
        self.assertEqual(set(self.by_word), gkeys | kkeys)
        dual, rich_pool = gkeys & kkeys, kkeys | rich
        for e in self.index:
            key = e['id']
            expected = 1 if key in dual else 2 if key in rich_pool else 3
            self.assertEqual(e['tier'], expected, key)

    def test_ui_buckets_prefixes_and_dms_order(self):
        self.assertEqual(self.manifest['MALTESE_UI_BUCKETS_30'], list(MALTESE_UI_BUCKETS_30))
        self.assertEqual(sum(s['count'] for s in self.manifest['shards']), 24045)
        self.assertEqual(Counter(e['bucket'] for e in self.index),
                         Counter({b:n for b,n in self.manifest['bucket_counts'].items() if n}))
        words = [e['word'] for e in self.index]
        self.assertEqual(words, sorted(words,key=lambda w:maltese_sort_key(w,mode='dms200')))
        self.assertIn('ie', self.manifest['sub_prefix_counts']['I'])
        self.assertEqual(next(iter(self.manifest['sub_prefix_counts']['I'])), 'ie')
        for e in self.index:
            if e['word'].lower().startswith('ie'):
                self.assertEqual((e['bucket'],e['sub_prefix']), ('I','ie'))

    def test_reverse_lookup_inflections_articles_and_clitics(self):
        for surface, lemma in [('ktibt','kiteb'), ('kotba','ktieb'), ('kun','kien'),
                               ('jiktbu','kiteb'), ('ix-xemx','xemx'), ('il-ktieb','ktieb'),
                               ('l-iskola','skola'), ('fil-ktieb','ktieb'), ("m'għandix",'għand')]:
            with self.subTest(surface=surface):
                self.assertIn(lemma, [r['lemma'] for r in self.lookup[surface]])
                self.assertTrue(all(r['tag'] for r in self.lookup[surface]))
        self.assertTrue(any('first-person' in r['tag'] and 'perfect' in r['tag'] for r in self.lookup['ktibt']))
        for surface,candidates in self.lookup.items():
            for candidate in candidates:
                self.assertIn(candidate['lemma'], self.by_word)
            self.assertEqual(surface, normalize_exact_search(surface))

    def test_reverse_chains_stop_on_cycles_and_absent_lemmas(self):
        edges={'a':{'b'},'b':{'a','c'},'d':{'missing'}}
        self.assertEqual(resolve_edges('a',edges,{'c'}), {'c'})
        self.assertEqual(resolve_edges('d',edges,{'c'}), set())
        self.assertEqual(resolve_edges('a',edges,set()), set())

    def test_multi_lemma_references_are_kept_as_alternatives(self):
        row = {'head_templates':[{'name':'mt-head','args':{'1':'verb form','2':'sab,sieb'}}],
               'senses':[{'form_of':[{'word':'qattus and qattusa'}]}]}
        found={key for key,tag in targets(row)}
        self.assertTrue({'sab','sieb','qattus','qattusa'} <= found)

    def test_reverse_tags_intern_grammar_without_repeated_spellings(self):
        row = {'word': 'ktibt', 'head_templates': [{'name': 'mt-head',
               'args': {'1': 'verb form', '2': 'kiteb'},
               'expansion': 'ktibt\n# first-person singular perfect of kiteb\n# second-person singular perfect of kiteb'}]}
        found = targets(row)
        self.assertEqual(found, [('kiteb', 'mt-head: first-person singular perfect / second-person singular perfect')])

    def test_output_cannot_overwrite_raw_sources(self):
        with self.assertRaisesRegex(ValueError,'raw source'):
            build(PROJECT/'data/raw',PROJECT/'data/raw/generated',self.seed)

    def test_phase1_can_read_the_release_zip_without_a_repository_clone(self):
        raw = self.output.parent / 'zip-only-raw'
        raw.mkdir()
        shutil.copyfile(PROJECT/'data/raw/GabraMalteseDict_MDX_v1.0.zip',raw/'GabraMalteseDict_MDX_v1.0.zip')
        report, records = audit_gabra(raw,require_repository=False)
        self.assertEqual(len(records),21083)
        self.assertIsNone(report['release_repository_byte_identity'])
        # Phase 0 retains its original strict default.
        with self.assertRaises(FileNotFoundError):
            audit_gabra(raw)

    def test_rebuild_matches_workbench_and_tracked_summary(self):
        generated=PROJECT/'app/static/data'
        for path in self.output.rglob('*.json'):
            self.assertEqual(path.read_bytes(),(generated/path.relative_to(self.output)).read_bytes(),path.name)
        self.assertEqual(self.seed.read_bytes(),(PROJECT/'data/seed/lemma_pool_summary.json').read_bytes())

    def test_eight_dimension_schema_and_nullable_boundaries(self):
        required={'headword','morphology','senses','dual_scenarios','inflection_and_clitics','pragmatics_and_cognates','etymology'}
        for e in self.entries:
            self.assertTrue(required <= set(e))
            h,m=e['headword'],e['morphology']
            self.assertEqual(h['editorial_status'],'source_attested')
            self.assertIn(h['ipa_source'], ('gabra','kaikki','wikipron',None))
            if not m['root_consonants']:
                self.assertIsNone(m['root_radicals'])
                self.assertIsNone(m['word_family'])
            p = e['pragmatics_and_cognates']
            if p and p['register']:
                self.assertEqual(p['register'],sorted(p['register']))
            for relative in m['word_family'] or []:
                relative_id=normalize_exact_search(relative)
                self.assertIn(relative_id,self.by_word)
                self.assertTrue({r['root'] for r in m['root_evidence']} &
                                {r['root'] for r in self.by_word[relative_id]['morphology']['root_evidence']})
            if e['id'] not in ENRICHED:
                self.assertIsNone(e['dual_scenarios'])
                self.assertTrue(all(s['zh_definition'] is None for s in e['senses']))
        self.assertIsNone(self.by_word['skola']['morphology']['root_consonants'])
        self.assertEqual(self.by_word['skola']['morphology']['pattern_type'],'hybrid_assimilated')
        self.assertIn('kotba',self.by_word['ktieb']['morphology']['plural_forms'])
        self.assertEqual(self.by_word['kiteb']['morphology']['imperfect'],'jikteb')

    def test_showcase_has_honest_examples_and_translations(self):
        self.assertEqual(self.summary['showcase_count'],100)
        for key in SHOWCASE:
            entry=self.by_word[key]
            self.assertEqual(entry['dual_scenarios']['formal']['source_type'],'pedagogical_example')
            self.assertEqual(entry['dual_scenarios']['colloquial']['source_type'],'pedagogical_dialogue')
            self.assertEqual(entry['dual_scenarios']['review_status'],'phase2_reviewed')
            self.assertTrue(entry['dual_scenarios']['formal']['zh'])
            self.assertTrue(entry['dual_scenarios']['colloquial']['zh'])
            teaching=[s for s in entry['senses'] if s['definition_origin']=='authored_pedagogical']
            self.assertEqual(len(teaching),1)
            self.assertTrue(teaching[0]['zh_definition'])
            self.assertTrue(teaching[0]['collocations'])

    def test_audio_and_root_aggregate_counts(self):
        self.assertEqual(self.summary['audio_source_rows'],720)
        self.assertEqual(self.summary['audio_count'],sum(bool(e['headword']['audio_url']) for e in self.entries))
        self.assertEqual(self.summary['root_count'],sum(bool(e['morphology']['root_consonants']) for e in self.entries))
        for e in self.entries:
            if e['headword']['audio_url']:
                self.assertTrue(e['headword']['audio_url'].startswith('https://upload.wikimedia.org/'))
                self.assertTrue(e['headword']['audio_file'])
                self.assertTrue(e['headword']['audio_commons_url'].startswith('https://commons.wikimedia.org/wiki/File:'))

    def test_nominal_plurals_never_contain_verbal_inflections(self):
        self.assertIn('kotba', self.by_word['ktieb']['morphology']['plural_forms'])
        for word in ('kiteb', 'għand'):
            self.assertFalse(set(self.by_word[word]['morphology']['plural_forms'] or []) &
                             {'jiktbu', 'ktibna', 'iktbu', 'għandhom'})

    def test_homographs_preserve_source_record_boundaries(self):
        dar = self.by_word['dar']['lexeme_analyses']
        noun = next(a for a in dar if a['source'] == 'kaikki' and a['pos'] == 'noun')
        verb = next(a for a in dar if a['source'] == 'kaikki' and a['pos'] == 'verb')
        self.assertEqual(noun['gender'], 'f.')
        self.assertIn('djar', noun['plural_forms'])
        self.assertIsNone(noun['verb_paradigm'])
        # Kaikki has no explicit Latin-script root for this record; Ġabra does.
        self.assertIsNone(verb['root_consonants'])
        rooted_verb = next(a for a in dar if a['source'] == 'gabra' and a['root_consonants'] == 'd-w-r')
        self.assertEqual(rooted_verb['pos'], 'VERB')
        self.assertTrue(all('house' not in s['en_definition'] for s in rooted_verb['senses']))
        self.assertEqual(verb['verb_paradigm']['imperfett_3sg_m'], 'jdur')
        self.assertEqual(verb['verb_paradigm']['past_participle'], 'midur')
        self.assertIsNone(verb['plural_forms'])
        self.assertNotEqual(noun['senses'], verb['senses'])
        for entry in self.entries:
            ids = [a['source_record_id'] for a in entry['lexeme_analyses']]
            self.assertEqual(len(ids), len(set(ids)))

    def test_root_attestation_does_not_imply_historical_stratum(self):
        rooted_gabra_only = [e for e in self.entries if e['headword']['source_presence'] == ['gabra']
                             and e['morphology']['root_consonants']]
        self.assertTrue(rooted_gabra_only)
        for entry in rooted_gabra_only:
            self.assertEqual(entry['etymology']['stratum'], 'unspecified')
            self.assertEqual(entry['morphology']['root_status'], 'attested')
            self.assertEqual(entry['morphology']['pattern_type'], 'root_and_pattern')
        self.assertTrue(all(a['stratum'] == 'unspecified' for e in self.entries
                            for a in e['lexeme_analyses'] if a['source'] == 'gabra'))

    def test_compact_lookup_and_snapshot_license(self):
        self.assertEqual(self.compact['version'], self.manifest['version'])
        self.assertEqual(set(self.compact), {'version', 'tags', 'forms'})
        self.assertLess(self.manifest['wordforms_lookup']['bytes'], 6_000_000)
        self.assertEqual(self.manifest['sources']['gabra']['license'], 'CC BY 3.0')


class Phase1HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=5)

    def test_workbench_serves_real_resources(self):
        for path in ('/','/app.js','/worker.js','/db.js','/audio.js','/sw.js','/styles.css','/data/manifest.json'):
            with self.subTest(path=path), urlopen(self.base+path,timeout=5) as response:
                self.assertEqual(response.status,200)
                self.assertTrue(response.read())
                if path.endswith('.js'):
                    self.assertIn('javascript',response.headers['Content-Type'])

    def test_raw_data_git_and_traversal_not_served(self):
        for path in ('/data/raw/','/.git/config','/../server.py','/%2e%2e/server.py','/data/'):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(self.base+path,timeout=5)
            self.assertIn(error.exception.code,(403,404))

    def test_custom_port_cli(self):
        result=subprocess.run([sys.executable,'app/server.py','--help'],cwd=PROJECT,capture_output=True,text=True,encoding='utf-8',timeout=10)
        self.assertEqual(result.returncode,0)
        self.assertIn('--port',result.stdout)


class Phase1ClientTests(unittest.TestCase):
    def test_actual_worker_and_audio_pipeline(self):
        node=shutil.which('node')
        if not node:
            self.skipTest('Node.js is required for optional JavaScript behavior checks')
        result=subprocess.run([node,'tests/phase1_client_checks.mjs'],cwd=PROJECT,capture_output=True,text=True,encoding='utf-8',timeout=40)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('client checks passed',result.stdout)


if __name__ == '__main__':
    unittest.main()
