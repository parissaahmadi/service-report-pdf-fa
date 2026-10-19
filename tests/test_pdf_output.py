import copy
from pathlib import Path

from fontTools.ttLib import TTFont
import pdfplumber

from service_report import certificate, cli, layout, service_report
from service_report import fingerprint as fp
from service_report.i18n import Ctx

EX = Path(__file__).resolve().parents[1] / "examples"
FONTS = Path(layout.__file__).parent / "fonts"


def load(name):
    return fp.load_json((EX / name).read_text(encoding="utf-8"))


def pages_text(path):
    """Text per page in *drawn* (visual, left-to-right) order, reconstructed from glyph positions.

    pypdf/poppler re-run their own bidi logic on extraction, which scrambles digit runs; sorting
    glyphs by x within a baseline shows exactly what a reader sees.
    """
    out = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            rows: dict[int, list] = {}
            for ch in page.chars:
                rows.setdefault(round(ch["bottom"] / 2), []).append(ch)
            lines = ["".join(c["text"] for c in sorted(cs, key=lambda c: c["x0"]))
                     for _, cs in sorted(rows.items())]  # fmt: skip
            out.append("\n".join(lines))
    return out


def vis(text, base="rtl"):
    """What the renderer writes into the PDF for ``text``."""
    return layout.prepare(text, base)


def test_certificate_text_roundtrips_through_the_pdf(tmp_path):
    out = tmp_path / "c.pdf"
    digest = certificate.render(load("certificate_fail.json"), str(out), Ctx("both"))
    text = "\n".join(pages_text(out))
    assert "CAL-2026-00418" in text
    assert vis("مردود") in text and "FAIL" in text
    assert vis("گواهی کالیبراسیون") in text and "Calibration Certificate" in text
    assert "+0.80" in text  # the failing error, signed
    assert digest[:4] + " " + digest[4:8] in text  # fingerprint in the footer
    with pdfplumber.open(str(out)) as pdf:
        assert f"sha256:{digest}" in pdf.metadata.get("Keywords", "")


def test_pass_certificate_says_pass(tmp_path):
    out = tmp_path / "p.pdf"
    certificate.render(load("certificate_pass.json"), str(out), Ctx("fa"))
    text = "\n".join(pages_text(out))
    assert vis("قبول") in text
    assert vis("مردود") not in text


def test_persian_digits_and_separators(tmp_path):
    out = tmp_path / "s.pdf"
    service_report.render(load("service_report.json"), str(out), Ctx("fa"))
    text = "\n".join(pages_text(out))
    assert "۸۰٬۱۱۳٬۰۰۰" in text  # total with Persian digits and thousands separator
    assert "80,113,000" not in text
    assert vis("هشتاد میلیون و صد و سیزده هزار ریال") in text


def test_english_output_uses_ascii_digits(tmp_path):
    out = tmp_path / "e.pdf"
    service_report.render(load("service_report.json"), str(out), Ctx("en"))
    text = "\n".join(pages_text(out))
    assert "80,113,000" in text
    assert "eighty million one hundred thirteen thousand rials" in text
    assert not any(ch in text for ch in "۰۱۲۳۴۵۶۷۸۹")


def test_digit_override_forces_persian_digits_in_english_text(tmp_path):
    out = tmp_path / "o.pdf"
    service_report.render(load("service_report.json"), str(out), Ctx("en", "fa"))
    text = "\n".join(pages_text(out))
    assert "۸۰٬۱۱۳٬۰۰۰" in text


def test_page_x_of_y_matches_real_page_count(tmp_path):
    out = tmp_path / "n.pdf"
    service_report.render(load("service_report.json"), str(out), Ctx("both"))
    texts = pages_text(out)
    n = len(texts)
    assert n >= 2
    for i, t in enumerate(texts, 1):
        assert f"Page {i} of {n}" in t


