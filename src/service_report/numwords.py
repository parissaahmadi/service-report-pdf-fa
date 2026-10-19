"""Integer -> words, in Persian and English (for amounts written out in full)."""

from __future__ import annotations

_FA_ONES = (
    "صفر", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده",
    "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده",
)  # fmt: skip
_FA_TENS = ("", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود")
_FA_HUNDREDS = (
    "", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد",
)  # fmt: skip
_FA_SCALES = ("", "هزار", "میلیون", "میلیارد", "تریلیون")

_EN_ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen",
)  # fmt: skip
_EN_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_EN_SCALES = ("", "thousand", "million", "billion", "trillion")

LIMIT = 10**15  # exclusive upper bound


def _check(n: int) -> None:
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("integer required")
    if abs(n) >= LIMIT:
        raise ValueError(f"|n| must be below {LIMIT}")


def _fa_below_1000(n: int) -> str:
    parts: list[str] = []
    h, r = divmod(n, 100)
    if h:
        parts.append(_FA_HUNDREDS[h])
    if r:
        if r < 20:
            parts.append(_FA_ONES[r])
        else:
            t, o = divmod(r, 10)
            parts.append(_FA_TENS[t])
            if o:
                parts.append(_FA_ONES[o])
    return " و ".join(parts)


def to_words_fa(n: int) -> str:
    """Persian words. 1000 is written ``یک هزار`` (explicit, as on financial documents)."""
    _check(n)
    if n == 0:
        return _FA_ONES[0]
    if n < 0:
        return "منفی " + to_words_fa(-n)
    groups: list[int] = []
    while n:
        n, g = divmod(n, 1000)
        groups.append(g)
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if not g:
            continue
        w = _fa_below_1000(g)
        parts.append(f"{w} {_FA_SCALES[i]}" if i else w)
    return " و ".join(parts)


def _en_below_1000(n: int) -> str:
    words: list[str] = []
    h, r = divmod(n, 100)
    if h:
        words += [_EN_ONES[h], "hundred"]
    if r:
        if r < 20:
            words.append(_EN_ONES[r])
        else:
            t, o = divmod(r, 10)
            words.append(_EN_TENS[t] + (f"-{_EN_ONES[o]}" if o else ""))
    return " ".join(words)


def to_words_en(n: int) -> str:
    _check(n)
    if n == 0:
        return _EN_ONES[0]
    if n < 0:
        return "minus " + to_words_en(-n)
    groups: list[int] = []
    while n:
        n, g = divmod(n, 1000)
        groups.append(g)
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        if groups[i]:
            w = _en_below_1000(groups[i])
            parts.append(f"{w} {_EN_SCALES[i]}" if i else w)
    return " ".join(parts)
