"""Phase 2 positive integration and adversarial gate/overlay regressions."""
from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import threading
import uuid

from scripts.phase2_enrichment import (PROJECT, apply_overlays, load_overlays,
                                       write_json, pos_class, validate_overlay, required_sense_selectors)
from scripts.phase2_quality_gates import (compute_definite_article, validate_definite_article,
    gate1, gate2, gate3, gate4, gate5, protected_record, content_samples, validate_dataset)
from scripts.phase1_showcase import SHOWCASE
from scripts.maltese_alphabet import strip_definite_article
from scripts.run_phase2_enrichment import prepare_batch
from scripts.sync_enriched_to_shards import sync
from scripts import run_phase2_sliding_queue as queue
from scripts import run_phase2_ab_benchmark as benchmark


class ArticleTests(unittest.TestCase):
    def test_canonical_articles_and_provenance(self):
        cases = {'ktieb': 'il-ktieb', 'kbir': 'il-kbir', 'kliem': 'il-kliem',
            'xemx': 'ix-xemx', 'żmien': 'iż-żmien', 'triq': 'it-triq', 'jum': 'il-jum',
            'skola': 'l-iskola', 'student': 'l-istudent', 'sptar': 'l-isptar',
            'storja': 'l-istorja', 'stess': 'l-istess', 'xkaffa': 'l-ixkaffa',
            'żball': 'l-iżball', 'għajn': 'l-għajn', 'ilma': 'l-ilma',
            'omm': 'l-omm', 'idea': 'l-idea', 'hena': 'l-hena',
            'ċavetta': 'iċ-ċavetta', 'dar': 'id-dar', 'nar': 'in-nar',
            'ras': 'ir-ras', 'sema': 'is-sema', 'zokkor': 'iz-zokkor',
            'żgħir': 'iż-żgħir', 'ħobż': 'il-ħobż', 'ġnien': 'il-ġnien'}
        for word, form in cases.items():
            with self.subTest(word=word):
                obj = compute_definite_article(word, 'noun')
                self.assertEqual(obj['form'], form)
                self.assertTrue(validate_definite_article(word, obj))
                self.assertEqual(obj['source_type'], 'grammar_reference')
                self.assertEqual(obj['source'], 'docs/MASTER_PLAN_V2.md#gate-3')

    def test_nominal_pos_aliases_and_non_nominal(self):
        for pos in ['noun', 'NOUN', 'n.', 'n.m.', 'n.f.', 'adj', 'adj.', 'num', 'num.']:
            self.assertIsNotNone(compute_definite_article('ktieb', pos))
        for pos in ['verb', 'prep', 'ADP', 'intj', None, '']:
            self.assertIsNone(compute_definite_article('kiteb', pos))

    def test_rejects_invalid_articles_and_false_provenance(self):
        for word, bad in [('ktieb', 'l-iktieb'), ('ktieb', 'ix-ktieb'), ('jum', 'ij-jum'),
                          ('żmien', 'l-iżmien'), ('triq', 'l-itriq'), ('skola', 'is-skola')]:
            obj = compute_definite_article(word, 'noun')
            obj['form'] = bad
            self.assertFalse(validate_definite_article(word, obj))
        obj = compute_definite_article('ktieb', 'noun')
        for field, wrong in [('prefix', 'l-i'), ('source_type', 'corpus_attested'), ('source', 'invented'), ('context', 'any_context')]:
            self.assertFalse(validate_definite_article('ktieb', {**obj, field: wrong}))
        self.assertFalse(validate_definite_article('ktieb', None))
        with self.assertRaises(ValueError):
            compute_definite_article('', 'noun')

    def test_unicode_case_and_context_note(self):
        self.assertEqual(compute_definite_article('Z\u0307mien', 'noun')['form'], 'iż-żmien')
        self.assertIn('after consonants', compute_definite_article('għajn', 'noun')['note'])
        self.assertIn('after consonants', compute_definite_article('hena', 'noun')['note'])

    def test_search_stripping_cannot_reintroduce_invalid_euphonic_articles(self):
        known = {'ktieb', 'żmien', 'triq', 'jum', 'żgħir', 'skola'}
        for query, forbidden in [('l-iktieb', 'ktieb'), ('l-iżmien', 'żmien'),
                                 ('l-itriq', 'triq'), ('ij-jum', 'jum'), ('l-iżgħir', 'żgħir')]:
            self.assertNotEqual(strip_definite_article(query, known_lemmas=known)[0], forbidden)
        self.assertEqual(strip_definite_article('l-iskola', known_lemmas=known), ('skola', 'l-i'))


