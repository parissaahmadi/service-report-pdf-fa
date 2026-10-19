"""A compact implementation of the Unicode Bidirectional Algorithm (UAX #9).

Implemented: P2/P3 (optional auto direction), W1-W7, N1-N2, I1-I2, L1, L2, L4.
Not implemented: explicit embeddings/overrides/isolates (those characters are
removed), rule N0 (paired-bracket resolution), and multi-paragraph input.
The character classes come from ``unicodedata.bidirectional``.

Typical use: call ``visual(line, base)`` on a *single line* of text that is already
shaped; draw the returned string left to right.
"""

from __future__ import annotations

import unicodedata as ud

_REMOVED = {"BN", "LRE", "RLE", "PDF", "LRO", "RLO", "LRI", "RLI", "FSI", "PDI"}
_NI = {"B", "S", "WS", "ON"}

_MIRROR_PAIRS = ("()", "[]", "{}", "<>", "«»", "‹›")
MIRROR = {}
for _a, _b in _MIRROR_PAIRS:
    MIRROR[_a] = _b
    MIRROR[_b] = _a


def _strip(text: str) -> str:
    return "".join(c for c in text if ud.bidirectional(c) not in _REMOVED)


def paragraph_level(text: str, base: str = "rtl") -> int:
    """0 for LTR, 1 for RTL. ``base`` is ``"ltr"``, ``"rtl"`` or ``"auto"`` (P2/P3)."""
    if base == "ltr":
        return 0
    if base == "rtl":
        return 1
    if base != "auto":
        raise ValueError(f"unknown base direction: {base!r}")
    for c in text:
        cls = ud.bidirectional(c)
        if cls == "L":
            return 0
        if cls in ("R", "AL"):
            return 1
    return 0


def resolve_levels(text: str, base: str = "rtl") -> list[int]:
    """Resolved embedding level for each character of ``text`` (after rule L1)."""
    text = _strip(text)
    n = len(text)
    if n == 0:
        return []
    para = paragraph_level(text, base)
    sos = "R" if para else "L"
    orig = [ud.bidirectional(c) for c in text]
    t = list(orig)

    # W1: NSM takes the type of the previous character.
    for i in range(n):
        if t[i] == "NSM":
            t[i] = t[i - 1] if i else sos

    # W2: EN after AL becomes AN.   W3: AL -> R.
    last = sos
    for i in range(n):
        if t[i] in ("L", "R", "AL"):
            last = t[i]
        elif t[i] == "EN" and last == "AL":
            t[i] = "AN"
    t = ["R" if x == "AL" else x for x in t]

    # W4: single separators between numbers.
    for i in range(1, n - 1):
        if t[i] == "ES" and t[i - 1] == "EN" and t[i + 1] == "EN":
            t[i] = "EN"
        elif t[i] == "CS" and t[i - 1] == t[i + 1] and t[i - 1] in ("EN", "AN"):
            t[i] = t[i - 1]

    # W5: ET adjacent to EN becomes EN.
    i = 0
    while i < n:
        if t[i] == "ET":
            j = i
            while j < n and t[j] == "ET":
                j += 1
            if (i > 0 and t[i - 1] == "EN") or (j < n and t[j] == "EN"):
                for k in range(i, j):
                    t[k] = "EN"
            i = j
        else:
            i += 1

    # W6: leftover separators/terminators become ON.
    t = ["ON" if x in ("ES", "ET", "CS") else x for x in t]

    # W7: EN after L becomes L.
    last = sos
    for i in range(n):
        if t[i] in ("L", "R"):
            last = t[i]
        elif t[i] == "EN" and last == "L":
            t[i] = "L"

    # N1/N2: neutrals take the surrounding direction, else the embedding direction.
    emb = "R" if para else "L"

    def strong(x: str) -> str:
        return "R" if x in ("R", "EN", "AN") else "L"

    i = 0
    while i < n:
        if t[i] in _NI:
            j = i
            while j < n and t[j] in _NI:
                j += 1
            before = strong(t[i - 1]) if i > 0 else sos
            after = strong(t[j]) if j < n else sos
            resolved = before if before == after else emb
            for k in range(i, j):
                t[k] = resolved
            i = j
        else:
            i += 1

    # I1/I2: levels.
    levels = []
    for x in t:
        if para % 2 == 0:
            levels.append(para + (1 if x == "R" else 2 if x in ("AN", "EN") else 0))
        else:
            levels.append(para + (1 if x in ("L", "EN", "AN") else 0))

    # L1: separators, and whitespace before them / at end of line, take the paragraph level.
    k = n
    trailing = True
    for i in range(n - 1, -1, -1):
        if orig[i] in ("S", "B"):
            levels[i] = para
            trailing = True
        elif orig[i] == "WS" and trailing:
            levels[i] = para
        else:
            trailing = False
        k = i
    del k
    return levels


def visual(text: str, base: str = "rtl") -> str:
    """Reorder one line into left-to-right drawing order, mirroring paired punctuation."""
    text = _strip(text)
    levels = resolve_levels(text, base)
    if not text:
        return ""
    items = list(zip(text, levels, strict=True))

    # L2: reverse runs from the highest level down to the lowest odd level.
    top = max(levels)
    lowest_odd = min((lv for lv in levels if lv % 2), default=None)
    if lowest_odd is not None:
        for lvl in range(top, lowest_odd - 1, -1):
            i = 0
            while i < len(items):
                if items[i][1] >= lvl:
                    j = i
                    while j < len(items) and items[j][1] >= lvl:
                        j += 1
                    items[i:j] = items[i:j][::-1]
                    i = j
                else:
                    i += 1

    # L4: mirror at odd levels.
    return "".join(MIRROR.get(c, c) if lv % 2 else c for c, lv in items)
