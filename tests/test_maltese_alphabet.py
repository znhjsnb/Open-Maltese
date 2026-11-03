"""Regression tests for Maltese graphemes, collation and search contracts."""
import unittest

from scripts.maltese_alphabet import (
    MALTESE_ALPHABET_30, MALTESE_UI_BUCKETS_30, SUN_CONSONANTS,
    compare_maltese_headwords, get_letter_bucket_30, get_ui_letter_bucket,
    maltese_sort_key, normalize_ascii_tolerant, normalize_exact_search,
    normalize_nfc, strip_definite_article, tokenize_maltese_graphemes,
    tokenize_root_consonants,
)


class AlphabetTests(unittest.TestCase):
    def test_alphabet_and_ui_buckets(self):
        expected = tuple('A B Ċ D E F Ġ G GĦ H Ħ I IE J K L M N O P Q R S T U V W X Ż Z'.split())
        self.assertEqual(MALTESE_ALPHABET_30, expected)
        self.assertEqual(len(set(MALTESE_ALPHABET_30)), 30)
        self.assertEqual(MALTESE_UI_BUCKETS_30,
                         tuple(x for x in expected if x != 'IE') + ('#',))
        self.assertEqual(len(set(MALTESE_UI_BUCKETS_30)), 30)

    def test_sun_consonants(self):
        self.assertEqual(set(SUN_CONSONANTS), set('ċdnrstxżz'))
        self.assertEqual(len(SUN_CONSONANTS), 9)
        self.assertNotIn('j', SUN_CONSONANTS)

    def test_normalize_apostrophes(self):
        for apostrophe in ('’', '‘', 'ʼ'):
            with self.subTest(apostrophe=apostrophe):
                self.assertEqual(normalize_nfc('m' + apostrophe + 'għandix'), "m'għandix")

    def test_normalize_dashes_whitespace_and_composition(self):
        self.assertEqual(normalize_nfc(' il–ktieb\t\n l—iskola  '), 'il-ktieb l-iskola')
        self.assertEqual(normalize_nfc('  G\u0307abra\u00a0kafe\u0300 '), 'Ġabra kafè')
        self.assertEqual(normalize_nfc(''), '')
        text = "Għajn ’ il–ktieb"
        self.assertEqual(normalize_nfc(normalize_nfc(text)), normalize_nfc(text))

    def test_graphemes_longest_prefix_and_case(self):
        cases = {
            'għg': ['għ', 'g'], 'iei': ['ie', 'i'],
            'ċġħż': ['ċ', 'ġ', 'ħ', 'ż'],
            'Għawdex': ['għ', 'a', 'w', 'd', 'e', 'x'],
            'GĦAJN': ['għ', 'a', 'j', 'n'], 'Iebes': ['ie', 'b', 'e', 's'],
            'qiegħed': ['q', 'ie', 'għ', 'e', 'd'],
            'għargħar': ['għ', 'a', 'r', 'għ', 'a', 'r'],
            'CY': ['c', 'y'], '': [],
        }
        for word, tokens in cases.items():
            with self.subTest(word=word):
                self.assertEqual(tokenize_maltese_graphemes(word), tokens)

    def test_graphemes_accents(self):
        for word, folded in [('kafè', 'kafe'), ('libertà', 'liberta'), ('però', 'pero')]:
            with self.subTest(word=word):
                self.assertEqual(tokenize_maltese_graphemes(word), list(folded))
                self.assertEqual(tokenize_maltese_graphemes(word, fold_accents=False), list(word))

    def test_graphemes_non_letters(self):
        self.assertEqual(tokenize_maltese_graphemes("m’għandix-2 !"),
                         ['m', 'għ', 'a', 'n', 'd', 'i', 'x'])
        self.assertEqual(tokenize_maltese_graphemes("m’għandix-2 !", include_non_letters=True),
                         ['m', "'", 'għ', 'a', 'n', 'd', 'i', 'x', '-', '2', ' ', '!'])

    def test_root_radicals(self):
        cases = {
            'k-t-b': ['k', 't', 'b'], 'għ-l-m': ['għ', 'l', 'm'],
            'b-għ-d': ['b', 'għ', 'd'], 'q-r-j': ['q', 'r', 'j'],
            't-r-ġ-m': ['t', 'r', 'ġ', 'm'],
            'għ-r-għ-x': ['għ', 'r', 'għ', 'x'],
        }
        for root, radicals in cases.items():
            with self.subTest(root=root):
                actual = tokenize_root_consonants(root)
                self.assertEqual(actual, radicals)
                if 'għ' in root:
                    self.assertNotIn('g', actual)
                    self.assertNotIn('ħ', actual)

    def test_articles(self):
        cases = {
            'il-ktieb': ('ktieb', 'il-'), 'l-iskola': ('iskola', 'l-'),
            'ix-xemx': ('xemx', 'ix-'), 'iż-żmien': ('żmien', 'iż-'),
            'il-jum': ('jum', 'il-'), 'ktieb': ('ktieb', None),
            'ij-jum': ('ij-jum', None), 'il-': ('il-', None), '': ('', None),
            'IL-Ktieb': ('Ktieb', 'IL-'),
        }
        for word, result in cases.items():
            with self.subTest(word=word):
                self.assertEqual(strip_definite_article(word), result)

    def test_all_assimilated_articles(self):
        for consonant in SUN_CONSONANTS:
            with self.subTest(consonant=consonant):
                prefix = 'i' + consonant + '-'
                self.assertEqual(strip_definite_article(prefix + consonant + 'a'),
                                 (consonant + 'a', prefix))

    def test_fused_prepositions_are_opt_in(self):
        for word, stem, prefix in [('fil-ktieb', 'ktieb', 'fil-'),
                                   ('għall-iskola', 'iskola', 'għall-')]:
            with self.subTest(word=word):
                self.assertEqual(strip_definite_article(word), (word, None))
                self.assertEqual(strip_definite_article(word, include_fused_prepositions=True),
                                 (stem, prefix))

    def test_letter_and_ui_buckets(self):
        self.assertEqual(get_letter_bucket_30('Għawdex'), 'GĦ')
        self.assertEqual(get_ui_letter_bucket('Għawdex')['bucket'], 'GĦ')
        self.assertEqual(get_letter_bucket_30('iebes'), 'IE')
        self.assertEqual(get_ui_letter_bucket('iebes'), {'bucket': 'I', 'sub_prefix': 'ie'})
        for letter in MALTESE_ALPHABET_30:
            with self.subTest(letter=letter):
                self.assertEqual(get_letter_bucket_30(letter.lower()), letter)

    def test_foreign_and_nonletter_buckets(self):
        for word in ('123', '!kelma', 'Cat', 'Yacht', ''):
            with self.subTest(word=word):
                self.assertEqual(get_letter_bucket_30(word), '#')
                self.assertEqual(get_ui_letter_bucket(word), {'bucket': '#', 'sub_prefix': None})

    def test_bucket_article_stripping(self):
        self.assertEqual(get_letter_bucket_30('il-ktieb'), 'I')
        self.assertEqual(get_letter_bucket_30('il-ktieb', strip_article=True), 'K')
        self.assertEqual(get_ui_letter_bucket('l-iebes', strip_article=True),
                         {'bucket': 'I', 'sub_prefix': 'ie'})


