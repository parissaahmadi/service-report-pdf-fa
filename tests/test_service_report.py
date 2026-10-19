import copy
from decimal import Decimal
from pathlib import Path

import pytest

from service_report import fingerprint as fp
from service_report import service_report as sr
from service_report.fingerprint import DataError

EX = Path(__file__).resolve().parents[1] / "examples"


def load():
    return fp.load_json((EX / "service_report.json").read_text(encoding="utf-8"))


def test_example_costs_are_exact():
    c = sr.compute_costs(load())
    assert c.parts_total == Decimal(51_830_000)  # 4.25M + 18.6M + 20 x 1.35M + 1.98M
    assert c.labor_hours == Decimal("6.0")
    assert c.labor_total == Decimal(21_000_000)
    assert c.subtotal == Decimal(72_830_000)
    assert c.tax == Decimal(7_283_000)
    assert c.total == Decimal(80_113_000)


def test_rounding_is_half_up_to_whole_rials():
    d = load()
    d["parts"] = [{"code": "X", "name": "x", "qty": Decimal("2.5"), "unit_price": 1001}]
    d["actions"] = [{"description": "x", "hours": 0}]
    d["tax_percent"] = 9
    c = sr.compute_costs(d)
    assert c.parts[0].amount == Decimal(2503)  # 2502.5 -> 2503 (half up, not banker's)
    assert c.tax == Decimal(225)  # 2503 * 9% = 225.27
    assert c.total == Decimal(2728)


def test_zero_tax_and_no_parts():
    d = load()
    d["parts"] = []
    d["tax_percent"] = 0
    c = sr.compute_costs(d)
    assert c.parts_total == 0 and c.tax == 0 and c.total == c.labor_total


def test_total_in_words_both_languages():
    assert sr.amount_words(Decimal(80_113_000), "fa") == "هشتاد میلیون و صد و سیزده هزار ریال"
    assert sr.amount_words(Decimal(80_113_000), "en") == "eighty million one hundred thirteen thousand rials"


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda d: d.pop("labor_rate"), "labor_rate"),
        (lambda d: d["parts"][0].update(qty=0), "qty"),
        (lambda d: d["parts"][0].update(unit_price=-5), "unit_price"),
        (lambda d: d["actions"][0].update(hours=-1), "hours"),
        (lambda d: d.update(tax_percent=101), "tax_percent"),
        (lambda d: d.update(next_service_date="2020-01-01"), "after"),
        (lambda d: d.update(service_date="yesterday"), "service_date"),
        (lambda d: d["parts"][1].update(qty="two"), "number"),
    ],
)
def test_rejects_bad_data(mutate, message):
    d = copy.deepcopy(load())
    mutate(d)
    with pytest.raises(DataError, match=message):
        sr.validate(d)
