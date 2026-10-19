"""Number and date formatting that respects the digit style."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from . import textnorm
from .jalali import JalaliDate

FA_THOUSANDS = "٬"  # ARABIC THOUSANDS SEPARATOR
FA_DECIMAL = "٫"  # ARABIC DECIMAL SEPARATOR


def decimal_places(x: Decimal) -> int:
    exp = x.as_tuple().exponent
    return max(0, -exp) if isinstance(exp, int) else 0


def number(x: Decimal | int | str, style: str = "en", *, places: int | None = None,
           signed: bool = False, group: bool = True) -> str:  # fmt: skip
    """Format ``x`` with thousands grouping.

    ``places`` forces a number of decimals (half-up rounding); otherwise the decimals
    already present in ``x`` are kept. ``style`` is ``"en"`` or ``"fa"``.
    """
    d = x if isinstance(x, Decimal) else Decimal(str(x))
    if places is not None:
        d = d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    text = format(d, "f")
    neg = text.startswith("-")
    text = text.lstrip("-")
    whole, _, frac = text.partition(".")
    if group:
        whole = f"{int(whole):,}"
    out = whole + (f".{frac}" if frac else "")
    if neg and Decimal(out.replace(",", "")) != 0:
        out = "-" + out
    elif signed and Decimal(out.replace(",", "")) != 0:
        out = "+" + out
    if style == "fa":
        out = out.replace(",", FA_THOUSANDS).replace(".", FA_DECIMAL)
        return textnorm.to_fa_digits(out)
    if style == "en":
        return out
    raise ValueError(f"unknown digit style: {style!r}")


def date_text(d: date, lang: str, style: str) -> str:
    """Both calendars in one string. Persian output leads with the Jalali date."""
    jd = JalaliDate.from_gregorian(d).iso()
    text = f"{jd} ({d.isoformat()})" if lang == "fa" else f"{d.isoformat()} ({jd} SH)"
    return textnorm.convert_digits(text, style)


def parse_date(text: str) -> date:
    return date.fromisoformat(text)
