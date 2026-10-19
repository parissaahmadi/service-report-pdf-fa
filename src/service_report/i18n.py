"""Language/digit context and the bilingual label catalogue."""

from __future__ import annotations

from dataclasses import dataclass

from . import textnorm

LANGS = ("fa", "en", "both")
DIGITS = ("auto", "fa", "en")


class Raw(str):
    """Language-neutral identifier (serial number, code). Rendered as-is, left-to-right."""


class Num(str):
    """Language-neutral number text. Rendered left-to-right; digits follow the digit style."""


@dataclass(frozen=True)
class Ctx:
    """Output language (``fa``, ``en`` or ``both``) and digit style (``auto``, ``fa``, ``en``).

    With ``digits="auto"`` every line uses the digits of its own language, and
    language-neutral numbers use Persian digits only in pure-Persian output.
    """

    lang: str = "both"
    digits: str = "auto"

    def __post_init__(self) -> None:
        if self.lang not in LANGS:
            raise ValueError(f"lang must be one of {LANGS}, got {self.lang!r}")
        if self.digits not in DIGITS:
            raise ValueError(f"digits must be one of {DIGITS}, got {self.digits!r}")

    @property
    def langs(self) -> tuple[str, ...]:
        """Languages to print, in print order (English first when both)."""
        return ("en", "fa") if self.lang == "both" else (self.lang,)

    @property
    def rtl_layout(self) -> bool:
        """Tables are mirrored only for pure-Persian output."""
        return self.lang == "fa"

    def digit_style(self, lang: str | None = None) -> str:
        if self.digits != "auto":
            return self.digits
        if lang is None:
            return "fa" if self.lang == "fa" else "en"
        return "fa" if lang == "fa" else "en"

    def conv(self, text: str, lang: str | None = None) -> str:
        return textnorm.convert_digits(text, self.digit_style(lang))


def bi(value) -> dict[str, str]:
    """Coerce ``str`` or ``{"fa":..,"en":..}`` to a complete bilingual mapping."""
    if isinstance(value, dict):
        fa, en = value.get("fa"), value.get("en")
        if fa is None and en is None:
            raise ValueError(f"bilingual value needs 'fa' or 'en': {value!r}")
        return {"fa": fa if fa is not None else en, "en": en if en is not None else fa}
    if isinstance(value, str):
        return {"fa": value, "en": value}
    raise TypeError(f"expected str or dict, got {type(value).__name__}")


