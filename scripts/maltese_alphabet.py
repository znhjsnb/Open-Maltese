"""Deterministic Maltese graphemes, search keys and dictionary ordering.

DMS 200:2009 section 4.1 treats ie as i+e for data processing; strict_30
is an explicit alternative. Secondary weights below are an application policy,
not a claim to implement every Unicode collation tailoring.
"""
import unicodedata

MALTESE_ALPHABET_30 = (
    'A', 'B', 'Ċ', 'D', 'E', 'F', 'Ġ', 'G', 'GĦ', 'H', 'Ħ', 'I', 'IE',
    'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V',
    'W', 'X', 'Ż', 'Z',
)
MALTESE_UI_BUCKETS_30 = tuple(x for x in MALTESE_ALPHABET_30 if x != 'IE') + ('#',)
SUN_CONSONANTS = ('ċ', 'd', 'n', 'r', 's', 't', 'x', 'ż', 'z')
_TRANSLATION = str.maketrans({
    **{x: "'" for x in '‘’‛ʼ＇′`´'},
    **{x: '-' for x in '‐‑‒–—−'},
})
_VOWELS = str.maketrans({
    c: base for base, chars in (
        ('a', 'àáâäãāăå'), ('e', 'èéêëēĕ'), ('i', 'ìíîïīĭ'),
        ('o', 'òóôöõōŏ'), ('u', 'ùúûüūŭ'),
    ) for c in chars
})


def normalize_nfc(text: str) -> str:
    """Canonical Unicode, apostrophes, dashes and whitespace; retain case."""
    return ' '.join(unicodedata.normalize('NFC', text).translate(_TRANSLATION).split())


def _fold(text: str) -> str:
    return text.translate(_VOWELS)


def tokenize_maltese_graphemes(word: str, *, fold_accents: bool = True,
                               include_non_letters: bool = False) -> list[str]:
    text = normalize_nfc(word).lower()
    if fold_accents:
        text = _fold(text)
    result = []
    i = 0
    while i < len(text):
        pair = text[i:i + 2]
        if pair in ('għ', 'ie'):
            result.append(pair)
            i += 2
        else:
            if text[i].isalpha() or include_non_letters:
                result.append(text[i])
            i += 1
    return result


def tokenize_root_consonants(root: str) -> list[str]:
    """Parse attested radicals, without inferring a root from a headword."""
    return [g for g in tokenize_maltese_graphemes(root)
            if g not in ('a', 'e', 'i', 'ie', 'o', 'u')]


def strip_definite_article(word: str, *, include_fused_prepositions: bool = False
                           ) -> tuple[str, str | None]:
    text = normalize_nfc(word)
    prefixes = ['il-', 'l-'] + ['i' + c + '-' for c in SUN_CONSONANTS]
    if include_fused_prepositions:
        prefixes += ['fil-', 'bil-', 'mal-', 'għall-', 'tal-', 'lil-']
    for prefix in sorted(prefixes, key=len, reverse=True):
        if text.lower().startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix):], text[:len(prefix)]
    return text, None


def get_letter_bucket_30(word: str, *, strip_article: bool = False) -> str:
    text = normalize_nfc(word)
    if strip_article:
        text = strip_definite_article(text)[0]
    tokens = tokenize_maltese_graphemes(text, include_non_letters=True)
    initial = tokens[0].upper() if tokens else '#'
    return initial if initial in MALTESE_ALPHABET_30 else '#'


def get_ui_letter_bucket(word: str, *, strip_article: bool = False) -> dict[str, str | None]:
    text = strip_definite_article(word)[0] if strip_article else normalize_nfc(word)
    bucket = get_letter_bucket_30(text)
    tokens = tokenize_maltese_graphemes(text, include_non_letters=True)
    if bucket == 'IE':
        return {'bucket': 'I', 'sub_prefix': 'ie'}
    sub = ''.join(tokens[:2]) if bucket != '#' and len(tokens) >= 2 and tokens[1].isalpha() else None
    return {'bucket': bucket, 'sub_prefix': sub}


def maltese_sort_key(word: str, *, mode: str = 'dms200', strip_article: bool = False) -> tuple:
    """Letters, accents, punctuation, case, article presence, original spelling.

    Punctuation is removed before primary tokenization. Digits and unknown letters
    have explicit fallback weights. Article stripping is opt-in and syntactic.
    """
    if mode not in ('dms200', 'strict_30'):
        raise ValueError('mode must be dms200 or strict_30')
    raw_text = normalize_nfc(word)
    text = raw_text
    article_prefix = None
    if strip_article:
        text, article_prefix = strip_definite_article(text)
    alphabet = list(MALTESE_ALPHABET_30)
    alphabet.insert(alphabet.index('D'), 'C')
    alphabet.insert(alphabet.index('Ż'), 'Y')
    if mode == 'dms200':
        alphabet.remove('IE')
    weights = {g.lower(): i + 1 for i, g in enumerate(alphabet)}
    letters = ''.join(c for c in text if c.isalnum())
    tokens = tokenize_maltese_graphemes(letters, include_non_letters=True)
    if mode == 'dms200':
        tokens = [part for g in tokens for part in (('i', 'e') if g == 'ie' else (g,))]
    primary = tuple((0, weights[g]) if g in weights else (1, ord(g[0])) for g in tokens)
    accents = tuple(0 if _fold(c.lower()) == c.lower() else ord(c.lower()) for c in letters)
    punctuation = tuple((i, ord(c)) for i, c in enumerate(text) if not c.isalnum())
    case = tuple(1 if c.isupper() else 0 for c in letters)
    has_article = 1 if (strip_article and article_prefix is not None) else 0
    return primary, accents, punctuation, case, has_article, raw_text


def compare_maltese_headwords(a: str, b: str, *, mode: str = 'dms200',
                              strip_article: bool = False) -> int:
    ka = maltese_sort_key(a, mode=mode, strip_article=strip_article)
    kb = maltese_sort_key(b, mode=mode, strip_article=strip_article)
    return (ka > kb) - (ka < kb)


def normalize_exact_search(text: str) -> str:
    return normalize_nfc(text).lower()


def normalize_ascii_tolerant(text: str, *, strip_punctuation: bool = True) -> str:
    text = _fold(normalize_exact_search(text)).translate(str.maketrans('ċġħż', 'cghz'))
    if strip_punctuation:
        text = ''.join(c for c in text if c.isalnum())
    return text
