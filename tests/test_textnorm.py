import pytest

from service_report import textnorm as tn


def test_arabic_letters_unified():
    assert tn.normalize("علي كتاب") == "علی کتاب"
    assert tn.normalize("موسى") == "موسی"


def test_tatweel_removed_zwnj_kept():
    assert tn.normalize("ســلام") == "سلام"
    assert tn.normalize("می‌رود") == "می‌رود"


@pytest.mark.parametrize(
    "src,fa,en",
    [
        ("2026", "۲۰۲۶", "2026"),
        ("۱۴۰۵", "۱۴۰۵", "1405"),
        ("٠١٢", "۰۱۲", "012"),
        ("abc 5", "abc ۵", "abc 5"),
    ],
)
def test_digit_conversion(src, fa, en):
    assert tn.to_fa_digits(src) == fa
    assert tn.to_en_digits(src) == en
    assert tn.convert_digits(src, "fa") == fa
    assert tn.convert_digits(src, "en") == en


def test_unknown_digit_style():
    with pytest.raises(ValueError):
        tn.convert_digits("1", "xx")


def test_strip_marks_and_has_rtl():
    assert tn.strip_marks("سَلامٌ") == "سلام"
    assert tn.has_rtl("abc سلام")
    assert not tn.has_rtl("abc 123 -")
