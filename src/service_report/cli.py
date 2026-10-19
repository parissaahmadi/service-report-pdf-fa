"""Command line interface: ``service-report``."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import certificate, fingerprint, jalali, numwords, service_report
from .fingerprint import DataError
from .i18n import DIGITS, LANGS, Ctx

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _load(path: str):
    return fingerprint.load_json(Path(path).read_text(encoding="utf-8"))


def _ctx(args) -> Ctx:
    return Ctx(args.lang, args.digits)


def _add_render_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", help="JSON data file")
    p.add_argument("-o", "--output", required=True, help="PDF path to write")
    p.add_argument("--lang", choices=LANGS, default="both", help="fa, en, or both (default)")
    p.add_argument("--digits", choices=DIGITS, default="auto",
                   help="auto = each line uses its own language's digits")  # fmt: skip


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="service-report", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("certificate", help="render a calibration certificate")
    _add_render_args(c)
    r = sub.add_parser("report", help="render a service report")
    _add_render_args(r)

    d = sub.add_parser("demo", help="render all bundled examples in all three languages")
    d.add_argument("-o", "--outdir", default="out")

    j = sub.add_parser("jalali", help="convert a date between calendars")
    j.add_argument("date", help="YYYY-MM-DD (Gregorian) or YYYY/MM/DD (Jalali)")

    w = sub.add_parser("words", help="write an integer in words")
    w.add_argument("number", type=int)
    return ap


def _cmd_demo(outdir: str) -> int:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("certificate_pass", certificate.render),
        ("certificate_fail", certificate.render),
        ("service_report", service_report.render),
    ]
    for name, fn in jobs:
        data = _load(str(EXAMPLES / f"{name}.json"))
        for lang in LANGS:
            target = out / f"{name}.{lang}.pdf"
            digest = fn(data, str(target), Ctx(lang))
            print(f"{target}  sha256:{digest[:16]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "certificate":
            digest = certificate.render(_load(args.input), args.output, _ctx(args))
            print(f"wrote {args.output}  sha256:{digest[:16]}")
        elif args.cmd == "report":
            digest = service_report.render(_load(args.input), args.output, _ctx(args))
            print(f"wrote {args.output}  sha256:{digest[:16]}")
        elif args.cmd == "demo":
            return _cmd_demo(args.outdir)
        elif args.cmd == "jalali":
            if "/" in args.date:
                jd = jalali.JalaliDate.parse(args.date)
                print(jd.to_gregorian().isoformat())
            else:
                g = date.fromisoformat(args.date)
                print(jalali.to_jalali(g).iso())
        elif args.cmd == "words":
            print(numwords.to_words_fa(args.number))
            print(numwords.to_words_en(args.number))
    except (DataError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
