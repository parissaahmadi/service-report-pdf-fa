"""Service report: cost calculation (exact decimals) and PDF rendering."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from . import fingerprint as fp
from . import fmt, numwords
from .fingerprint import DataError
from .i18n import Ctx, Num, Raw, bi, label
from .layout import BAND as _BAND
from .layout import MUTED, Cell, Doc, Line, head_cell, header_names, kv, sign_boxes

_RIAL = Decimal(1)


@dataclass(frozen=True)
class PartLine:
    code: str
    name: dict[str, str]
    qty: Decimal
    unit_price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Costs:
    parts: tuple[PartLine, ...]
    parts_total: Decimal
    labor_hours: Decimal
    labor_rate: Decimal
    labor_total: Decimal
    subtotal: Decimal
    tax_percent: Decimal
    tax: Decimal
    total: Decimal


def _num(v, where: str) -> Decimal:
    if isinstance(v, bool) or not isinstance(v, (int, Decimal)):
        raise DataError(f"{where} must be a number, got {v!r}")
    return Decimal(v)


def _money(x: Decimal) -> Decimal:
    """Round to whole rials, half up."""
    return x.quantize(_RIAL, rounding=ROUND_HALF_UP)


def compute_costs(data: dict) -> Costs:
    """Amounts are whole rials. Each line is rounded half-up; tax is rounded once on the subtotal."""
    parts = []
    for i, p in enumerate(data.get("parts", [])):
        qty = _num(p.get("qty"), f"parts[{i}].qty")
        price = _num(p.get("unit_price"), f"parts[{i}].unit_price")
        if qty <= 0 or price < 0:
            raise DataError(f"parts[{i}]: qty must be > 0 and unit_price >= 0")
        parts.append(PartLine(str(p.get("code", "")), bi(p["name"]), qty, price, _money(qty * price)))
    hours = Decimal(0)
    for i, a in enumerate(data.get("actions", [])):
        h = _num(a.get("hours"), f"actions[{i}].hours")
        if h < 0:
            raise DataError(f"actions[{i}].hours must be >= 0")
        hours += h
    rate = _num(data.get("labor_rate"), "labor_rate")
    pct = _num(data.get("tax_percent", 0), "tax_percent")
    if rate < 0 or not 0 <= pct <= 100:
        raise DataError("labor_rate must be >= 0 and tax_percent within 0..100")
    parts_total = sum((p.amount for p in parts), Decimal(0))
    labor_total = _money(hours * rate)
    subtotal = parts_total + labor_total
    tax = _money(subtotal * pct / 100)
    return Costs(tuple(parts), parts_total, hours, rate, labor_total, subtotal, pct, tax, subtotal + tax)


def validate(data: dict) -> None:
    for k in ("report_no", "service_date", "customer", "machine", "technician", "complaint",
              "root_cause", "actions", "labor_rate"):  # fmt: skip
        if k not in data:
            raise DataError(f"service report is missing '{k}'")
    for k in ("service_date", "next_service_date"):
        if k in data:
            try:
                fmt.parse_date(data[k])
            except ValueError as e:
                raise DataError(f"{k}: {e}") from None
    if "next_service_date" in data and fmt.parse_date(data["next_service_date"]) <= fmt.parse_date(
        data["service_date"]
    ):
        raise DataError("next_service_date must be after service_date")
    compute_costs(data)


def _date_value(text: str) -> dict[str, str]:
    d = fmt.parse_date(text)
    return {"en": fmt.date_text(d, "en", "en"), "fa": fmt.date_text(d, "fa", "en")}


def _lines(ctx: Ctx, key: str, **kw) -> list[Line]:
    return [
        Line(ctx.conv(label(key, lang).format(**{k: ctx.conv(str(v), lang) for k, v in kw.items()}), lang),
             "rtl" if lang == "fa" else "ltr")
        for lang in ctx.langs
    ]  # fmt: skip


def _currency_note(doc: Doc, ctx: Ctx) -> None:
    lines = [
        Line(ctx.conv(label("unit_note", lang).format(unit=label("currency", lang)), lang),
             "rtl" if lang == "fa" else "ltr")
        for lang in ctx.langs
    ]  # fmt: skip
    doc.paragraph(lines, size=8, color=MUTED)


def amount_words(total: Decimal, lang: str) -> str:
    n = int(total)
    if lang == "fa":
        return f"{numwords.to_words_fa(n)} {label('currency', 'fa')}"
    return f"{numwords.to_words_en(n)} {label('currency', 'en')}"


def render(data: dict, path: str, ctx: Ctx) -> str:
    """Write the service report PDF to ``path``; return the SHA-256 of the input data."""
    validate(data)
    costs = compute_costs(data)
    digest = fp.sha256_hex(data)
    report_no = str(data["report_no"])
    company = bi(data.get("company", {}).get("name", "Service Provider"))
    style = ctx.digit_style()

    doc = Doc(
        path, ctx,
        title=f"Service Report {report_no}",
        subject="Service report (fictional sample)",
        keywords=f"sha256:{digest}",
        footer_note=f"{fp.short(digest)}  ·  SHA-256",
        header_cb=lambda d, c: header_names(d, c, company, report_no),
    )  # fmt: skip

    doc.y -= 4
    for lang in ctx.langs:
        doc.draw(doc.c, label("sr_title", lang), doc.left, doc.right, doc.y - 16,
                 "rtl" if lang == "fa" else "ltr", "center", bold=True, size=17)  # fmt: skip
        doc.y -= 24
    doc.y -= 4

    cust = data["customer"]
    rows = [
        ("report_no", Raw(report_no)),
        ("service_date", _date_value(data["service_date"])),
    ]
    if "next_service_date" in data:
        rows.append(("next_service", _date_value(data["next_service_date"])))
    rows.append(("customer", cust["name"]))
    if "address" in cust:
        rows.append(("address", cust["address"]))
    rows.append(("technician", data["technician"]))
    doc.section("sec_general")
    kv(doc, rows)

    m = data["machine"]
    doc.section("sec_machine")
    rows = [("description", m["description"])]
    if "manufacturer" in m:
        rows.append(("manufacturer", m["manufacturer"]))
    rows += [("model", Raw(str(m["model"]))), ("serial", Raw(str(m["serial"])))]
    if "hours" in m:
        rows.append(("hours_meter", Num(fmt.number(_num(m["hours"], "machine.hours"), style))))
    if "location" in m:
        rows.append(("location", m["location"]))
    kv(doc, rows)

    for key, field in (("complaint", "complaint"), ("root_cause", "root_cause")):
        doc.section(key)
        doc.paragraph(doc.lines_for(bi(data[field])), size=9.2)

    # actions
    doc.section("sec_actions")
    widths = doc.col_widths(0.9, 7.2, 1.5)
    table = [[head_cell(doc, "col_no"), head_cell(doc, "action"), head_cell(doc, "hours")]]
    for i, a in enumerate(data["actions"], 1):
        table.append([
            Cell([Line(ctx.conv(str(i)), "ltr")], align="center"),
            Cell(doc.lines_for(bi(a["description"]))),
            Cell([Line(fmt.number(_num(a["hours"], "hours"), style), "ltr")], align="center"),
        ])  # fmt: skip
    doc.table(widths, table, header_rows=1)

    # parts
    if costs.parts:
        doc.section("sec_parts")
        _currency_note(doc, ctx)
        widths = doc.col_widths(0.9, 1.9, 3.4, 1.0, 2.1, 2.3)
        keys = ["col_no", "part_code", "part_name", "qty", "unit_price", "amount"]
        table = [[head_cell(doc, k) for k in keys]]
        for i, p in enumerate(costs.parts, 1):
            table.append([
                Cell([Line(ctx.conv(str(i)), "ltr")], align="center"),
                Cell([Line(p.code, "ltr")], align="center"),
                Cell(doc.lines_for(p.name)),
                Cell([Line(fmt.number(p.qty, style), "ltr")], align="center"),
                Cell([Line(fmt.number(p.unit_price, style), "ltr")], align="center"),
                Cell([Line(fmt.number(p.amount, style), "ltr")], align="center"),
            ])  # fmt: skip
        doc.table(widths, table, header_rows=1)

    # costs
    doc.section("sec_costs")
    _currency_note(doc, ctx)

    def money(x: Decimal) -> Num:
        return Num(f"{fmt.number(x, style)}")

    labor_detail = f"{fmt.number(costs.labor_hours, style)} × {fmt.number(costs.labor_rate, style)}"
    kv_rows = [
        ("parts_total", money(costs.parts_total)),
        ("labor", Num(f"{money(costs.labor_total)}   ({labor_detail})")),
        ("subtotal", money(costs.subtotal)),
    ]
    kv(doc, kv_rows)
    _tax_and_total(doc, ctx, costs)

    words = {lang: amount_words(costs.total, lang) for lang in ctx.langs}
    doc.space(4)
    for lang in ctx.langs:
        base = "rtl" if lang == "fa" else "ltr"
        doc.paragraph([Line(f"{label('in_words', lang)}: {words[lang]}", base)], size=9, bold=True)

    if data.get("recommendation"):
        doc.section("recommendation")
        doc.paragraph(doc.lines_for(bi(data["recommendation"])), size=9.2)

    sign_boxes(doc, [("prepared_by", data["technician"]),
                     ("accepted_by", {"fa": "نماینده‌ی مشتری", "en": "Customer representative"})])  # fmt: skip
    doc.space(6)
    doc.paragraph(_lines(ctx, "sample_notice"), size=7.2, color=MUTED)
    doc.finish()
    return digest


def _tax_and_total(doc: Doc, ctx: Ctx, costs: Costs) -> None:
    """Tax and total rows (total emphasised) as a separate small table."""
    from .i18n import LABELS

    style = ctx.digit_style()
    pct = fmt.number(costs.tax_percent, style)
    widths = doc.col_widths(3.1, 4.8, 3.1) if ctx.lang == "both" else doc.col_widths(3, 7)

    def lab(key: str, lang: str, **kw) -> Line:
        txt = LABELS[key][1 if lang == "fa" else 0].format(**{k: ctx.conv(v, lang) for k, v in kw.items()})
        return Line(ctx.conv(txt, lang), "rtl" if lang == "fa" else "ltr")

    rows = []
    for key, amount, strong in (("tax", costs.tax, False), ("total", costs.total, True)):
        kw = {"pct": pct} if key == "tax" else {}
        val = Cell([Line(fmt.number(amount, style), "ltr")], align="center" if ctx.lang == "both" else "start",
                   bold=strong, size=10 if strong else 9, fill=_BAND if strong else None)  # fmt: skip
        if ctx.lang == "both":
            rows.append([Cell([lab(key, "en", **kw)], bold=True, fill=_BAND, size=8.5), val,
                         Cell([lab(key, "fa", **kw)], align="end", bold=True, fill=_BAND, size=8.5)])  # fmt: skip
        else:
            rows.append([Cell([lab(key, ctx.lang, **kw)], bold=True, fill=_BAND, size=8.5), val])
    doc.table(widths, rows)
