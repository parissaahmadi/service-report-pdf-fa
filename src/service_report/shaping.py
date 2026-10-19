"""Arabic-script contextual shaping (logical order -> presentation forms).

The form tables are *derived from the Unicode database* at import time
(``unicodedata.decomposition`` of the Arabic Presentation Forms blocks), so there
is no hand-typed code point table to get wrong.

Scope: isolated / initial / medial / final forms, lam-alef ligatures, ZWNJ / ZWJ.
Not covered: other ligatures, mark positioning (see ``textnorm.strip_marks``).
"""

from __future__ import annotations

import unicodedata as ud

ZWNJ = "‌"
ZWJ = "‍"
LAM = "ل"

_BLOCKS = ((0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
_TAGS = ("isolated", "initial", "medial", "final")
_ALEFS = ("\u0622", "\u0623", "\u0625", "\u0627")  # only these form lam-alef (FEF5-FEFC)


def _build() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    forms: dict[str, dict[str, str]] = {}
    lam_alef: dict[str, dict[str, str]] = {}  # alef variant -> {"isolated"/"final": glyph}
    for lo, hi in _BLOCKS:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            dec = ud.decomposition(ch)
            if not dec.startswith("<"):
                continue
            tag_s, _, rest = dec.partition(" ")
            tag = tag_s.strip("<>")
            if tag not in _TAGS:
                continue
            parts = [chr(int(x, 16)) for x in rest.split()]
            if len(parts) == 1:
                forms.setdefault(parts[0], {}).setdefault(tag, ch)
            elif len(parts) == 2 and parts[0] == LAM and parts[1] in _ALEFS and tag in ("isolated", "final"):
                lam_alef.setdefault(parts[1], {}).setdefault(tag, ch)
    return forms, lam_alef


FORMS, LAM_ALEF = _build()


def joining_type(ch: str) -> str:
    """``D`` dual-joining, ``R`` right-joining, ``T`` transparent, ``U`` non-joining."""
    if ch == ZWJ:
        return "D"
    if ch == ZWNJ:
        return "U"
    forms = FORMS.get(ch)
    if forms:
        if "initial" in forms and "medial" in forms:
            return "D"
        if "final" in forms:
            return "R"
        return "U"
    if ud.category(ch) == "Mn":
        return "T"
    if ch == "ـ":  # tatweel joins on both sides and has no other form
        return "D"
    return "U"


def shape(text: str) -> str:
    """Replace joining letters by presentation forms. Output is still logical order."""
    # Token = [glyph options or literal char, joining type, kind]
    tokens: list[list] = []
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if ch == LAM and nxt in LAM_ALEF:
            tokens.append([LAM_ALEF[nxt], "R", "lig"])
            i += 2
            continue
        tokens.append([ch, joining_type(ch), "chr"])
        i += 1

    out: list[str] = []
    for k, (glyph, jt, kind) in enumerate(tokens):
        if kind == "chr" and glyph in (ZWNJ, ZWJ):
            continue  # joiners only influence neighbours
        if jt == "T" or (kind == "chr" and jt == "U"):
            out.append(glyph if kind == "chr" else glyph["isolated"])
            continue

        prev = next((t for t in reversed(tokens[:k]) if t[1] != "T"), None)
        following = next((t for t in tokens[k + 1 :] if t[1] != "T"), None)
        joins_prev = jt in ("D", "R") and prev is not None and prev[1] == "D"
        joins_next = jt == "D" and following is not None and following[1] in ("D", "R")

        if kind == "lig":
            out.append(glyph["final"] if joins_prev else glyph["isolated"])
            continue
        if glyph == "ـ":
            out.append(glyph)
            continue

        forms = FORMS[glyph]
        if joins_prev and joins_next:
            want = "medial"
        elif joins_prev:
            want = "final"
        elif joins_next:
            want = "initial"
        else:
            want = "isolated"
        out.append(forms.get(want) or forms.get("isolated") or glyph)
    return "".join(out)
