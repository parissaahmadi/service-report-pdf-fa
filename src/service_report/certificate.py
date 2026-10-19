"""Calibration certificate: data validation, pass/fail evaluation and PDF rendering."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from . import fingerprint as fp
from . import fmt
from .fingerprint import DataError
from .i18n import Ctx, Num, Raw, bi, label
from .layout import (
    FAIL_BG, FAIL_FG, MUTED, PASS_BG, PASS_FG, Cell, Doc, Line, head_cell, header_names, kv,
    sign_boxes, verdict,
)  # fmt: skip

RULES = ("simple", "guard_band")


@dataclass(frozen=True)
class PointResult:
    nominal: Decimal
    measured: Decimal
    error: Decimal
    tolerance: Decimal
    uncertainty: Decimal
    passed: bool


@dataclass(frozen=True)
class Evaluation:
    points: tuple[PointResult, ...]
    rule: str

    @property
    def passed(self) -> bool:
        return all(p.passed for p in self.points)

    @property
    def n_ok(self) -> int:
        return sum(p.passed for p in self.points)


def _dec(point: dict, key: str, idx: int) -> Decimal:
    try:
        v = point[key]
    except KeyError:
        raise DataError(f"points[{idx}] is missing '{key}'") from None
    if isinstance(v, bool) or not isinstance(v, (int, Decimal)):
        raise DataError(f"points[{idx}].{key} must be a number, got {v!r}")
    return Decimal(v)


def evaluate(data: dict) -> Evaluation:
    """Compute the error and the accept/reject decision for every measurement point.

    ``error = measured - nominal``. Rule ``simple``: pass if ``|error| <= tolerance``.
    Rule ``guard_band``: pass if ``|error| + U <= tolerance``. All math is exact ``Decimal``.
    """
    rule = data.get("decision_rule", "simple")
    if rule not in RULES:
        raise DataError(f"decision_rule must be one of {RULES}, got {rule!r}")
    raw = data.get("points")
    if not isinstance(raw, list) or not raw:
        raise DataError("'points' must be a non-empty list")
    out = []
    for i, p in enumerate(raw):
        nominal, measured = _dec(p, "nominal", i), _dec(p, "measured", i)
        tol, unc = _dec(p, "tolerance", i), _dec(p, "uncertainty", i)
        if tol < 0 or unc < 0:
            raise DataError(f"points[{i}]: tolerance and uncertainty must be >= 0")
        err = measured - nominal
        limit = abs(err) + (unc if rule == "guard_band" else 0)
        out.append(PointResult(nominal, measured, err, tol, unc, limit <= tol))
    return Evaluation(tuple(out), rule)


def _req(d: dict, key: str, where: str = "certificate"):
    if key not in d:
        raise DataError(f"{where} is missing '{key}'")
    return d[key]


def validate(data: dict) -> None:
    for k in ("certificate_no", "issue_date", "calibration_date", "next_due_date", "lab",
              "customer", "instrument", "references", "points", "signatures"):  # fmt: skip
        _req(data, k)
    for k in ("name",):
        _req(data["lab"], k, "lab")
        _req(data["customer"], k, "customer")
    for k in ("description", "manufacturer", "model", "serial", "unit"):
        _req(data["instrument"], k, "instrument")
    for k in ("issue_date", "calibration_date", "next_due_date"):
        try:
            fmt.parse_date(data[k])
        except ValueError as e:
            raise DataError(f"{k}: {e}") from None
    if fmt.parse_date(data["next_due_date"]) <= fmt.parse_date(data["calibration_date"]):
        raise DataError("next_due_date must be after calibration_date")
    evaluate(data)


def _date_value(text: str) -> dict[str, str]:
    d = fmt.parse_date(text)
    return {"en": fmt.date_text(d, "en", "en"), "fa": fmt.date_text(d, "fa", "en")}


def _places(ev: Evaluation) -> int:
    vals = []
    for p in ev.points:
        vals += [p.nominal, p.measured, p.error, p.tolerance, p.uncertainty]
    return max(fmt.decimal_places(v) for v in vals)


def render(data: dict, path: str, ctx: Ctx) -> str:
    """Write the certificate PDF to ``path``; return the SHA-256 of the input data."""
    validate(data)
    ev = evaluate(data)
    digest = fp.sha256_hex(data)
    inst = data["instrument"]
    unit = inst["unit"]
    lab_name = bi(data["lab"]["name"])
    cert_no = str(data["certificate_no"])

    doc = Doc(
        path, ctx,
        title=f"Calibration Certificate {cert_no}",
        subject="Calibration certificate (fictional sample)",
        keywords=f"sha256:{digest}",
        footer_note=f"{fp.short(digest)}  ·  SHA-256",
        header_cb=lambda d, c: header_names(d, c, lab_name, cert_no),
    )  # fmt: skip

    # ---- title
    doc.y -= 4
    for lang in ctx.langs:
        doc.draw(doc.c, label("cert_title", lang), doc.left, doc.right, doc.y - 16,
                 "rtl" if lang == "fa" else "ltr", "center", bold=True, size=17)  # fmt: skip
        doc.y -= 24
    doc.y -= 4

    # ---- general
    doc.section("sec_general")
    rows = [
        ("cert_no", Raw(cert_no)),
        ("issue_date", _date_value(data["issue_date"])),
        ("cal_date", _date_value(data["calibration_date"])),
        ("due_date", _date_value(data["next_due_date"])),
        ("customer", data["customer"]["name"]),
    ]
    if "address" in data["customer"]:
        rows.append(("address", data["customer"]["address"]))
    kv(doc, rows)

    # ---- instrument
    doc.section("sec_object")
    rows = [
        ("description", inst["description"]),
        ("manufacturer", inst["manufacturer"]),
        ("model", Raw(str(inst["model"]))),
        ("serial", Raw(str(inst["serial"]))),
    ]
    if "asset_tag" in inst:
        rows.append(("asset_tag", Raw(str(inst["asset_tag"]))))
    if "range" in inst:
        rows.append(("range", Raw(str(inst["range"]))))
    if "resolution" in inst:
        rows.append(("resolution", Raw(str(inst["resolution"]))))
    kv(doc, rows)

    # ---- environment
    env = data.get("environment")
    if env:
        doc.section("sec_env")
        rows = []
        st = ctx.digit_style()
        if "temperature_c" in env:
            rows.append(("temperature", Num(f"{fmt.number(env['temperature_c'], st)} °C")))
        if "humidity_pct" in env:
            rows.append(("humidity", Num(f"{fmt.number(env['humidity_pct'], st)} %")))
        if "pressure_kpa" in env:
            rows.append(("pressure", Num(f"{fmt.number(env['pressure_kpa'], st)} kPa")))
        if rows:
            kv(doc, rows)

    # ---- references
    refs = data["references"]
    if refs:
        doc.section("sec_refs")
        widths = doc.col_widths(4.2, 2.2, 2.4, 2.2)
        keys = ["ref_name", "ref_id", "ref_cert", "ref_due"]
        table = [[head_cell(doc, k) for k in keys]]
        for r in refs:
            table.append([
                Cell(doc.lines_for(bi(r["name"]))),
                Cell([Line(str(r["id"]), "ltr")], align="center"),
                Cell([Line(str(r.get("certificate", "-")), "ltr")], align="center"),
                Cell([Line(ctx.conv(str(r.get("valid_until", "-"))), "ltr")], align="center"),
            ])  # fmt: skip
        doc.table(widths, table, header_rows=1)

    # ---- results
    doc.section("sec_results")
    places = _places(ev)
    doc.paragraph(
        [Line(ctx.conv(label("unit_note", lang).format(unit=unit), lang), "rtl" if lang == "fa" else "ltr")
         for lang in ctx.langs],
        size=8, color=MUTED,
    )  # fmt: skip
    cols = [("col_no", ""), ("nominal", ""), ("measured", ""), ("error", ""),
            ("tolerance", ""), ("uncertainty", ""), ("result", "")]  # fmt: skip
    widths = doc.col_widths(1.0, 2.0, 2.0, 2.0, 2.0, 2.2, 1.9)
    table = [[head_cell(doc, k, s) for k, s in cols]]
    style = ctx.digit_style()
    for i, p in enumerate(ev.points, 1):
        def n(x: Decimal, signed: bool = False) -> Cell:
            return Cell([Line(fmt.number(x, style, places=places, signed=signed), "ltr")], align="center")

        fg, bg = (PASS_FG, PASS_BG) if p.passed else (FAIL_FG, FAIL_BG)
        word = "pass" if p.passed else "fail"
        table.append([
            Cell([Line(ctx.conv(str(i)), "ltr")], align="center"),
            n(p.nominal), n(p.measured), n(p.error, signed=True), n(p.tolerance), n(p.uncertainty),
            Cell([Line(label(word, lang), "rtl" if lang == "fa" else "ltr") for lang in ctx.langs],
                 align="center", bold=True, color=fg, fill=bg, size=8.5),
        ])  # fmt: skip
    doc.table(widths, table, header_rows=1)
    doc.space(4)
    notes = [("rule_guard" if ev.rule == "guard_band" else "rule_simple"), "uncertainty_note"]
    for key in notes:
        doc.paragraph(
            [Line(ctx.conv(label(key, lang), lang), "rtl" if lang == "fa" else "ltr") for lang in ctx.langs],
            size=7.8, color=MUTED,
        )  # fmt: skip

    verdict(doc, ev.passed, "points_summary", ok=ev.n_ok, n=len(ev.points))

    if data.get("remarks"):
        doc.section("remarks")
        doc.paragraph(doc.lines_for(bi(data["remarks"])), size=9)

    sig_items = []
    for s in data["signatures"]:
        sig_items.append((s["role"], s["name"]))
    sign_boxes(doc, sig_items)

    doc.space(6)
    doc.paragraph(
        [Line(label("sample_notice", lang), "rtl" if lang == "fa" else "ltr") for lang in ctx.langs],
        size=7.2, color=MUTED,
    )  # fmt: skip
    doc.finish()
    return digest
