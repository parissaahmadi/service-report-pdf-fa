import pytest

from service_report.numwords import to_words_en, to_words_fa


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "صفر"),
        (7, "هفت"),
        (11, "یازده"),
        (20, "بیست"),
        (21, "بیست و یک"),
        (100, "صد"),
        (101, "صد و یک"),
        (999, "نهصد و نود و نه"),
        (1000, "یک هزار"),
        (2500, "دو هزار و پانصد"),
        (1_205_030, "یک میلیون و دویست و پنج هزار و سی"),
        (12_500_000, "دوازده میلیون و پانصد هزار"),
        (3_000_000_000, "سه میلیارد"),
        (-5, "منفی پنج"),
    ],
)
def test_persian_words(n, expected):
    assert to_words_fa(n) == expected


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "zero"),
        (13, "thirteen"),
        (42, "forty-two"),
        (100, "one hundred"),
        (1_250_000, "one million two hundred fifty thousand"),
        (-8, "minus eight"),
    ],
)
def test_english_words(n, expected):
    assert to_words_en(n) == expected


def test_limits_and_types():
    assert to_words_fa(10**15 - 1).startswith("نهصد و نود و نه تریلیون")
    with pytest.raises(ValueError):
        to_words_fa(10**15)
    with pytest.raises(TypeError):
        to_words_fa(1.5)
    with pytest.raises(TypeError):
        to_words_en(True)
