"""A small hand-rolled layout engine on top of the reportlab canvas.

reportlab cannot shape or reorder Arabic-script text, so every string goes through
``textnorm -> shaping -> bidi`` and is drawn left-to-right as a visual-order string.
Line breaking happens on *logical* text first, then each line is reordered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from . import bidi, shaping, textnorm
from .i18n import Ctx, label

FONT = "SRSans"
FONT_BOLD = "SRSans-Bold"
FONT_DIR = Path(__file__).parent / "fonts"

INK = HexColor("#1b1f24")
MUTED = HexColor("#5b6470")
LINE = HexColor("#b9c0ca")
BAND = HexColor("#e9eef4")
HEAD = HexColor("#1f4e79")
HEAD_TEXT = HexColor("#ffffff")
PASS_FG, PASS_BG = HexColor("#146c2e"), HexColor("#e3f3e8")
FAIL_FG, FAIL_BG = HexColor("#a4261b"), HexColor("#fbe6e3")

_fonts_ready = False


def register_fonts() -> None:
    global _fonts_ready
    if not _fonts_ready:
        pdfmetrics.registerFont(TTFont(FONT, str(FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))
        _fonts_ready = True


# --------------------------------------------------------------------------- text


def prepare(text: str, base: str) -> str:
    """Logical text for ONE line -> visual-order string ready for ``drawString``."""
    return bidi.visual(shaping.shape(textnorm.clean_for_layout(text)), base)


def width_of(text: str, bold: bool, size: float, base: str = "ltr") -> float:
    register_fonts()
    return pdfmetrics.stringWidth(prepare(text, base), FONT_BOLD if bold else FONT, size)


def _word_width(word: str, bold: bool, size: float) -> float:
    shaped = shaping.shape(textnorm.clean_for_layout(word))
    return pdfmetrics.stringWidth(shaped, FONT_BOLD if bold else FONT, size)


def wrap(text: str, max_width: float, *, bold: bool = False, size: float = 9.5) -> list[str]:
    """Greedy word wrap of logical text. Honors ``\\n``; hard-splits over-long words."""
    register_fonts()
    font = FONT_BOLD if bold else FONT
    space = pdfmetrics.stringWidth(" ", font, size)
    lines: list[str] = []
    for para in text.split("\n"):
        cur: list[str] = []
        cur_w = 0.0
        for word in para.split(" "):
            w = _word_width(word, bold, size)
            if w > max_width:  # hard split
                if cur:
                    lines.append(" ".join(cur))
                    cur, cur_w = [], 0.0
                chunk = ""
                for ch in word:
                    if chunk and _word_width(chunk + ch, bold, size) > max_width:
                        lines.append(chunk)
                        chunk = ""
                    chunk += ch
                cur, cur_w = [chunk], _word_width(chunk, bold, size)
                continue
            add = w if not cur else space + w
            if cur and cur_w + add > max_width:
                lines.append(" ".join(cur))
                cur, cur_w = [word], w
            else:
                cur.append(word)
                cur_w += add
        lines.append(" ".join(cur))
    return lines


@dataclass
class Line:
    text: str
    base: str  # "ltr" | "rtl"


@dataclass
class Cell:
    lines: list[Line]
    align: str = "start"  # start|center|end, relative to the table direction
    bold: bool = False
    size: float = 9.0
    color: Color = INK
    fill: Color | None = None


def lead(size: float) -> float:
    return size * 1.5


# --------------------------------------------------------------------------- canvas


class NumberedCanvas(rl_canvas.Canvas):
    """Canvas that knows the total page count (two-pass 'page x of y')."""

    def __init__(self, *args, decor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._decor = decor
        self._saved_states: list[dict] = []

    def showPage(self):  # noqa: N802 (reportlab API)
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            if self._decor:
                self._decor(self, self._pageNumber, total)
            super().showPage()
        super().save()


@dataclass
class Doc:
    path: str
    ctx: Ctx
    title: str
    subject: str = ""
    keywords: str = ""
    header_cb: object = None  # callable(doc, canvas) drawing the page header
    footer_note: str = ""  # fingerprint text shown in the footer
    margin: float = 40.0
    head_h: float = 76.0
    foot_h: float = 40.0
    c: NumberedCanvas = field(init=False)
    y: float = field(init=False)

    def __post_init__(self) -> None:
        register_fonts()
        self.W, self.H = A4
        self.c = NumberedCanvas(self.path, pagesize=A4, invariant=1, decor=self._decor)
        self.c.setTitle(self.title)
        self.c.setSubject(self.subject)
        self.c.setKeywords(self.keywords)
        self.c.setAuthor("service-report-pdf-fa (sample data)")
        self.c.setCreator("service-report-pdf-fa")
        self.y = self.H - self.head_h
        self.left = self.margin
        self.right = self.W - self.margin
        self.width = self.right - self.left
        self.bottom = self.margin + self.foot_h

    # ----- page furniture
    def _decor(self, c, page: int, total: int) -> None:
        if self.header_cb:
            self.header_cb(self, c)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        fy = self.margin + 22
        c.line(self.left, fy, self.right, fy)
        pieces = []
        for lang in self.ctx.langs:
            st = self.ctx.digit_style(lang)
            tpl = label("page_of", lang)
            txt = tpl.format(p=textnorm.convert_digits(str(page), st),
                             n=textnorm.convert_digits(str(total), st))  # fmt: skip
            pieces.append((txt, "rtl" if lang == "fa" else "ltr"))
        if self.ctx.lang == "both":
            self.draw(c, pieces[0][0], self.left, self.right, self.margin + 8, "ltr", "start",
                      size=7.5, color=MUTED)  # fmt: skip
            self.draw(c, pieces[1][0], self.left, self.right, self.margin + 8, "rtl", "start",
                      size=7.5, color=MUTED)  # fmt: skip
        else:
            self.draw(c, pieces[0][0], self.left, self.right, self.margin + 8, pieces[0][1],
                      "end", size=7.5, color=MUTED)  # fmt: skip
        if self.footer_note:
            self.draw(c, self.footer_note, self.left, self.right, self.margin + 8, "ltr",
                      "center", size=6.8, color=MUTED)  # fmt: skip

    def draw(self, c, text: str, x0: float, x1: float, y: float, base: str, align: str = "start",
             *, bold: bool = False, size: float = 9.0, color: Color = INK,
             table_rtl: bool | None = None) -> None:  # fmt: skip
        """Draw one line of logical text inside [x0, x1] at baseline ``y``.

        ``align`` is relative to ``table_rtl`` (defaults to the line's own direction).
        """
        vis = prepare(text, base)
        font = FONT_BOLD if bold else FONT
        w = pdfmetrics.stringWidth(vis, font, size)
        rtl = (base == "rtl") if table_rtl is None else table_rtl
        if align == "center":
            x = x0 + (x1 - x0 - w) / 2
        elif (align == "start") == rtl:  # start of an RTL table, or end of an LTR one
            x = x1 - w
        else:
            x = x0
        c.setFillColor(color)
        c.setFont(font, size)
        c.drawString(x, y, vis)

    # ----- flow
    def new_page(self) -> None:
        self.c.showPage()
        self.y = self.H - self.head_h

    def ensure(self, h: float) -> None:
        if self.y - h < self.bottom:
            self.new_page()

    def space(self, h: float) -> None:
        self.y -= h

    def finish(self) -> None:
        self.c.showPage()  # flush the last page into the saved states
        self.c.save()

    def lines_for(self, bi_map: dict[str, str], *, bold=False, size=9.0) -> list[Line]:
        """Bilingual value -> Line objects honouring the ctx (one per language, deduplicated)."""
        out: list[Line] = []
        seen: set[str] = set()
        for lang in self.ctx.langs:
            txt = self.ctx.conv(bi_map[lang], lang)
            if txt in seen:
                continue
            seen.add(txt)
            out.append(Line(txt, "rtl" if lang == "fa" else "ltr"))
        return out

    def label_lines(self, key: str, **fmt_args) -> list[Line]:
        out = []
        for lang in self.ctx.langs:
            txt = label(key, lang).format(**{k: self.ctx.conv(str(v), lang) for k, v in fmt_args.items()})
            out.append(Line(self.ctx.conv(txt, lang), "rtl" if lang == "fa" else "ltr"))
        return out

    # ----- blocks
    def section(self, key: str) -> None:
        h = 20
        self.ensure(h + 40)
        self.y -= 6
        c = self.c
        c.setFillColor(HEAD)
        c.rect(self.left, self.y - h, self.width, h, stroke=0, fill=1)
        base_y = self.y - h + 6.5
        if self.ctx.lang == "both":
            self.draw(c, label(key, "en"), self.left + 8, self.right - 8, base_y, "ltr", "start",
                      bold=True, size=10, color=HEAD_TEXT)  # fmt: skip
            self.draw(c, label(key, "fa"), self.left + 8, self.right - 8, base_y, "rtl", "start",
                      bold=True, size=10, color=HEAD_TEXT)  # fmt: skip
        else:
            lang = self.ctx.lang
            self.draw(c, label(key, lang), self.left + 8, self.right - 8, base_y,
                      "rtl" if lang == "fa" else "ltr", "start", bold=True, size=10,
                      color=HEAD_TEXT)  # fmt: skip
        self.y -= h + 6

    def paragraph(self, lines: list[Line], *, size: float = 9.5, bold: bool = False,
                  color: Color = INK, align: str = "start") -> None:  # fmt: skip
        """Wrapped paragraph(s); each Line is wrapped and aligned by its own direction."""
        ld = lead(size)
        for ln in lines:
            for piece in wrap(ln.text, self.width, bold=bold, size=size):
                self.ensure(ld)
                self.y -= ld
                self.draw(self.c, piece, self.left, self.right, self.y + ld * 0.28, ln.base, align,
                          bold=bold, size=size, color=color)  # fmt: skip
            self.y -= 2

    # ----- tables
    def col_widths(self, *fractions: float) -> list[float]:
        total = sum(fractions)
        return [self.width * f / total for f in fractions]

    def table(self, widths: list[float], rows: list[list[Cell]], *, header_rows: int = 0,
              rtl: bool | None = None, pad: float = 4.0) -> None:  # fmt: skip
        rtl = self.ctx.rtl_layout if rtl is None else rtl
        # 1. wrap every cell and measure row heights
        wrapped: list[list[list[Line]]] = []
        heights: list[float] = []
        for row in rows:
            cells = []
            hmax = 0.0
            for cell, w in zip(row, widths, strict=True):
                pieces: list[Line] = []
                for ln in cell.lines:
                    pieces += [Line(p, ln.base)
                               for p in wrap(ln.text, w - 2 * pad, bold=cell.bold, size=cell.size)]  # fmt: skip
                cells.append(pieces)
                hmax = max(hmax, len(pieces) * lead(cell.size) + 2 * pad - 2)
            wrapped.append(cells)
            heights.append(max(hmax, 18.0))

        def x_span(i: int) -> tuple[float, float]:
            before = sum(widths[:i])
            if rtl:
                return self.right - before - widths[i], self.right - before
            return self.left + before, self.left + before + widths[i]

        def draw_row(idx: int) -> None:
            h = heights[idx]
            top = self.y
            for i, (cell, pieces) in enumerate(zip(rows[idx], wrapped[idx], strict=True)):
                x0, x1 = x_span(i)
                self.c.setLineWidth(0.5)
                self.c.setStrokeColor(LINE)
                if cell.fill is not None:
                    self.c.setFillColor(cell.fill)
                    self.c.rect(x0, top - h, x1 - x0, h, stroke=1, fill=1)
                else:
                    self.c.rect(x0, top - h, x1 - x0, h, stroke=1, fill=0)
                ld = lead(cell.size)
                content = len(pieces) * ld
                start = top - (h - content) / 2
                for k, ln in enumerate(pieces):
                    baseline = start - k * ld - ld * 0.72
                    self.draw(self.c, ln.text, x0 + pad, x1 - pad, baseline, ln.base, cell.align,
                              bold=cell.bold, size=cell.size, color=cell.color,
                              table_rtl=rtl)  # fmt: skip
            self.y -= h

        header_h = sum(heights[:header_rows])
        first_body = heights[header_rows] if len(rows) > header_rows else 0
        self.ensure(header_h + first_body)
        for i in range(len(rows)):
            if i >= header_rows and self.y - heights[i] < self.bottom:
                self.new_page()
                for j in range(header_rows):  # repeat header
                    draw_row(j)
            draw_row(i)


# --------------------------------------------------------------------------- composite blocks


def _lab(doc: Doc, key: str, lang: str) -> Line:
    return Line(doc.ctx.conv(label(key, lang), lang), "rtl" if lang == "fa" else "ltr")


def value_lines(doc: Doc, value) -> list[Line]:
    """Raw/Num values are left-to-right; anything else is a (bilingual) text value."""
    from .i18n import Num, Raw, bi

    if isinstance(value, Raw):
        return [Line(str(value), "ltr")]
    if isinstance(value, Num):
        return [Line(doc.ctx.conv(str(value)), "ltr")]
    return doc.lines_for(bi(value))


def kv(doc: Doc, rows: list[tuple[str, object]]) -> None:
    """Label/value table. ``both`` -> [English label | value | Persian label]."""
    if doc.ctx.lang == "both":
        widths = doc.col_widths(3.1, 4.8, 3.1)
        out = [
            [
                Cell([_lab(doc, k, "en")], bold=True, fill=BAND, size=8.5),
                Cell(value_lines(doc, v), align="center"),
                Cell([_lab(doc, k, "fa")], align="end", bold=True, fill=BAND, size=8.5),
            ]
            for k, v in rows
        ]
    else:
        lang = doc.ctx.lang
        widths = doc.col_widths(3, 7)
        out = [
            [Cell([_lab(doc, k, lang)], bold=True, fill=BAND, size=8.5),
             Cell(value_lines(doc, v))]  # fmt: skip
            for k, v in rows
        ]
    doc.table(widths, out)


def head_cell(doc: Doc, key: str, suffix: str = "") -> Cell:
    lines = []
    for lang in doc.ctx.langs:
        lines.append(Line(doc.ctx.conv(label(key, lang), lang) + suffix, "rtl" if lang == "fa" else "ltr"))
    return Cell(lines, align="center", bold=True, size=8.2, color=HEAD_TEXT, fill=HEAD)


def verdict(doc: Doc, passed: bool, summary_key: str, **fmt_args) -> None:
    h = 64
    doc.ensure(h + 10)
    doc.y -= 8
    fg, bg = (PASS_FG, PASS_BG) if passed else (FAIL_FG, FAIL_BG)
    c = doc.c
    top = doc.y
    c.setFillColor(bg)
    c.setStrokeColor(fg)
    c.setLineWidth(1.2)
    c.roundRect(doc.left, top - h, doc.width, h, 5, stroke=1, fill=1)
    word = "pass" if passed else "fail"
    mid = (doc.left + doc.right) / 2
    halves = {"en": (doc.left, mid), "fa": (mid, doc.right)}
    for lang in doc.ctx.langs:
        x0, x1 = halves[lang] if doc.ctx.lang == "both" else (doc.left, doc.right)
        base = "rtl" if lang == "fa" else "ltr"
        doc.draw(c, doc.ctx.conv(label("overall", lang), lang), x0 + 10, x1 - 10, top - 15, base,
                 "center", size=8.5, color=fg)  # fmt: skip
        doc.draw(c, label(word, lang), x0 + 10, x1 - 10, top - 38, base, "center", bold=True,
                 size=18, color=fg)  # fmt: skip
        txt = label(summary_key, lang).format(**{k: doc.ctx.conv(str(v), lang) for k, v in fmt_args.items()})
        doc.draw(c, doc.ctx.conv(txt, lang), x0 + 10, x1 - 10, top - 54, base, "center", size=8.2,
                 color=fg)  # fmt: skip
    if doc.ctx.lang == "both":
        c.setStrokeColor(fg)
        c.setLineWidth(0.4)
        c.line(mid, top - 8, mid, top - h + 8)
    doc.y -= h + 6


def sign_boxes(doc: Doc, items: list[tuple[str, object]]) -> None:
    """``items``: (label key, person name value). Drawn side by side."""
    n = len(items)
    h = 88
    doc.ensure(h + 10)
    doc.y -= 10
    gap = 12
    bw = (doc.width - gap * (n - 1)) / n
    c = doc.c
    top = doc.y
    order = list(range(n))
    if doc.ctx.rtl_layout:
        order = order[::-1]  # first item on the right in pure-Persian output
    for slot, idx in enumerate(order):
        key, name = items[idx]
        x0 = doc.left + slot * (bw + gap)
        x1 = x0 + bw
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.rect(x0, top - h, bw, h, stroke=1, fill=0)
        yy = top - 14
        for lang in doc.ctx.langs:
            doc.draw(c, doc.ctx.conv(label(key, lang), lang), x0 + 6, x1 - 6, yy,
                     "rtl" if lang == "fa" else "ltr", "center", bold=True, size=8.2, color=HEAD)  # fmt: skip
            yy -= 12
        for ln in value_lines(doc, name):
            doc.draw(c, ln.text, x0 + 6, x1 - 6, yy - 2, ln.base, "center", size=8.5)
            yy -= 12
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.5)
        c.line(x0 + 14, top - h + 24, x1 - 14, top - h + 24)
        sy = top - h + 12
        for lang in doc.ctx.langs:
            doc.draw(c, label("signature", lang), x0 + 6, x1 - 6, sy, "rtl" if lang == "fa" else "ltr",
                     "center", size=7, color=MUTED)  # fmt: skip
            sy -= 8 if doc.ctx.lang == "both" else 0
    doc.y -= h + 4


def header_names(doc: Doc, c, names: dict[str, str], ref: str) -> None:
    """Page header: organisation name (per language) and a language-neutral reference."""
    top = doc.H - doc.margin + 8
    for lang in doc.ctx.langs:
        txt = doc.ctx.conv(names[lang], lang)
        base = "rtl" if lang == "fa" else "ltr"
        doc.draw(c, txt, doc.left, doc.right, top - 8, base, "start", bold=True, size=10.5, color=HEAD)
    doc.draw(c, ref, doc.left, doc.right, top - 24, "ltr", "center", size=7.5, color=MUTED)
    c.setStrokeColor(HEAD)
    c.setLineWidth(1.2)
    c.line(doc.left, top - 31, doc.right, top - 31)
