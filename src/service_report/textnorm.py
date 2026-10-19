"""Text normalisation helpers for Persian text.

Everything here is pure stdlib and operates on *logical* order strings.
"""

from __future__ import annotations

import unicodedata

ZWNJ = "‌"
ZWJ = "‍"

# Arabic letter variants that frequently sneak in from Arabic keyboards.
_LETTER_MAP = str.maketrans(
    {
        "ي": "ی",  # ARABIC YEH            -> FARSI YEH
        "ى": "ی",  # ALEF MAKSURA          -> FARSI YEH
        "ك": "ک",  # ARABIC KAF            -> KEHEH
    }
)

_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_TO_FA = str.maketrans("0123456789" + _AR_DIGITS, _FA_DIGITS * 2)
_TO_EN = str.maketrans(_FA_DIGITS + _AR_DIGITS, "0123456789" * 2)


def normalize(text: str) -> str:
    """Unify Arabic/Persian letter variants and drop tatweel.

    ZWNJ is kept: it is meaningful in Persian orthography.
    """
    return text.translate(_LETTER_MAP).replace("ـ", "")


def to_fa_digits(text: str) -> str:
    """ASCII and Arabic-Indic digits -> Persian digits."""
    return text.translate(_TO_FA)


def to_en_digits(text: str) -> str:
    """Persian and Arabic-Indic digits -> ASCII digits."""
    return text.translate(_TO_EN)


def convert_digits(text: str, style: str) -> str:
    """Apply a digit style: ``"fa"`` or ``"en"``."""
    if style == "fa":
        return to_fa_digits(text)
    if style == "en":
        return to_en_digits(text)
    raise ValueError(f"unknown digit style: {style!r}")


def strip_marks(text: str) -> str:
    """Remove combining marks (harakat). The layout engine does not position them."""
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def has_rtl(text: str) -> bool:
    """True if the text contains at least one strong right-to-left character."""
    return any(unicodedata.bidirectional(c) in ("R", "AL") for c in text)


def clean_for_layout(text: str) -> str:
    """The full pre-layout cleanup used by the renderer."""
    return strip_marks(normalize(text))
