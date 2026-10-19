from datetime import date, timedelta

import pytest

from service_report import jalali as j

REFERENCE = [
    ((1405, 1, 1), date(2026, 3, 21)),
    ((1348, 10, 11), date(1970, 1, 1)),
    ((1405, 7, 16), date(2026, 10, 8)),
    ((1399, 12, 30), date(2021, 3, 20)),
    ((1403, 1, 1), date(2024, 3, 20)),
]


@pytest.mark.parametrize("jd,gd", REFERENCE)
def test_reference_points_both_directions(jd, gd):
    assert j.JalaliDate(*jd).to_gregorian() == gd
    assert j.to_jalali(gd) == j.JalaliDate(*jd)


def test_leap_years():
    leaps = [y for y in range(1395, 1411) if j.is_leap(y)]
    assert leaps == [1395, 1399, 1403, 1408]


def test_month_lengths():
    assert [j.days_in_month(1404, m) for m in (1, 6, 7, 11, 12)] == [31, 31, 30, 30, 29]
    assert j.days_in_month(1403, 12) == 30


def test_roundtrip_every_day_over_a_century():
    d = date(1960, 1, 1)
    end = date(2060, 1, 1)
    prev = None
    while d < end:
        jd = j.to_jalali(d)
        assert jd.to_gregorian() == d
        if prev is not None:
            assert jd > prev  # strictly increasing
        prev = jd
        d += timedelta(days=1)


def test_year_boundaries_are_continuous():
    # The day before 1 Farvardin is the last day of Esfand.
    for y in range(1380, 1420):
        nowruz = j.JalaliDate(y, 1, 1).to_gregorian()
        last = j.to_jalali(nowruz - timedelta(days=1))
        assert (last.year, last.month) == (y - 1, 12)
        assert last.day == j.days_in_month(y - 1, 12)


@pytest.mark.parametrize("args", [(1405, 13, 1), (1405, 0, 1), (1405, 7, 31), (1404, 12, 30)])
def test_invalid_dates_rejected(args):
    with pytest.raises(ValueError):
        j.JalaliDate(*args)


def test_out_of_range_year_rejected():
    with pytest.raises(ValueError):
        j.JalaliDate(1700, 1, 1)
    with pytest.raises(ValueError):
        j.to_jalali(date(2500, 1, 1))


def test_parse_and_format():
    d = j.JalaliDate.parse("1405/07/16")
    assert d.iso() == "1405/07/16"
    assert j.JalaliDate.parse("1405-7-6").day == 6
    assert d.long_fa() == "16 مهر 1405"
    assert d.long_en() == "16 Mehr 1405 SH"
    with pytest.raises(ValueError):
        j.JalaliDate.parse("1405/07")


def test_weekday_names():
    assert j.weekday_fa(date(2026, 10, 10)) == "شنبه"  # a Saturday
    assert j.weekday_fa(date(2026, 10, 9)) == "جمعه"