class Phase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = PROJECT / 'app/static/data'
        read = lambda name: json.loads((cls.data / name).read_text(encoding='utf-8'))
        cls.manifest = read('manifest.json')
        cls.index, cls.lookup, cls.baseline = read('index_lite.json'), read('wordforms_lookup.json'), read('phase2_baseline.json')
        cls.entries = [e for meta in cls.manifest['shards'] for e in read(meta['file'])]
        cls.by_key = {e['id']: e for e in cls.entries}
        cls.overlays, cls.digests = load_overlays()
        artifacts = PROJECT / 'tests/artifacts'
        artifacts.mkdir(exist_ok=True)
        cls.scratch = artifacts / ('phase2-' + uuid.uuid4().hex)
        cls.scratch.mkdir()
        cls.addClassCleanup(shutil.rmtree, cls.scratch)

    def test_all_five_gates_and_deterministic_report(self):
        report = validate_dataset()
        self.assertTrue(report['passed'], {n: g['errors'][:8] for n, g in report['gates'].items()})
        self.assertEqual(len(report['gates']), 5)
        saved = json.loads((PROJECT / 'data/audit/phase2_quality_gate_report.json').read_text(encoding='utf-8'))
        self.assertEqual(report, saved)
        self.assertTrue(all(g['passed'] and g['error_count'] == 0 for g in report['gates'].values()))

    def test_batch_complete_and_conserved(self):
        self.assertGreaterEqual(len(self.overlays), 100)
        self.assertTrue(set(SHOWCASE) <= set(self.overlays))
        self.assertGreaterEqual(len(set(self.overlays) - set(SHOWCASE)), 75)
        self.assertEqual({e['id'] for e in self.index if e.get('is_enriched')}, set(self.overlays))
        self.assertEqual(self.manifest['enriched_count'], len(self.overlays))
        self.assertEqual(self.manifest['unenriched_count'], 24045 - len(self.overlays))
        self.assertEqual(self.manifest['showcase_count'], len(self.overlays))
        self.assertEqual(self.manifest['total_lemmas'], 24045)
        self.assertEqual(len(self.lookup['forms']), 124488)
        tiers = {i['id']: i['tier'] for i in self.index}
        has_audio = {i['id']: i['has_audio'] for i in self.index}
        self.assertTrue(all(tiers[k] in (1, 2) or has_audio[k] for k in set(self.overlays) - set(SHOWCASE)))
        self.assertEqual(tiers['bongu'], 3)
        self.assertEqual(tiers['għand'], 2)

    def test_every_entry_has_complete_authored_dimensions(self):
        for key, item in self.overlays.items():
            with self.subTest(key=key):
                e = self.by_key[key]
                teaching = next(s for s in e['senses'] if s['id'] == 'teaching')
                self.assertTrue(all(teaching[k] for k in ('en_definition', 'zh_definition', 'mt_definition', 'pos')))
                self.assertEqual(teaching['source'], 'phase2_enrichment')
                self.assertEqual(teaching['definition_origin'], 'authored_pedagogical')
                self.assertEqual(teaching['review_status'], 'phase2_reviewed')
                self.assertGreaterEqual(len(teaching['collocations']), 2)
                self.assertEqual(e['etymology']['cognitive_memory_aid'], item['cognitive_memory_aid'])
                for a in e['lexeme_analyses']:
                    for s in a['senses']:
                        self.assertTrue(s['zh_definition'])
                        self.assertEqual(s['translation_provenance']['definition_origin'], 'authored_pedagogical')

    def test_source_evidence_unchanged(self):
        for key in self.overlays:
            self.assertEqual(protected_record(self.by_key[key]), protected_record(self.baseline[key]['entry']), key)

    def test_dar_homograph_sense_isolation(self):
        e = self.by_key['dar']
        for a in e['lexeme_analyses']:
            if pos_class(a['pos']) == 'noun':
                self.assertTrue(all(not any(x in s['zh_definition'] for x in ('转向', '旅行', '转弯')) for s in a['senses']))
                self.assertIsNone(a['verb_paradigm'])
            else:
                self.assertTrue(all('房屋' not in s['zh_definition'] for s in a['senses']))
                self.assertIsNone(a['definite_article'])
        noun = next(a for a in e['lexeme_analyses'] if a['pos'] == 'noun')
        self.assertEqual([s['zh_definition'] for s in noun['senses']], ['房屋', '房间', '家庭'])

    def test_gate1_rejects_controls_placeholders_and_bad_orthography(self):
        for bad in ['TODO', 'TBD', '????', 'ċ\x00', 'a\n', 'z\u0307', '\u200b', '\ufffd']:
            self.assertTrue(gate1([], {'mt': bad}), repr(bad))
        self.assertTrue(gate1([], {'mt': 'ta’ Malta'}))
        self.assertTrue(gate1([], {'mt': 'il‐ktieb'}))
        self.assertFalse(gate1([], {'mt': "Ċ Ġ Għ Ħ Ie Ż ċ ġ għ ħ ie ż ta' Malta il-ktieb"}))

    def test_gate2_rejects_fabricated_root_form_and_lost_hybrid(self):
        for key, mutate in [
            ('skola', lambda e: e['morphology'].update(root_consonants='s-k-l')),
            ('kiteb', lambda e: e['morphology'].update(verb_form='Forma X')),
            ('skola', lambda e: e['morphology'].update(pattern_type='stem_affixation'))]:
            e = deepcopy(self.by_key[key]); mutate(e)
            self.assertTrue(gate2([e], {key: self.overlays[key]}, self.baseline))

    def test_gate2_rejects_translation_cross_contamination_and_analysis_loss(self):
        e = deepcopy(self.by_key['dar'])
        next(a for a in e['lexeme_analyses'] if a['pos'] == 'verb')['senses'][0]['zh_definition'] = '房屋'
        self.assertTrue(gate2([e], {'dar': self.overlays['dar']}, self.baseline))
        e = deepcopy(self.by_key['dar']); e['lexeme_analyses'].pop()
        self.assertTrue(gate2([e], {'dar': self.overlays['dar']}, self.baseline))

    def test_gate3_rejects_missing_article_and_unattested_clitic(self):
        e = deepcopy(self.by_key['ktieb'])
        e['lexeme_analyses'][0]['definite_article'] = None
        self.assertTrue(gate3([e], {'ktieb': self.overlays['ktieb']}, self.lookup))
        e = deepcopy(self.by_key['kiteb'])
        e['inflection_and_clitics']['pronomi_mehmuzin'] = [{'form': 'kitebhieliFAKE', 'source': 'camilleri'}]
        self.assertIn('unattested attached pronoun', ' '.join(gate3([e], {}, self.lookup)))

    def test_gate4_rejects_wrong_license_audio_and_unlabelled_authorship(self):
        for source, wrong in [('gabra', 'CC BY 4.0'), ('kaikki', 'public domain'), ('wikipron', 'Apache 2.0'), ('camilleri', 'CC BY-SA 3.0')]:
            manifest = deepcopy(self.manifest); manifest['sources'][source]['license'] = wrong
            self.assertIn(source + ': incorrect license', gate4([], {}, manifest))
        e = deepcopy(next(e for e in self.entries if e['headword']['audio_url']))
        e['headword']['audio_commons_url'] = None
        self.assertIn('missing Commons attribution', ' '.join(gate4([e], {}, self.manifest)))
        e = deepcopy(self.by_key['dar']); e['senses'][0]['definition_origin'] = 'licensed_source'
        self.assertIn('unlabelled authored definition', ' '.join(gate4([e], {'dar': self.overlays['dar']}, self.manifest)))

    def test_gate4_rejects_excluded_sources_and_historical_fabrication(self):
        for bad in ['masri', 'dizzjunarju.mt']:
            e = deepcopy(self.by_key['dar']); e['headword']['source_presence'].append(bad)
            self.assertIn('unapproved source', ' '.join(gate4([e], {}, self.manifest)))
        overlay = deepcopy(self.overlays['dar']); overlay['cognitive_memory_aid'] = '英国海军时期的故事'
        self.assertIn('unsupported historical story', ' '.join(gate4([self.by_key['dar']], {'dar': overlay}, self.manifest)))
        e = deepcopy(self.by_key['dar']); e['etymology'].pop('cognitive_memory_aid_provenance')
        self.assertIn('unlabelled mnemonic', ' '.join(gate4([e], {'dar': self.overlays['dar']}, self.manifest)))

    def test_gate5_rejects_count_drift(self):
        for field, wrong in [('enriched_count', 99), ('unenriched_count', 0), ('wordform_surface_count', 1), ('showcase_count', 25)]:
            manifest = {**self.manifest, field: wrong}
            self.assertTrue(gate5(self.entries, self.index, self.lookup, manifest, self.overlays), field)
        self.assertTrue(gate5(self.entries[:-1], self.index, self.lookup, self.manifest, self.overlays))

    def test_historical_context_uses_licensed_definition_but_not_teaching(self):
        e = deepcopy(self.by_key['kastellanija'])
        item = self.overlays['kastellanija']
        self.assertEqual(gate4([e], {'kastellanija': item}, self.manifest, check_audio_totals=False), [])
        for a in e['lexeme_analyses']:
            for s in a['senses']:
                s['definition_origin'] = 'authored_pedagogical'
        self.assertIn('unsupported historical story', ' '.join(gate4(
            [e], {'kastellanija': item}, self.manifest, check_audio_totals=False)))

    def test_stratified_samples_stable_and_cover_all_tiers(self):
        samples = content_samples(self.entries, self.index)
        self.assertEqual(samples, content_samples(list(reversed(self.entries)), self.index))
        self.assertEqual({s['stratum'].split('/')[0] for s in samples}, {'tier_1', 'tier_2', 'tier_3'})
        self.assertTrue(any(s['stratum'].endswith('/enriched') for s in samples))

    def test_sorted_overlay_files_and_fail_closed(self):
        folder = self.scratch / 'overlays'; folder.mkdir(exist_ok=True)
        write_json(folder / 'z.json', [self.overlays['dar']])
        write_json(folder / 'a.json', [self.overlays['ktieb']])
        loaded, digests = load_overlays(folder)
        self.assertEqual(list(loaded), ['ktieb', 'dar'])
        self.assertEqual(list(digests), ['a.json', 'z.json'])
        write_json(folder / 'z.json', [self.overlays['ktieb']])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            load_overlays(folder)
        for field in ('headword', 'morphology', 'lexeme_analyses', 'etymology', 'attested_forms'):
            write_json(folder / 'z.json', [{**self.overlays['dar'], field: {}}])
            with self.assertRaisesRegex(ValueError, 'forbidden'):
                load_overlays(folder)

    def test_incomplete_and_unattested_overlay_rejected(self):
        e, idx = deepcopy(self.by_key['dar']), deepcopy(next(i for i in self.index if i['id'] == 'dar'))
        bad = deepcopy(self.overlays['dar']); bad['sense_translations'][0]['en_definition'] = 'unattested meaning'
        with self.assertRaises(ValueError):
            apply_overlays([e], [idx], {'dar': bad}, {'dar': self.baseline['dar']})
        bad = deepcopy(self.overlays['dar']); bad['exact_key'] = 'nonexistent-lemma'
        with self.assertRaisesRegex(ValueError, 'absent from pool'):
            apply_overlays([e], [idx], {bad['exact_key']: bad})

    def test_corrupt_baseline_cannot_overwrite_source_evidence(self):
        e = deepcopy(self.by_key['dar'])
        idx = deepcopy(next(i for i in self.index if i['id'] == 'dar'))
        baseline = {'dar': deepcopy(self.baseline['dar'])}
        baseline['dar']['entry']['morphology']['root_consonants'] = 'f-a-k-e'
        with self.assertRaisesRegex(ValueError, 'baseline source evidence mismatch'):
            apply_overlays([e], [idx], {'dar': self.overlays['dar']}, baseline)
        self.assertEqual(protected_record(e), protected_record(self.by_key['dar']))

    def test_overlay_orthography_and_false_provenance_rejected_before_publication(self):
        folder = self.scratch / 'bad-overlay'; folder.mkdir()
        for field, bad in [('gloss_zh', 'TODO'), ('cognitive_memory_aid', 'bad\x00text')]:
            item = deepcopy(self.overlays['dar']); item[field] = bad
            write_json(folder / 'bad.json', [item])
            with self.assertRaises(ValueError):
                load_overlays(folder)
        item = deepcopy(self.overlays['dar'])
        item['sense_translations'][0]['definition_origin'] = 'licensed_source'
        write_json(folder / 'bad.json', [item])
        with self.assertRaisesRegex(ValueError, 'translation provenance'):
            load_overlays(folder)

    def test_fast_sync_byte_identical_and_overlay_removal_restores_baseline(self):
        data = self.scratch / 'sync-data'; shutil.copytree(self.data, data)
        summary = self.scratch / 'summary.json'
        shutil.copyfile(PROJECT / 'data/seed/lemma_pool_summary.json', summary)
        tracked = [p for p in data.rglob('*.json')]
        before = {p.relative_to(data): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
        sync(data, summary)
        self.assertEqual(before, {p.relative_to(data): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked})
        self.assertEqual(summary.read_bytes(), (PROJECT / 'data/seed/lemma_pool_summary.json').read_bytes())
        folder = self.scratch / 'remaining-overlay'; folder.mkdir()
        write_json(folder / 'batch.json', [v for k,v in self.overlays.items() if k != 'dar'])
        sync(data, summary, folder)
        meta = next(m for m in self.manifest['shards'] if m['bucket'] == 'D')
        dar = next(e for e in json.loads((data / meta['file']).read_text(encoding='utf-8')) if e['id'] == 'dar')
        self.assertEqual(dar, self.baseline['dar']['entry'])
        self.assertEqual(json.loads(summary.read_text(encoding='utf-8'))['enriched_count'], len(self.overlays) - 1)
        sync(data, summary)
        self.assertEqual(before, {p.relative_to(data): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked})

    def test_future_batch_preparation_is_bounded_and_does_not_dispatch(self):
        empty_overlays = self.scratch / 'empty-overlays'; empty_overlays.mkdir(exist_ok=True)
        _, request = prepare_batch(3, self.data, empty_overlays, self.scratch / 'request')
        self.assertEqual(request['batch_size'], 3)
        self.assertEqual(len(request['source_evidence']), 3)
        self.assertTrue(all(e['headword']['tier'] == 1 for e in request['source_evidence']))
        with self.assertRaises(ValueError):
            prepare_batch(0, self.data, empty_overlays, self.scratch / 'request')

    def test_all_100_dialogues_have_two_complete_preserved_turns(self):
        batch1 = {item['exact_key']: item for item in json.loads((PROJECT / 'data/enriched/phase2_tier1_batch1.json').read_text(encoding='utf-8'))}
        self.assertEqual(len(batch1), 100)
        for key, item in batch1.items():
            c = item['dual_scenarios']['colloquial']
            self.assertEqual(len(c['messages']), 2, key)
            for lang, field in [('mt', 'mt_spoken'), ('en', 'en'), ('zh', 'zh')]:
                self.assertEqual([s.strip() for s in c[lang].split('—') if s.strip()],
                                 [t[field] for t in c['messages']], key)
            for turn in c['messages']:
                self.assertEqual(turn['mt_spoken'], turn['mt_standard'])
                self.assertRegex(turn['speaker'], r'[\u4e00-\u9fff]')
        for key, item in self.overlays.items():
            c = item['dual_scenarios']['colloquial']
            self.assertGreaterEqual(len(c['messages']), 2, key)
            validate_overlay(item, self.by_key[key])

    def test_messages_and_anti_dilution_fail_closed_in_overlay_and_gate4(self):
        def messages(item, value):
            item['dual_scenarios']['colloquial']['messages'] = value
        mutations = [lambda i: messages(i, []), lambda i: messages(i, [{}]),
                     lambda i: messages(i, 'two turns'),
                     lambda i: i.update(cognitive_memory_aid='太短'),
                     lambda i: i['collocations'].__setitem__(1, deepcopy(i['collocations'][0])),
                     lambda i: i['collocations'][0].update(en=' ')]
        for field in ('speaker', 'mt_spoken', 'mt_standard', 'zh', 'en'):
            mutations.append(lambda i, f=field: i['dual_scenarios']['colloquial']['messages'][1].update({f: ' '}))
        for mutate in mutations:
            item = deepcopy(self.overlays['dar'])
            mutate(item)
            with self.assertRaises(ValueError):
                validate_overlay(item, self.by_key['dar'])
            entry = deepcopy(self.by_key['dar'])
            entry['dual_scenarios'] = deepcopy(item['dual_scenarios'])
            entry['etymology']['cognitive_memory_aid'] = item['cognitive_memory_aid']
            entry['senses'][0]['collocations'] = deepcopy(item['collocations'])
            errors = gate4([entry], {'dar': item}, self.manifest, check_audio_totals=False)
            self.assertTrue(errors)
        item = deepcopy(self.overlays['dar'])
        item['sense_translations'][0]['zh_definition'] = ' '
        with self.assertRaises(ValueError):
            validate_overlay(item)
        item = deepcopy(self.overlays['dar'])
        item['sense_translations'].pop()
        with self.assertRaisesRegex(ValueError, 'every exact attested'):
            validate_overlay(item, self.by_key['dar'])
        entry = deepcopy(self.by_key['dar'])
        entry['lexeme_analyses'][0]['senses'][0]['zh_definition'] = ' '
        self.assertIn('Every attested sense', ' '.join(gate4([entry], {}, self.manifest, check_audio_totals=False)))

    def test_packet_deduplicates_all_source_selectors_without_changing_english(self):
        entry = deepcopy(self.by_key['dar'])
        entry['senses'].append({'id': 'extra-source', 'pos': 'NOUN', 'en_definition': 'Top-level ONLY; exact punctuation!'})
        packet = queue.assemble_packet(entry)
        expected = []
        for sense in [s for a in entry['lexeme_analyses'] for s in a['senses']] + entry['senses']:
            if sense['id'] != 'teaching':
                selector = {'pos': pos_class(sense['pos']), 'en_definition': sense['en_definition']}
                if selector not in expected:
                    expected.append(selector)
        self.assertEqual(packet['sense_selectors'], expected)
        self.assertEqual(required_sense_selectors(entry), expected)
        self.assertNotIn('lexeme_analyses', packet)
        self.assertEqual(packet['word'], 'dar')
        self.assertEqual(packet['tier'], 1)
        self.assertEqual(packet['roots'], list(dict.fromkeys(r for a in entry['lexeme_analyses'] for r in a['roots'])))
        self.assertEqual(set(packet), {'exact_key', 'word', 'tier', 'stratum', 'roots', 'teaching_pos_default', 'sense_selectors'})
        item = deepcopy(self.overlays['dar'])
        with self.assertRaises(ValueError):
            validate_overlay(item, entry)

    def test_queue_priority_and_waves_preserve_dms_and_exclude_duplicates(self):
        clean = [{**i, 'is_enriched': False} for i in self.index]
        all_pool = queue.candidate_queue(clean, (), (), 'all')
        wave1 = queue.candidate_queue(clean, (), (), '1')
        wave2 = queue.candidate_queue(clean, (), (), '2')
        self.assertEqual(all_pool, wave1 + wave2)
        self.assertEqual(len(wave1), 5384)
        audio = [i for i in clean if i['has_audio']]
        self.assertEqual(wave1[:len(audio)], audio)
        self.assertTrue(all(i['tier'] == 1 for i in wave1[len(audio):]))
        self.assertTrue(all(i['tier'] == 2 and not i['has_audio'] for i in wave2))
        excluded = {all_pool[0]['exact_key']}
        filtered = queue.candidate_queue(clean, excluded, {all_pool[1]['exact_key']}, 'all')
        self.assertEqual(filtered, all_pool[2:])
        self.assertEqual(len({i['exact_key'] for i in all_pool}), len(all_pool))
        self.assertEqual(len(queue.candidate_queue(clean, wave='1')), 5384)
        self.assertEqual(len(queue.candidate_queue(clean)), 16465)

    def worker_store(self):
        return SimpleNamespace(entries=self.by_key, indices={i['id']: i for i in self.index},
                               manifest=self.manifest, lookup=self.lookup)

    def test_worker_partial_commit_positions_provenance_and_no_source_mutation(self):
        packets = [queue.assemble_packet(self.by_key[k]) for k in ('dar', 'ktieb', 'kiteb')]
        rows = [deepcopy(self.overlays[k]) for k in ('dar', 'ktieb')]
        rows[1]['dual_scenarios']['colloquial']['messages'] = []
        rows[0]['teaching_sense']['source'] = 'wrong-worker-label'
        rows[0]['dual_scenarios']['colloquial']['messages'][0]['mt_standard'] = 'M?għandix ħin?'
        before = deepcopy(self.by_key['dar'])
        def invoke(command, prompt, timeout):
            self.assertIn('read-only', command)
            self.assertIn('--ephemeral', command)
            self.assertEqual(command[-1], '-')
            self.assertEqual(timeout, 420)
            self.assertIn(json.dumps(packets[0]['sense_selectors'], ensure_ascii=False, separators=(',', ':')), prompt)
            Path(command[command.index('-o') + 1]).write_text('```json\n' + json.dumps(rows, ensure_ascii=False) + '\n```', encoding='utf-8')
            return 0, '', ''
        with patch.object(queue.shutil, 'which', return_value='codex'), patch.object(queue, '_invoke_worker', side_effect=invoke), patch.object(queue, 'source_store', return_value=self.worker_store()):
            result = queue.process_micro_batch('mock-partial', packets, 420)
        self.assertEqual(set(result['validated_entries']), {'dar'}, result['errors'])
        self.assertEqual(set(result['errors']), {'ktieb', 'kiteb'})
        self.assertEqual(result['positions'], {'dar': 1, 'ktieb': 2, 'kiteb': 3})
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['validated_entries']['dar']['teaching_sense']['source'], 'phase2_enrichment')
        self.assertEqual(result['validated_entries']['dar']['dual_scenarios']['colloquial']['messages'][0]['mt_standard'], "M'għandix ħin?")
        self.assertEqual(self.by_key['dar'], before)

    def test_worker_duplicate_missing_timeout_and_selector_mismatch_are_per_word_errors(self):
        packets = [queue.assemble_packet(self.by_key[k]) for k in ('dar', 'ktieb')]
        bad = deepcopy(self.overlays['dar'])
        bad['sense_translations'][0]['en_definition'] += ' WRONG'
        good = deepcopy(self.overlays['ktieb'])
        for rows, expected_valid in [([bad, good], {'ktieb'}), ([good, good], set()), ({'ktieb': good}, {'ktieb'}), (good, {'ktieb'}), ([], set())]:
            def invoke(command, prompt, timeout):
                Path(command[command.index('-o') + 1]).write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
                return 1, '', ''  # A completed output can survive a nonzero worker exit.
            with patch.object(queue.shutil, 'which', return_value='codex'), patch.object(queue, '_invoke_worker', side_effect=invoke), patch.object(queue, 'source_store', return_value=self.worker_store()):
                result = queue.process_micro_batch('mock-output', packets, 420)
            self.assertEqual(set(result['validated_entries']), expected_valid, result['errors'])
            self.assertEqual(set(result['errors']), {'dar', 'ktieb'} - expected_valid)
        with patch.object(queue.shutil, 'which', return_value='codex'), patch.object(queue, '_invoke_worker', side_effect=queue.subprocess.TimeoutExpired('codex', 1)):
            result = queue.process_micro_batch('mock-timeout', packets, 1)
        self.assertEqual(set(result['errors']), {'dar', 'ktieb'})
        self.assertFalse(result['validated_entries'])

    def test_unicode_normalization_keeps_question_marks_and_exact_english(self):
        row = queue.normalize_overlay({'mt_spoken': 'X’inhu? M?għandix.', 'mt_standard': 'Z\u0307mien',
                                       'en_definition': 'What’s this? Are?you?'})
        self.assertEqual(row['mt_spoken'], "X'inhu? M'għandix.")
        self.assertEqual(row['mt_standard'], 'Żmien')
        self.assertEqual(row['en_definition'], 'What’s this? Are?you?')
        self.assertTrue(gate1([], {'mt_spoken': 'X’inhu?'}))

    def test_sliding_queue_retries_partial_commits_quarantine_and_max_words(self):
        folder = self.scratch / 'mock-queue'; folder.mkdir()
        clean = [{**i, 'is_enriched': False} for i in self.index]
        selected = queue.candidate_queue(clean, (), wave='1')[:5]
        store = self.worker_store()
        store.index = clean
        store.packet = lambda key: queue.assemble_packet(store.entries[key])
        counts, calls = {}, []
        bad_key = selected[0]['exact_key']
        flaky_key = selected[1]['exact_key']
        def worker(tag, packets, timeout):
            calls.append((packets, timeout))
            valid, errors = {}, {}
            for packet in packets:
                key = packet['exact_key']
                counts[key] = counts.get(key, 0) + 1
                if key == bad_key or (key == flaky_key and counts[key] == 1):
                    errors[key] = 'simulated invalid'
                else:
                    valid[key] = {'exact_key': key}
            return {'validated_entries': valid, 'errors': errors}
        with patch.object(queue, 'source_store', return_value=store), patch.object(queue, 'process_micro_batch', side_effect=worker), patch.object(queue, 'publish_and_validate', return_value={'enriched_count': 104}) as publish, patch.object(queue, 'OVERLAY_DIR', folder), patch.object(queue, 'QUARANTINE', folder / 'quarantine.json'):
            result = queue.run_queue(slots=2, batch_size=4, max_words=5, milestone_interval=2, wave='1')
        self.assertEqual(result, {'selected': 5, 'validated': 4, 'quarantined': 1, 'enriched_count': 104})
        self.assertEqual(counts[bad_key], 4)
        self.assertEqual(counts[flaky_key], 2)
        self.assertTrue(all(len(p) <= 2 and t == 360 for p, t in calls if t != 420))
        self.assertGreaterEqual(publish.call_count, 2)
        self.assertEqual(json.loads((folder / 'quarantine.json').read_text(encoding='utf-8'))[bad_key]['retries'], 3)
        self.assertEqual(len(list(folder.glob('phase2_queue_*.json'))), 4)

    def test_sliding_queue_refills_before_slow_slot_finishes(self):
        folder = self.scratch / 'mock-refill'; folder.mkdir()
        clean = [{**i, 'is_enriched': False} for i in self.index]
        store = self.worker_store()
        store.index = clean
        store.packet = lambda key: queue.assemble_packet(store.entries[key])
        selected = queue.candidate_queue(clean, (), wave='1')[:3]
        first, third = selected[0]['exact_key'], selected[2]['exact_key']
        refilled = threading.Event()
        def worker(tag, packets, timeout):
            key = packets[0]['exact_key']
            if key == first:
                self.assertTrue(refilled.wait(5), 'Sliding refill waited for slow peer')
            if key == third:
                refilled.set()
            return {'validated_entries': {key: {'exact_key': key}}, 'errors': {}}
        with patch.object(queue, 'source_store', return_value=store), patch.object(queue, 'process_micro_batch', side_effect=worker), patch.object(queue, 'publish_and_validate', return_value={'enriched_count': 103}), patch.object(queue, 'OVERLAY_DIR', folder), patch.object(queue, 'QUARANTINE', folder / 'quarantine.json'):
            result = queue.run_queue(slots=2, batch_size=1, max_words=3)
        self.assertEqual(result['validated'], 3)

    def test_ab_benchmark_dispatch_retry_metrics_and_position_denominators(self):
        folder = self.scratch / 'mock-ab'; folder.mkdir()
        clean = [{**i, 'is_enriched': False} for i in self.index]
        store = self.worker_store()
        store.index = clean
        store.packet = lambda key: queue.assemble_packet(store.entries[key])
        seen, counter, lock = [], [0], threading.Lock()
        def worker(tag, packets, timeout):
            with lock:
                counter[0] += 1
                number = counter[0]
                seen.append((tag, len(packets), timeout))
            valid, errors = {}, {}
            for position, packet in enumerate(packets, 1):
                key = packet['exact_key']
                if 'retry' not in tag and position == len(packets):
                    errors[key] = 'retry me'
                else:
                    valid[key] = {**deepcopy(self.overlays['dar']), 'exact_key': key}
            return {'batch_tag': tag, 'words': [p['exact_key'] for p in packets],
                    'validated_entries': valid, 'errors': errors,
                    'positions': {p['exact_key']: n for n, p in enumerate(packets, 1)},
                    'elapsed_sec': 10, 'started_monotonic': number, 'finished_monotonic': number + 10,
                    'input_chars': len(queue.build_prompt(packets))}
        with patch.object(benchmark, 'source_store', return_value=store), patch.object(benchmark, 'process_micro_batch', side_effect=worker), patch.object(benchmark, 'publish_and_validate', return_value={'enriched_count': 180}), patch.object(benchmark, 'OUTPUT', folder / 'output.json'), patch.object(benchmark, 'REPORT', folder / 'report.json'), patch.object(benchmark, 'QUARANTINE', folder / 'quarantine.json'):
            report = benchmark.run_benchmark(overlays={})
        initial = [(size, timeout) for tag, size, timeout in seen if 'retry' not in tag]
        self.assertEqual(Counter(initial), {(4, 420): 10, (8, 840): 5})
        self.assertTrue(all(size <= 2 and timeout == 360 for tag, size, timeout in seen if 'retry' in tag))
        self.assertEqual(report['completed'], 80)
        self.assertEqual(report[benchmark.ARM_A]['first_pass_validated'], 30)
        self.assertEqual(report[benchmark.ARM_B]['first_pass_validated'], 35)
        self.assertEqual(report[benchmark.ARM_A]['completed'], 40)
        self.assertEqual(report[benchmark.ARM_B]['completed'], 40)
        positions = report['arm_b_intra_batch_position_analysis']
        self.assertEqual(positions['positions_1_to_4']['first_pass_rate'], 1)
        self.assertEqual(positions['positions_5_to_8']['first_pass_rate'], .75)
        self.assertEqual(positions['positions_5_to_8']['selected'], 20)
        self.assertGreater(report[benchmark.ARM_B]['input_chars_savings_pct_vs_arm_a'], 0)
        self.assertEqual(len(json.loads((folder / 'output.json').read_text(encoding='utf-8'))), 80)


if __name__ == '__main__':
    unittest.main()
