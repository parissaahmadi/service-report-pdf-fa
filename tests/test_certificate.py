import copy
import re
from decimal import Decimal
from pathlib import Path

import pytest

from service_report import certificate as cert
from service_report import fingerprint as fp
from service_report.fingerprint import DataError

EX = Path(__file__).resolve().parents[1] / "examples"


def load(name):
    return fp.load_json((EX / name).read_text(encoding="utf-8"))


def test_pass_example_all_points_pass():
    ev = cert.evaluate(load("certificate_pass.json"))
    assert ev.passed and ev.n_ok == 5 and len(ev.points) == 5
    assert ev.points[0].error == Decimal("0.1")


def test_fail_example_has_two_rejected_points():
    ev = cert.evaluate(load("certificate_fail.json"))
    assert not ev.passed
    assert [p.passed for p in ev.points] == [True, True, True, False, True]
    assert ev.points[3].error == Decimal("0.8")


def test_boundary_is_inclusive_and_decimal_exact():
    data = {"points": [{"nominal": 10, "measured": Decimal("10.5"), "tolerance": Decimal("0.5"),
                        "uncertainty": 0}]}  # fmt: skip
    assert cert.evaluate(data).passed
    data["points"][0]["measured"] = Decimal("10.51")
    assert not cert.evaluate(data).passed
    # 0.1 + 0.2 style float traps must not matter:
    d = {"points": [{"nominal": Decimal("0.1"), "measured": Decimal("0.3"),
                     "tolerance": Decimal("0.2"), "uncertainty": 0}]}  # fmt: skip
    assert cert.evaluate(d).passed


def test_guard_band_rule_is_stricter():
    base = {"points": [{"nominal": 100, "measured": Decimal("100.4"), "tolerance": Decimal("0.5"),
                        "uncertainty": Decimal("0.2")}]}  # fmt: skip
    assert cert.evaluate(base).passed
    assert not cert.evaluate({**base, "decision_rule": "guard_band"}).passed


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda d: d.pop("points"), "points"),
        (lambda d: d.update(points=[]), "non-empty"),
        (lambda d: d.update(decision_rule="coin_flip"), "decision_rule"),
        (lambda d: d["points"][0].pop("measured"), "measured"),
        (lambda d: d["points"][0].update(tolerance=-1), ">= 0"),
        (lambda d: d["points"][0].update(nominal="ten"), "number"),
        (lambda d: d["points"][0].update(nominal=True), "number"),
    ],
)
def test_evaluate_rejects_bad_data(mutate, message):
    d = copy.deepcopy(load("certificate_pass.json"))
    mutate(d)
    with pytest.raises(DataError, match=message):
        cert.evaluate(d)


def test_validate_checks_dates():
    d = copy.deepcopy(load("certificate_pass.json"))
    d["next_due_date"] = d["calibration_date"]
    with pytest.raises(DataError, match="after"):
        cert.validate(d)
    d = copy.deepcopy(load("certificate_pass.json"))
    d["issue_date"] = "05/10/2026"
    with pytest.raises(DataError, match="issue_date"):
        cert.validate(d)
    d = copy.deepcopy(load("certificate_pass.json"))
    del d["customer"]
    with pytest.raises(DataError, match="customer"):
        cert.validate(d)


def test_fingerprint_is_stable_under_reformatting_and_key_order():
    text = (EX / "certificate_pass.json").read_text(encoding="utf-8")
    a = fp.load_json(text)
    # strip all whitespace that is outside of string literals
    compact = re.sub(r'\s+(?=(?:[^"]*"[^"]*")*[^"]*$)', "", text)
    assert len(compact) < len(text)
    assert fp.sha256_hex(fp.load_json(compact)) == fp.sha256_hex(a)
    assert fp.sha256_hex(dict(reversed(list(a.items())))) == fp.sha256_hex(a)


def test_fingerprint_changes_with_any_value():
    a = load("certificate_pass.json")
    c = copy.deepcopy(a)
    c["points"][0]["measured"] = Decimal("0.2")
    assert fp.sha256_hex(a) != fp.sha256_hex(c)
    assert len(fp.sha256_hex(a)) == 64
    # 0.10 and 0.1 are different input text, hence different fingerprints
    x, y = copy.deepcopy(a), copy.deepcopy(a)
    x["points"][0]["measured"], y["points"][0]["measured"] = Decimal("0.1"), Decimal("0.10")
    assert fp.sha256_hex(x) != fp.sha256_hex(y)


def test_short_groups_hex():
    assert fp.short("abcdef0123456789ffff") == "abcd ef01 2345 6789"