def test_output_is_byte_for_byte_reproducible(tmp_path):
    data = load("certificate_pass.json")
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    certificate.render(data, str(a), Ctx("both"))
    certificate.render(copy.deepcopy(data), str(b), Ctx("both"))
    assert a.read_bytes() == b.read_bytes()


def test_long_table_paginates_and_repeats_header(tmp_path):
    data = copy.deepcopy(load("certificate_pass.json"))
    base = data["points"][0]
    data["points"] = [
        {**base, "nominal": i, "measured": i, "uncertainty": base["uncertainty"]} for i in range(80)
    ]
    out = tmp_path / "long.pdf"
    certificate.render(data, str(out), Ctx("en"))
    texts = pages_text(out)
    assert len(texts) >= 3
    pages_with_header = [t for t in texts if "Nominal" in t and "Uncertainty" in t]
    assert len(pages_with_header) >= 2  # header repeated on continuation pages
    # 80 rows + the overall verdict box, each saying PASS exactly once
    assert sum(t.count("PASS") for t in texts) == 81


def test_every_drawn_glyph_exists_in_the_font(tmp_path):
    recorded = []
    original = layout.prepare

    def spy(text, base):
        out = original(text, base)
        recorded.append(out)
        return out

    layout.prepare = spy
    try:
        for name, fn in (("certificate_pass.json", certificate.render),
                         ("certificate_fail.json", certificate.render),
                         ("service_report.json", service_report.render)):  # fmt: skip
            for lang in ("fa", "en", "both"):
                fn(load(name), str(tmp_path / "x.pdf"), Ctx(lang))
    finally:
        layout.prepare = original
    used = set("".join(recorded))
    for fname in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        cmap = TTFont(FONTS / fname).getBestCmap()
        missing = sorted(hex(ord(c)) for c in used if ord(c) not in cmap and c not in "‌‍")
        assert missing == [], f"{fname} lacks {missing}"
    assert len(used) > 80  # sanity: the spy really saw the documents


def test_wrap_respects_width():
    text = "گزارش سرویس دوره‌ای دستگاه تست طولانی برای شکستن خط " * 6 + "A" * 80
    for width in (60, 120, 300):
        for line in layout.wrap(text, width, size=9.5):
            assert layout.width_of(line, False, 9.5, "rtl") <= width + 0.01


def test_cli_end_to_end(tmp_path):
    out = tmp_path / "cli.pdf"
    rc = cli.main(["certificate", str(EX / "certificate_pass.json"), "-o", str(out), "--lang", "fa"])
    assert rc == 0 and out.stat().st_size > 5_000
    rc = cli.main(["report", str(EX / "service_report.json"), "-o", str(tmp_path / "r.pdf")])
    assert rc == 0


def test_cli_reports_data_errors_without_traceback(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"points": []}', encoding="utf-8")
    rc = cli.main(["certificate", str(bad), "-o", str(tmp_path / "x.pdf")])
    assert rc == 2
    assert not (tmp_path / "x.pdf").exists()


def test_cli_jalali_and_words(tmp_path):
    assert cli.main(["jalali", "2026-10-08"]) == 0
    assert cli.main(["jalali", "1405/07/16"]) == 0
    assert cli.main(["jalali", "1405/13/16"]) == 2
    assert cli.main(["words", "1250000"]) == 0


def test_demo_writes_nine_pdfs(tmp_path):
    assert cli.main(["demo", "-o", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.pdf"))) == 9


def test_both_mode_each_line_uses_its_own_languages_digits(tmp_path):
    out = tmp_path / "d.pdf"
    certificate.render(load("certificate_pass.json"), str(out), Ctx("both"))
    text = "\n".join(pages_text(out))
    assert "2026-10-05 (1405/07/13 SH)" in text  # English line: ASCII digits
    assert vis("۱۴۰۵/۰۷/۱۳ (۲۰۲۶-۱۰-۰۵)") in text  # Persian line: Persian digits