class CollationTests(unittest.TestCase):
    def assert_order(self, words, **options):
        self.assertEqual(sorted(reversed(words), key=lambda w: maltese_sort_key(w, **options)), words)
        for a, b in zip(words, words[1:]):
            with self.subTest(a=a, b=b, options=options):
                self.assertEqual(compare_maltese_headwords(a, b, **options), -1)
                self.assertEqual(compare_maltese_headwords(b, a, **options), 1)
        for word in words:
            self.assertEqual(compare_maltese_headwords(word, word, **options), 0)

    def test_dms200_letter_sequences(self):
        for sequence in (['B', 'Ċ', 'C', 'D'], ['F', 'Ġ', 'G', 'GĦ', 'H', 'Ħ', 'I'],
                         ['W', 'X', 'Y', 'Ż', 'Z']):
            self.assert_order(sequence, mode='dms200')

    def test_dms200_ie_is_i_plus_e(self):
        self.assert_order(['id', 'iebes', 'ifittex'])

    def test_strict_30_ie_is_separate(self):
        self.assert_order(['I', 'IE', 'J'], mode='strict_30')
        self.assert_order(['ifittex', 'iebes', 'jaqra'], mode='strict_30')

    def test_punctuation_breaks_primary_ties(self):
        for punctuated in ('a-b', "a'b"):
            with self.subTest(punctuated=punctuated):
                self.assertEqual(maltese_sort_key('ab')[0], maltese_sort_key(punctuated)[0])
                self.assert_order(['ab', punctuated])

    def test_article_ties_preserve_stem_order(self):
        for mode in ('dms200', 'strict_30'):
            with self.subTest(mode=mode):
                bare = maltese_sort_key('ktieb', mode=mode, strip_article=True)
                article = maltese_sort_key('il-ktieb', mode=mode, strip_article=True)
                self.assertEqual(bare[:4], article[:4])
                self.assertEqual(bare[4:], (0, 'ktieb'))
                self.assertEqual(article[4:], (1, 'il-ktieb'))
                self.assert_order(['ktieb', 'il-ktieb'], mode=mode, strip_article=True)
                # O precedes T: stripping an article cannot reverse primary stem order.
                self.assert_order(['kotba', 'ktieb', 'il-ktieb'], mode=mode, strip_article=True)

    def test_article_stripping_is_opt_in_and_keeps_original_spelling(self):
        self.assert_order(['il-ktieb', 'ktieb'])
        self.assertNotEqual(maltese_sort_key('ktieb')[0], maltese_sort_key('il-ktieb')[0])
        key = maltese_sort_key(' il–ktieb ', strip_article=True)
        self.assertEqual(key[-2:], (1, 'il-ktieb'))
        self.assertEqual(compare_maltese_headwords('il–ktieb', 'il-ktieb', strip_article=True), 0)
        self.assertNotEqual(maltese_sort_key('l-ktieb', strip_article=True), key)

    def test_accent_and_case_secondary_order(self):
        self.assert_order(['kafe', 'kafè'])
        self.assert_order(['Għajn', 'għajn'])
        self.assert_order(['Marsa', 'marsa'])
        self.assertEqual(compare_maltese_headwords('G\u0307abra', 'Ġabra'), 0)

    def test_empty_digits_and_unknown_letters_are_comparable(self):
        self.assert_order(['', '0', '2', '9', 'a', 'Ω'])

    def test_article_phonological_context(self):
        known = {'xemx', 'dar', 'skola', 'ktieb', 'kelb', 'għajn'}
        for surface, stem in [('fix-xemx', 'xemx'), ('bid-dar', 'dar'),
                              ('x-xemx', 'xemx'), ('d-dar', 'dar'), ('lill-kelb', 'kelb'),
                              ('l-iskola', 'skola'), ('fl-iskola', 'skola'),
                              ('bil-iskola', 'skola'), ('mal-iskola', 'skola'),
                              ('tal-iskola', 'skola'), ('għall-iskola', 'skola')]:
            with self.subTest(surface=surface):
                self.assertEqual(strip_definite_article(surface, include_fused_prepositions=True,
                                                       known_lemmas=known)[0], stem)
        for surface in ('ix-ktieb', 'fix-ktieb', 'bid-xemx', 'il-dar', 'fil-xemx', 'lill-dar'):
            self.assertEqual(strip_definite_article(surface, include_fused_prepositions=True,
                                                   known_lemmas=known), (surface, None))
        self.assertEqual(strip_definite_article('l-iskola', known_lemmas=known | {'iskola'}), ('iskola', 'l-'))
        self.assertEqual(strip_definite_article('l-iktieb', known_lemmas=known)[0], 'iktieb')

    def test_all_fused_and_apocopated_sun_articles(self):
        for base in ('', 'i', 'fi', 'bi', 'ma', 'ta', 'għa', 'li'):
            for consonant in SUN_CONSONANTS:
                prefix = base + consonant + '-'
                self.assertEqual(strip_definite_article(prefix + consonant + 'a',
                    include_fused_prepositions=True), (consonant + 'a', prefix))
                self.assertEqual(strip_definite_article(prefix + 'kelb',
                    include_fused_prepositions=True), (prefix + 'kelb', None))

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            maltese_sort_key('ktieb', mode='unknown')
        with self.assertRaises(ValueError):
            compare_maltese_headwords('a', 'b', mode='unknown')


