"""Conservative text normalization. Only whitespace/line-ending/Unicode-
representation cleanup -- never anything that could alter the meaning of
business content. Numbers, currencies, codes, quantities, and dates
pass through completely unchanged: nothing here touches digits,
punctuation, or letters, only redundant whitespace and equivalent
Unicode encodings of the same characters.
"""

import re
import unicodedata

_REPEATED_SPACES_OR_TABS = re.compile(r"[ \t]{2,}")
_THREE_OR_MORE_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    # NFC: canonicalizes equivalent Unicode representations (e.g. a
    # precomposed accented character vs. the same character built from
    # a base letter + combining accent) without changing what character
    # it represents -- safe for any script, and never touches ASCII
    # digits/currency symbols/codes at all.
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _REPEATED_SPACES_OR_TABS.sub(" ", text)
    text = _THREE_OR_MORE_BLANK_LINES.sub("\n\n", text)
    return text.strip()

