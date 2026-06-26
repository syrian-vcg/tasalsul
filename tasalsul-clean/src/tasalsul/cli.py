"""واجهة سطر الأوامر لتسلسل v2."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from . import __version__
from .engine import (
    create_archive,
    extract_archive,
    read_metadata,
    migrate_v1,
    InvalidPasswordError,
    CorruptArchiveError,
    UnsupportedVersionError,
    ThumbnailMeta,
    SubtitleRef,
)


def _get_password(arg_password: str | None, confirm: bool = False) -> str:
    if arg_password:
        return arg_password
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    pw = getpass.getpass("🔑 كلمة السر: ")
    if confirm:
        pw2 = getpass.getpass("🔑 تأكيد كلمة السر: ")
        if pw != pw2:
            print("❌ كلمتا السر غير متطابقتين.", file=sys.stderr)
            sys.exit(1)
    return pw


def cmd_create(args: argparse.Namespace) -> None:
    password = _get_password(args.password, confirm=True)
    output   = args.output or Path(args.input).with_suffix(".tslsl")

    thumbnail = None
    if args.thumbnail:
        import base64
        data = Path(args.thumbnail).read_bytes()
        thumbnail = ThumbnailMeta(
            data_b64=base64.b64encode(data).decode(),
            mime="image/jpeg" if args.thumbnail.endswith((".jpg", ".jpeg")) else "image/png",
        )

    subtitles = []
    if args.subtitle:
        import base64
        for sub in args.subtitle:
            lang, path = sub.split(":", 1)
            data = Path(path).read_bytes()
            subtitles.append(SubtitleRef(
                language=lang,
                label=lang,
                data_b64=base64.b64encode(data).decode(),
            ))

    result = create_archive(
        source         = args.input,
        dest           = output,
        password       = password,
        series_name    = args.series,
        season         = args.season,
        episode        = args.episode,
        title          = args.title,
        description    = args.description,
        duration       = args.duration,
        resolution     = args.resolution,
        language       = args.language,
        subtitles      = subtitles or None,
        thumbnail      = thumbnail,
        tags           = args.tag or [],
        source_url     = args.source_url,
        content_rating = args.rating,
    )
    mb = result.size_bytes / 1_048_576
    print(f"✅ تم: {output}  ({mb:.2f} MB)")


def cmd_extract(args: argparse.Namespace) -> None:
    password = _get_password(args.password)
    output   = args.output
    if not output:
        meta   = read_metadata(args.input)
        output = Path(args.input).parent / meta.original_filename

    try:
        result = extract_archive(source=args.input, dest=output, password=password)
    except InvalidPasswordError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(2)
    except CorruptArchiveError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(3)
    print(f"✅ استُخرج إلى: {result.path}")


def cmd_info(args: argparse.Namespace) -> None:
    try:
        meta = read_metadata(args.input)
    except (CorruptArchiveError, UnsupportedVersionError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(3)

    if args.json:
        print(meta.to_json(indent=2))
        return

    def row(label, value):
        if value is not None and value != "" and value != []:
            print(f"  {label:<18}: {value}")

    print(f"\n📦 تسلسل — v{meta.format_version}\n{'─'*40}")
    row("المسلسل",  meta.series_name)
    row("الموسم",   meta.season)
    row("الحلقة",   meta.episode)
    row("العنوان",  meta.title)
    row("الوصف",    meta.description)
    row("المدة",    f"{meta.duration_seconds:.0f}s" if meta.duration_seconds else None)
    row("الدقة",    meta.resolution)
    row("اللغة",    meta.language)
    row("التصنيف",  meta.content_rating)
    row("الملف",    meta.original_filename)
    row("الإنشاء",  meta.created_at[:19])
    row("الضغط",    meta.compression)
    row("التشفير",  meta.encryption)
    if meta.tags:
        row("الوسوم", ", ".join(meta.tags))
    if meta.subtitles:
        langs = ", ".join(s.language for s in meta.subtitles)
        row("الترجمات", langs)
    if meta.thumbnail:
        row("مصغّرة", f"{meta.thumbnail.width}×{meta.thumbnail.height} {meta.thumbnail.mime}")
    print()


def cmd_migrate(args: argparse.Namespace) -> None:
    password = _get_password(args.password)
    output   = args.output or Path(args.input).with_suffix(".v2.tslsl")
    try:
        migrate_v1(source=args.input, dest=output, password=password)
    except InvalidPasswordError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(2)
    print(f"✅ تم الترقية: {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tslsl",
        description="تسلسل: أرشيف مضغوط ومشفّر للمسلسلات (.tslsl)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # ── create ──────────────────────────────────────────────────────
    c = sub.add_parser("create", help="إنشاء أرشيف .tslsl")
    c.add_argument("input",                 help="ملف الفيديو المصدر")
    c.add_argument("-o", "--output",        help="مسار الأرشيف الناتج")
    c.add_argument("-s", "--series",        required=True, help="اسم المسلسل")
    c.add_argument("--season",              type=int, help="رقم الموسم")
    c.add_argument("--episode",             type=int, help="رقم الحلقة")
    c.add_argument("--title",               help="عنوان الحلقة")
    c.add_argument("--description",         help="وصف الحلقة")
    c.add_argument("--duration",            type=float, help="المدة بالثواني")
    c.add_argument("--resolution",          help="الدقة مثل 1920x1080")
    c.add_argument("--language",            help="لغة الحلقة (ar, en, ...)")
    c.add_argument("--rating",              help="التصنيف العمري")
    c.add_argument("--source-url",          help="رابط المصدر")
    c.add_argument("--tag",                 action="append", help="وسم (يمكن تكراره)")
    c.add_argument("--thumbnail",           help="مسار صورة مصغّرة (jpg/png)")
    c.add_argument("--subtitle",            action="append",
                   metavar="LANG:FILE",     help="ترجمة: ar:subs_ar.srt")
    c.add_argument("-p", "--password",      help="كلمة السر")
    c.set_defaults(func=cmd_create)

    # ── extract ──────────────────────────────────────────────────────
    e = sub.add_parser("extract", help="استخراج فيديو من أرشيف")
    e.add_argument("input")
    e.add_argument("-o", "--output")
    e.add_argument("-p", "--password")
    e.set_defaults(func=cmd_extract)

    # ── info ─────────────────────────────────────────────────────────
    i = sub.add_parser("info", help="عرض ميتاداتا الأرشيف")
    i.add_argument("input")
    i.add_argument("--json", action="store_true", help="إخراج بصيغة JSON")
    i.set_defaults(func=cmd_info)

    # ── migrate ──────────────────────────────────────────────────────
    m = sub.add_parser("migrate", help="ترقية أرشيف v1 إلى v2")
    m.add_argument("input")
    m.add_argument("-o", "--output")
    m.add_argument("-p", "--password")
    m.set_defaults(func=cmd_migrate)

    return parser


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