class SearchNormalizationTests(unittest.TestCase):
    def test_exact_retains_maltese_distinctions(self):
        for original, ascii_key in [('żminijiet', 'zminijiet'), ('għajn', 'ghajn'),
                                     ('maħfra', 'mahfra'), ('ċikkulata', 'cikkulata'),
                                     ('ġabra', 'gabra')]:
            with self.subTest(original=original):
                self.assertEqual(normalize_exact_search(original.upper()), original)
                self.assertNotEqual(normalize_exact_search(original), ascii_key)
                self.assertEqual(normalize_ascii_tolerant(original.upper()), ascii_key)

    def test_apostrophes_and_optional_punctuation_removal(self):
        self.assertEqual(normalize_exact_search(' M’GĦANDIX '), "m'għandix")
        self.assertEqual(''.join(tokenize_maltese_graphemes("m'għandix")), 'mgħandix')
        self.assertEqual(normalize_ascii_tolerant("m'għandix"), 'mghandix')
        self.assertEqual(normalize_ascii_tolerant(' M’GĦANDIX ', strip_punctuation=False), "m'ghandix")
        self.assertEqual(normalize_exact_search(' Il–Ktieb  '), 'il-ktieb')
        self.assertEqual(normalize_ascii_tolerant(' Il–Ktieb  '), 'ilktieb')

    def test_accented_vowels_and_nfc(self):
        self.assertEqual(normalize_exact_search('KAFE\u0300'), 'kafè')
        self.assertEqual(normalize_ascii_tolerant('KAFE\u0300'), 'kafe')
        self.assertEqual(normalize_exact_search(''), '')
        self.assertEqual(normalize_ascii_tolerant(''), '')


if __name__ == '__main__':
    unittest.main()
