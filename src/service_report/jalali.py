"""Jalali (Solar Hijri) calendar conversion.

Uses the 33-year arithmetic rule: year ``y`` is leap when ``(25*y + 11) % 33 < 8``.
This agrees with the official calendar for the years supported here
(``MIN_YEAR``..``MAX_YEAR``); outside that range a ``ValueError`` is raised
rather than returning a silently wrong date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import cache

MIN_YEAR = 1200
MAX_YEAR = 1600

# Anchor: 1 Farvardin 1405 == 2026-03-21.
_ANCHOR_YEAR = 1405
_ANCHOR_ORDINAL = date(2026, 3, 21).toordinal()

MONTHS_FA = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)  # fmt: skip
MONTHS_EN = (
    "Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar",
    "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand",
)  # fmt: skip
# Indexed by date.weekday() (Monday == 0).
WEEKDAYS_FA = (
    "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه",
)  # fmt: skip


def is_leap(year: int) -> bool:
    return (25 * year + 11) % 33 < 8


def days_in_month(year: int, month: int) -> int:
    if not 1 <= month <= 12:
        raise ValueError(f"month out of range: {month}")
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if is_leap(year) else 29


def _check_year(year: int) -> None:
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"Jalali year {year} outside supported range {MIN_YEAR}..{MAX_YEAR}")


@cache
def _year_start(year: int) -> int:
    """Gregorian ordinal of 1 Farvardin of ``year``."""
    _check_year(year)
    ordinal = _ANCHOR_ORDINAL
    if year >= _ANCHOR_YEAR:
        for y in range(_ANCHOR_YEAR, year):
            ordinal += 366 if is_leap(y) else 365
    else:
        for y in range(year, _ANCHOR_YEAR):
            ordinal -= 366 if is_leap(y) else 365
    return ordinal


@dataclass(frozen=True, order=True)
class JalaliDate:
    year: int
    month: int
    day: int

    def __post_init__(self) -> None:
        _check_year(self.year)
        if not 1 <= self.day <= days_in_month(self.year, self.month):
            raise ValueError(f"invalid Jalali date {self.year}/{self.month}/{self.day}")

    def to_gregorian(self) -> date:
        doy = sum(days_in_month(self.year, m) for m in range(1, self.month)) + self.day - 1
        return date.fromordinal(_year_start(self.year) + doy)

    @classmethod
    def from_gregorian(cls, d: date) -> JalaliDate:
        year = d.year - 621
        ordinal = d.toordinal()
        # The estimate is off by at most one year.
        if ordinal < _year_start(year):
            year -= 1
        elif ordinal >= _year_start(year + 1):
            year += 1
        doy = ordinal - _year_start(year)
        month = 1
        while doy >= days_in_month(year, month):
            doy -= days_in_month(year, month)
            month += 1
        return cls(year, month, doy + 1)

    @classmethod
    def parse(cls, text: str) -> JalaliDate:
        """Parse ``YYYY/MM/DD`` (or ``-`` separated)."""
        parts = text.replace("-", "/").split("/")
        if len(parts) != 3:
            raise ValueError(f"expected YYYY/MM/DD, got {text!r}")
        return cls(*(int(p) for p in parts))

    def iso(self) -> str:
        """``1405/07/16`` (ASCII digits)."""
        return f"{self.year:04d}/{self.month:02d}/{self.day:02d}"

    def long_fa(self) -> str:
        """``۱۶ مهر ۱۴۰۵`` is produced by the caller's digit style; here ASCII digits."""
        return f"{self.day} {MONTHS_FA[self.month - 1]} {self.year}"

    def long_en(self) -> str:
        return f"{self.day} {MONTHS_EN[self.month - 1]} {self.year} SH"


def to_jalali(d: date) -> JalaliDate:
    return JalaliDate.from_gregorian(d)


def to_gregorian(year: int, month: int, day: int) -> date:
    return JalaliDate(year, month, day).to_gregorian()


def weekday_fa(d: date) -> str:
    return WEEKDAYS_FA[d.weekday()]
