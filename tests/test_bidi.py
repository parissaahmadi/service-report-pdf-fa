import pytest

from service_report import bidi


@pytest.mark.parametrize(
    "logical,expected",
    [
        ("سلام abc", "abc مالس"),  # handoff reference cases (RTL base)
        ("سال ۱۴۰۵", "۱۴۰۵ لاس"),
        ("(سلام)", "(مالس)"),
        ("ab cd", "ab cd"),  # pure Latin keeps order, even in an RTL paragraph
        ("12 34", "34 12"),  # first number sits on the right in an RTL paragraph
        ("abc سلام", "مالس abc"),
        ("سلام", "مالس"),
        ("", ""),
    ],
)
def test_rtl_base(logical, expected):
    assert bidi.visual(logical, "rtl") == expected


@pytest.mark.parametrize(
    "logical,expected",
    [
        ("abc سلام", "abc مالس"),
        ("abc def", "abc def"),
        ("a (b)", "a (b)"),
        ("سلام", "مالس"),
    ],
)
def test_ltr_base(logical, expected):
    assert bidi.visual(logical, "ltr") == expected


def test_numbers_with_separators_stay_together():
    assert bidi.visual("مبلغ 1,250.50 ریال", "rtl") == "لایر 1,250.50 غلبم"
    assert bidi.visual("تاریخ 1405/07/16", "rtl") == "1405/07/16 خیرات"


def test_hyphenated_identifier_stays_left_to_right():
    assert bidi.visual("شماره SN-2026-0042", "rtl") == "SN-2026-0042 هرامش"


def test_percent_sign_follows_number_in_reading_order():
    # Alone, number+sign form one EN run. After Persian letters the digits become AN (W2)
    # and the sign is a neutral that joins the RTL run, i.e. it ends up left of the number.
    assert bidi.visual("۱۰٪", "rtl") == "۱۰٪"
    assert bidi.visual("تخفیف ۱۰٪", "rtl") == "٪۱۰ فیفخت"


def test_parentheses_mirror_only_in_rtl_runs():
    assert bidi.visual("(ab)", "rtl") == "(ab)"
    assert bidi.visual("سلام (ab)", "rtl") == "(ab) مالس"
    assert bidi.visual("«سلام»", "rtl") == "«مالس»"


def test_trailing_space_goes_to_paragraph_edge():
    # L1: trailing whitespace takes the paragraph level.
    assert bidi.visual("abc ", "rtl") == " abc"
    assert bidi.visual("abc ", "ltr") == "abc "


def test_auto_direction():
    assert bidi.paragraph_level("سلام abc", "auto") == 1
    assert bidi.paragraph_level("abc سلام", "auto") == 0
    assert bidi.paragraph_level("123 ...", "auto") == 0
    with pytest.raises(ValueError):
        bidi.paragraph_level("x", "sideways")


def test_explicit_formatting_characters_are_removed():
    assert bidi.visual("a‫b‬c", "ltr") == "abc"


def test_levels_shape():
    assert bidi.resolve_levels("سلام abc", "rtl") == [1, 1, 1, 1, 1, 2, 2, 2]
    assert bidi.resolve_levels("abc", "ltr") == [0, 0, 0]


def test_visual_is_a_permutation_without_mirroring():
    text = "گزارش Report 12-34 سرویس x"
    out = bidi.visual(text, "rtl")
    assert sorted(out) == sorted(text)


def test_segment_separator_resets_to_paragraph_level_l1():
    # Without rule L1 the tab would be absorbed into the surrounding LTR run.
    assert bidi.resolve_levels("ab\tcd", "rtl") == [2, 2, 1, 2, 2]
    assert bidi.visual("ab\tcd", "rtl") == "cd\tab"
    # whitespace directly before the separator is reset too
    assert bidi.resolve_levels("ab \tcd", "rtl") == [2, 2, 1, 1, 2, 2]