# key -> (English, Persian)
LABELS: dict[str, tuple[str, str]] = {
    # --- shared ---
    "page_of": ("Page {p} of {n}", "صفحه {p} از {n}"),
    "fingerprint": ("Data fingerprint (SHA-256)", "اثرانگشت داده (SHA-256)"),
    "sample_notice": (
        "Fictional sample document generated for demonstration. All names and values are invented.",
        "این سند یک نمونه‌ی ساختگی برای نمایش فنی است. همه‌ی نام‌ها و مقادیر فرضی‌اند.",
    ),
    "signature": ("Signature", "امضا"),
    "customer": ("Customer", "مشتری"),
    "address": ("Address", "نشانی"),
    "description": ("Description", "شرح"),
    "manufacturer": ("Manufacturer", "سازنده"),
    "model": ("Model", "مدل"),
    "serial": ("Serial No.", "شماره سریال"),
    "asset_tag": ("Asset Tag", "شماره دارایی"),
    "col_no": ("No.", "ردیف"),
    "pass": ("PASS", "قبول"),
    "fail": ("FAIL", "مردود"),
    # --- calibration certificate ---
    "cert_title": ("Calibration Certificate", "گواهی کالیبراسیون"),
    "cert_no": ("Certificate No.", "شماره گواهی"),
    "issue_date": ("Date of Issue", "تاریخ صدور"),
    "cal_date": ("Date of Calibration", "تاریخ کالیبراسیون"),
    "due_date": ("Recommended Next Calibration", "موعد کالیبراسیون بعدی"),
    "lab": ("Laboratory", "آزمایشگاه"),
    "sec_general": ("General Information", "اطلاعات کلی"),
    "sec_object": ("Item Calibrated", "مشخصات ابزار"),
    "range": ("Range", "محدوده‌ی اندازه‌گیری"),
    "resolution": ("Resolution", "دقت نمایش"),
    "sec_env": ("Environmental Conditions", "شرایط محیطی"),
    "temperature": ("Temperature", "دما"),
    "humidity": ("Relative Humidity", "رطوبت نسبی"),
    "pressure": ("Ambient Pressure", "فشار محیط"),
    "sec_refs": ("Reference Standards", "استانداردهای مرجع"),
    "ref_name": ("Standard", "استاندارد"),
    "ref_id": ("ID", "شناسه"),
    "ref_cert": ("Certificate", "گواهی"),
    "ref_due": ("Valid until", "اعتبار تا"),
    "sec_results": ("Measurement Results", "نتایج اندازه‌گیری"),
    "nominal": ("Nominal", "مقدار اسمی"),
    "measured": ("Measured", "مقدار اندازه‌گیری‌شده"),
    "error": ("Error", "خطا"),
    "tolerance": ("Tolerance ±", "تلرانس ±"),
    "uncertainty": ("Uncertainty ±U", "عدم قطعیت ±U"),
    "result": ("Result", "نتیجه"),
    "overall": ("Overall result", "نتیجه‌ی کلی"),
    "points_summary": ("{ok} of {n} points within tolerance", "{ok} نقطه از {n} نقطه در محدوده‌ی تلرانس"),
    "rule_simple": (
        "Decision rule: simple acceptance. A point passes when |error| ≤ tolerance; "
        "the uncertainty is reported but not added to the error.",
        "قاعده‌ی تصمیم‌گیری: پذیرش ساده. هر نقطه وقتی قبول است که |خطا| ≤ تلرانس باشد؛ "
        "عدم قطعیت گزارش می‌شود اما به خطا افزوده نمی‌شود.",
    ),
    "rule_guard": (
        "Decision rule: guard band. A point passes when |error| + U ≤ tolerance.",
        "قاعده‌ی تصمیم‌گیری: باند محافظ. هر نقطه وقتی قبول است که |خطا| + U ≤ تلرانس باشد.",
    ),
    "uncertainty_note": (
        "Expanded uncertainty U is stated for a coverage factor k = 2 (about 95 % confidence).",
        "عدم قطعیت گسترده‌ی U برای ضریب پوشش k = 2 (حدود ۹۵٪ اطمینان) گزارش شده است.",
    ),
    "unit_note": ("All values in {unit}.", "همه‌ی مقادیر بر حسب {unit} هستند."),
    "remarks": ("Remarks", "ملاحظات"),
    # --- service report ---
    "sr_title": ("Service Report", "گزارش سرویس"),
    "report_no": ("Report No.", "شماره گزارش"),
    "service_date": ("Service Date", "تاریخ سرویس"),
    "next_service": ("Next Service Due", "موعد سرویس بعدی"),
    "sec_machine": ("Machine", "دستگاه"),
    "hours_meter": ("Operating Hours", "ساعت کارکرد"),
    "location": ("Location", "محل نصب"),
    "technician": ("Technician", "تکنسین"),
    "complaint": ("Reported Problem", "شرح خرابی"),
    "root_cause": ("Root Cause", "علت ریشه‌ای"),
    "sec_actions": ("Actions Performed", "اقدامات انجام‌شده"),
    "action": ("Action", "اقدام"),
    "hours": ("Hours", "ساعت"),
    "sec_parts": ("Parts Used", "قطعات مصرفی"),
    "part_code": ("Code", "کد"),
    "part_name": ("Part", "قطعه"),
    "qty": ("Qty", "تعداد"),
    "unit_price": ("Unit price", "قیمت واحد"),
    "amount": ("Amount", "مبلغ"),
    "sec_costs": ("Cost Summary", "خلاصه‌ی هزینه"),
    "parts_total": ("Parts total", "جمع قطعات"),
    "labor": ("Labor", "اجرت"),
    "subtotal": ("Subtotal", "جمع پیش از مالیات"),
    "tax": ("VAT {pct} %", "مالیات بر ارزش افزوده {pct}٪"),
    "total": ("Total payable", "مبلغ قابل پرداخت"),
    "in_words": ("In words", "به حروف"),
    "currency": ("rials", "ریال"),
    "recommendation": ("Recommendation", "توصیه"),
    "prepared_by": ("Serviced by", "سرویس‌دهنده"),
    "accepted_by": ("Accepted by (customer)", "تأییدکننده (مشتری)"),
    "calibrated_by": ("Calibrated by", "کالیبره‌کننده"),
    "approved_by": ("Approved by", "تأییدکننده"),
}


def label(key: str, lang: str) -> str:
    en, fa = LABELS[key]
    return fa if lang == "fa" else en
