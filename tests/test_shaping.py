import pytest
from fontTools.ttLib import TTFont

from service_report import shaping
from service_report.shaping import FORMS, LAM_ALEF, joining_type, shape

FONT_DIR = shaping.__file__.rsplit("/", 1)[0] + "/fonts/"


def test_handoff_reference_words():
    assert shape("سلام") == "ﺳﻼﻡ"
    assert shape("ایران") == "ﺍﯾﺮﺍﻥ"


def test_single_letters_are_isolated():
    assert shape("م") == FORMS["م"]["isolated"]
    assert shape("ا") == FORMS["ا"]["isolated"]


def test_dual_joining_forms():
    f = FORMS["ب"]
    assert shape("ببب") == f["initial"] + f["medial"] + f["final"]
    assert shape("بب") == f["initial"] + f["final"]


def test_right_joining_letters_break_the_chain():
    # د does not join to the following letter, so ب after it starts a new word-shape.
    assert shape("بدب") == FORMS["ب"]["initial"] + FORMS["د"]["final"] + FORMS["ب"]["isolated"]


def test_persian_specific_letters_have_forms():
    for ch in "پچژکگی":
        assert joining_type(ch) in ("D", "R")
        assert "isolated" in FORMS[ch]
    assert shape("پ") != "پ"
    assert shape("گل") == FORMS["گ"]["initial"] + FORMS["ل"]["final"]


def test_zwnj_breaks_joining_and_is_removed():
    assert "‌" not in shape("می‌روم")
    joined = shape("میرم")
    split = shape("می‌رم")
    assert joined != split
    assert split[0] == FORMS["م"]["initial"]
    assert split[1] == FORMS["ی"]["final"]  # joins the preceding م but not the ر after ZWNJ
    assert split[2] == FORMS["ر"]["isolated"]  # ر after ZWNJ starts fresh (right-joining only)


def test_zwj_forces_joining():
    assert shape("ب‍") == FORMS["ب"]["initial"]
    assert shape("‍ب") == FORMS["ب"]["final"]


def test_lam_alef_ligature():
    assert shape("لا") == LAM_ALEF["ا"]["isolated"]
    assert shape("بلا") == FORMS["ب"]["initial"] + LAM_ALEF["ا"]["final"]
    assert set(LAM_ALEF) == {"آ", "أ", "إ", "ا"}


def test_non_arabic_text_untouched():
    assert shape("Hello, 123 - ۱۲۳") == "Hello, 123 - ۱۲۳"
    assert shape("abc سلام") == "abc ﺳﻼﻡ"


def test_spaces_and_digits_break_joining():
    b = FORMS["ب"]
    assert shape("ب ب") == b["isolated"] + " " + b["isolated"]
    assert shape("ب۱ب") == b["isolated"] + "۱" + b["isolated"]


def test_marks_are_transparent():
    b = FORMS["ب"]
    assert shape("بَب") == b["initial"] + "َ" + b["final"]


def test_idempotent_on_presentation_forms():
    once = shape("گزارش سرویس")
    assert shape(once) == once


@pytest.mark.parametrize("font", ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"])
def test_bundled_fonts_cover_all_persian_forms(font):
    cmap = TTFont(FONT_DIR + font).getBestCmap()
    letters = "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیآئؤءأإ"
    needed = {g for ch in letters for g in FORMS.get(ch, {}).values()}
    needed |= {g for v in LAM_ALEF.values() for g in v.values()}
    needed |= set("۰۱۲۳۴۵۶۷۸۹٬٫٪،؛؟«»")
    assert {hex(ord(c)) for c in needed if ord(c) not in cmap} == set()
