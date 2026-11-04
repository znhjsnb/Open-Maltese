"""Observable fusion boundaries and refinement compatibility, using isolated data."""
from copy import deepcopy
import unittest

from scripts.sense_display import display_layer, pos_class, refresh_display
from scripts.phase2_enrichment import translations_for
from scripts.run_phase2_sliding_queue import candidate_queue, validate_worker_refinements


def analysis(source, name, gloss='abacus', pos='NOUN', roots=(), **fields):
    return dict(id=name, source=source, pos=pos, roots=list(roots), **fields,
                senses=[dict(id=name + ':s1', source=source, pos=pos, en_definition=gloss,
                             definition_origin='licensed_source', zh_definition='算盘；计数工具。')])


def entry(*analyses):
    return {'lexeme_analyses': list(analyses), 'senses': []}


class SenseDisplayTests(unittest.TestCase):
    def test_pos_aliases_unknowns_and_whitespace(self):
        cases = {'NOUN':'noun', 'VERB':'verb', 'adjective':'adj', 'adverb':'adv',
                 'ADP':'prep', 'preposition':'prep', 'pronoun':'pron', 'SCONJ':'conj',
                 'CCONJ':'conj', 'conjunction':'conj', 'numeral':'num', 'interjection':'intj',
                 'particle':'part', 'article':'art', 'PROPN':'propn', 'name':'propn',
                 'AUX':'aux', 'DET':'det', ' X-Custom ':'x-custom', None:'', '  ':''}
        for value, expected in cases.items():
            self.assertEqual(pos_class(value), expected)

    def test_cross_source_fusion_preserves_source_and_translation_identities(self):
        a, b = analysis('gabra','a',' AbAcUs '), analysis('kaikki','b','abacus',pos='noun')
        b['senses'][0].update(en_explanation='An abacus is a tool used for counting.', mt_definition='Għodda għall-għadd.')
        e = entry(a,b); before = deepcopy(e)
        senses, guide = display_layer(e)
        self.assertEqual(e, before)
        self.assertIsNone(guide)
        self.assertEqual(len(senses), 1)
        self.assertEqual(senses[0]['sources'], ['gabra','kaikki'])
        self.assertEqual(senses[0]['analysis_ids'], ['a','b'])
        self.assertEqual(senses[0]['sense_ids'], ['a:s1','b:s1'])
        self.assertEqual(senses[0]['en_definition'], ' AbAcUs ')
        self.assertEqual(senses[0]['en_explanation'], b['senses'][0]['en_explanation'])
        self.assertEqual(len(senses[0]['translations']), 2)
        self.assertEqual(display_layer(e), (senses, guide))

    def test_nfc_whitespace_and_case_match_but_punctuation_remains_meaningful(self):
        self.assertEqual(len(display_layer(entry(analysis('gabra','a',' Cafe\u0301   tool'),
            analysis('kaikki','b','café tool')))[0]), 1)
        for a,b in [('nightmare?','nightmare'),('word.','word')]:
            self.assertEqual(len(display_layer(entry(analysis('gabra','a',a),analysis('kaikki','b',b)))[0]), 2)

    def test_same_source_homographs_and_conflicting_roots_never_merge(self):
        a, b, c = analysis('gabra','a'), analysis('gabra','b'), analysis('kaikki','c')
        self.assertEqual(len(display_layer(entry(a,b,c))[0]), 3)
        for field, left, right in [('roots',['d-j-r'],['d-w-r']),('gender','m.','f.'),
                                   ('stratum','semitic','english'),('collectivity','kollettiv','singulattiv')]:
            a, b = analysis('gabra','a'), analysis('kaikki','b')
            a[field], b[field] = left, right
            self.assertEqual(len(display_layer(entry(a,b))[0]), 2)

    def teaching(self, pos='noun', en='abacus', zh='算盘'):
        return dict(id='teaching', pos=pos, en_definition=en, zh_definition=zh,
                    mt_definition='Għodda għall-għadd.', definition_origin='authored_pedagogical')

    def test_single_group_fuses_only_matching_teaching_and_never_overwrites_source(self):
        e = entry(analysis('gabra','a'),analysis('kaikki','b'))
        e['senses'] = [self.teaching()]
        g = display_layer(e)[0][0]
        self.assertEqual(g['teaching_mode'],'fused')
        self.assertEqual(g['en_definition'],'abacus')
        for teaching in (self.teaching('verb'),self.teaching(en='to run',zh='跑步')):
            e['senses'] = [teaching]
            self.assertNotIn('teaching',display_layer(e)[0][0])

    def test_homograph_teaching_binds_only_to_matching_noun_not_rooted_verbs(self):
        e = entry(analysis('gabra','a','house','noun',['d-j-r']),
                  analysis('gabra','b','to reside','verb',['d-j-r']),
                  analysis('gabra','c','to turn','verb',['d-w-r']))
        e['senses'] = [self.teaching(en='house',zh='房屋')]
        senses, guide = display_layer(e)
        self.assertIsNone(guide)
        self.assertEqual(senses[0]['teaching_mode'],'bound')
        self.assertTrue(all('teaching' not in s for s in senses[1:]))

    def test_ordinary_polysemy_guide_is_unnumbered_and_omitted_when_all_have_mt(self):
        a = analysis('gabra','a','to abandon','verb')
        a['senses'].append(dict(a['senses'][0],id='a:s2',en_definition='to desert'))
        e = entry(a); e['senses'] = [self.teaching('verb','to abandon','抛弃')]
        senses, guide = display_layer(e)
        self.assertEqual(len(senses),2)
        self.assertEqual(guide['analysis_ids'],['a'])
        self.assertTrue(all('teaching' not in s for s in senses))
        for s in a['senses']: s['mt_definition']='Iħalli warajh.'
        self.assertIsNone(display_layer(e)[1])

    def test_optional_refinement_contract_is_legacy_compatible_and_new_workers_strict(self):
        row = dict(pos='noun',en_definition='abacus',zh_definition='算盘')
        self.assertTrue(translations_for({'sense_translations':[row]}))
        aliases = [dict(row,pos='name'),dict(row,pos='propn',zh_definition='另一来源的独立译释')]
        self.assertEqual(len(translations_for({'sense_translations':aliases})),2)
        with self.assertRaises(ValueError): validate_worker_refinements({'sense_translations':[row]})
        complete = dict(row,en_explanation='An abacus is a tool used for counting.',mt_definition='Għodda għall-għadd.')
        validate_worker_refinements({'sense_translations':[complete]})
        self.assertEqual(translations_for({'sense_translations':[complete]})[('noun','abacus')],complete)
        for value in ('', None, [], 3):
            with self.assertRaises(ValueError): translations_for({'sense_translations':[dict(complete,en_explanation=value)]})
        for value in ('abacus','A short gloss','An abacus is a tool used for counting'):
            with self.assertRaises(ValueError): validate_worker_refinements({'sense_translations':[dict(complete,en_explanation=value)]})

    def test_tier3_evidence_gaps_excluded_and_selection_is_stable(self):
        indices = [dict(exact_key=k,tier=3,gloss_en=g) for k,g in [('a',['abacus']),('b',[]),('c',['house'])]]
        self.assertEqual([i['exact_key'] for i in candidate_queue(indices,wave='tier3')],['a','c'])
        self.assertEqual([i['exact_key'] for i in candidate_queue(indices+indices,wave='tier3')],['a','c'])
        self.assertEqual(candidate_queue(indices,enriched=['a'],quarantined=['c'],wave='tier3'),[])
        # A misleading index gloss must not create a source selector at dispatch.
        sources = {'a':entry(), 'b':entry(), 'c':entry(analysis('gabra','c','house'))}
        self.assertEqual([i['exact_key'] for i in candidate_queue(indices,wave='tier3',entries=sources)],['c'])
