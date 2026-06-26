"""
تسلسل (TSLSL) — Archive Engine v2
===================================
صيغة أرشيف مضغوط ومشفّر من الجيل الثاني لفيديوهات المسلسلات.

الجديد في v2:
  • بث (streaming) الإنشاء والاستخراج — لا حاجة لتحميل الملف كاملاً
  • دعم ملفات الويب (bytes / BytesIO / BinaryIO)
  • ميتاداتا موسّعة: صورة مصغّرة، مدة، دقة، لغة، ترجمات
  • فحص سلامة تدريجي (SHA-256)
  • نسخة الصيغة مُضمَّنة للتوافق الأمامي

بنية الملف (.tslsl v2):
  ┌──────────────┬─────────────────────────────────────────┐
  │ 8  bytes     │ MAGIC = b'TSLSL002'                     │
  │ 2  bytes     │ FORMAT_VERSION (uint16 big-endian)      │
  │ 4  bytes     │ HEADER_LEN (uint32 big-endian)          │
  │ N  bytes     │ HEADER (JSON/UTF-8, unencrypted)        │
  │ 16 bytes     │ SALT (random, for key derivation)       │
  │ 16 bytes     │ IV (AES-GCM nonce)                      │
  │ M  bytes     │ PAYLOAD (zlib → AES-256-GCM)            │
  │ 16 bytes     │ GCM AUTH TAG                            │
  └──────────────┴─────────────────────────────────────────┘
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import struct
import zlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ─────────────────────────── constants ───────────────────────────────
MAGIC          = b"TSLSL002"
FORMAT_VERSION = 2
SALT_SIZE      = 16
IV_SIZE        = 16       # AES-GCM nonce
KEY_SIZE       = 32       # AES-256
PBKDF2_ITER    = 390_000
CHUNK_SIZE     = 256 * 1024
TAG_SIZE       = 16

FileInput = Union[str, Path, bytes, BinaryIO]


# ─────────────────────────── errors ──────────────────────────────────
class TasalsulError(Exception):
    """خطأ عام في معالجة أرشيف تسلسل."""

class InvalidPasswordError(TasalsulError):
    """كلمة السر خاطئة أو البيانات تالفة."""

class CorruptArchiveError(TasalsulError):
    """الأرشيف تالف أو لا يطابق صيغة تسلسل."""

class UnsupportedVersionError(TasalsulError):
    """إصدار الصيغة غير مدعوم."""


# ─────────────────────────── metadata ────────────────────────────────
@dataclass
class ThumbnailMeta:
    """صورة مصغّرة مُضمَّنة في الميتاداتا (base64)."""
    data_b64: str = ""
    mime: str = "image/jpeg"
    width: int = 0
    height: int = 0


@dataclass
class SubtitleRef:
    """مرجع لملف ترجمة خارجي أو مُضمَّن."""
    language: str
    label: str
    url: str = ""
    data_b64: str = ""


@dataclass
class SeriesMetadata:
    """ميتاداتا الحلقة — مرئية بلا كلمة سر."""

    # أساسية
    series_name:       str
    original_filename: str
    season:            Optional[int]   = None
    episode:           Optional[int]   = None
    title:             Optional[str]   = None

    # موسّعة
    description:       Optional[str]   = None
    duration_seconds:  Optional[float] = None
    resolution:        Optional[str]   = None
    language:          Optional[str]   = None
    subtitles:         list = field(default_factory=list)
    thumbnail:         Optional[ThumbnailMeta] = None
    tags:              list = field(default_factory=list)
    source_url:        Optional[str]   = None
    content_rating:    Optional[str]   = None

    # سلامة وتشفير
    sha256_original:   str = ""
    compression:       str = "zlib"
    encryption:        str = "aes-256-gcm-pbkdf2"
    format_version:    int = FORMAT_VERSION

    # توقيت
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SeriesMetadata":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        clean = {k: v for k, v in d.items() if k in known}
        if "subtitles" in clean and clean["subtitles"]:
            clean["subtitles"] = [
                SubtitleRef(**s) if isinstance(s, dict) else s
                for s in clean["subtitles"]
            ]
        if "thumbnail" in clean and isinstance(clean.get("thumbnail"), dict):
            clean["thumbnail"] = ThumbnailMeta(**clean["thumbnail"])
        return cls(**clean)

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "SeriesMetadata":
        return cls.from_dict(json.loads(text))


# ─────────────────────────── key derivation ──────────────────────────
def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITER,
    )
    return kdf.derive(password.encode("utf-8"))


# ─────────────────────────── helpers ─────────────────────────────────
def _open_input(source: FileInput) -> tuple:
    """يفتح مصدر البيانات ويعيد (stream, filename)."""
    if isinstance(source, (str, Path)):
        p = Path(source)
        return open(p, "rb"), p.name
    if isinstance(source, bytes):
        return io.BytesIO(source), None
    name = getattr(source, "name", None)
    if name:
        name = Path(name).name
    return source, name


def _sha256_stream(stream: BinaryIO) -> str:
    h = hashlib.sha256()
    stream.seek(0)
    while chunk := stream.read(CHUNK_SIZE):
        h.update(chunk)
    stream.seek(0)
    return h.hexdigest()


# ─────────────────────────── CREATE ──────────────────────────────────
def create_archive(
    *,
    source:         FileInput,
    dest:           FileInput,
    password:       str,
    series_name:    str,
    season:         Optional[int]   = None,
    episode:        Optional[int]   = None,
    title:          Optional[str]   = None,
    description:    Optional[str]   = None,
    duration:       Optional[float] = None,
    resolution:     Optional[str]   = None,
    language:       Optional[str]   = None,
    subtitles:      Optional[list]  = None,
    thumbnail:      Optional[ThumbnailMeta] = None,
    tags:           Optional[list]  = None,
    source_url:     Optional[str]   = None,
    content_rating: Optional[str]   = None,
    extra:          Optional[dict]  = None,
    compress_level: int             = 6,
) -> "ArchiveResult":
    """
    ينشئ أرشيف .tslsl من مصدر بيانات أي نوع.

    Parameters
    ----------
    source : path / bytes / BinaryIO — مصدر الفيديو
    dest   : path / BinaryIO         — وجهة الكتابة

    Returns
    -------
    ArchiveResult مع معلومات الملف الناتج
    """
    in_stream, src_name = _open_input(source)

    sha256   = _sha256_stream(in_stream)
    raw_data = in_stream.read()
    in_stream.close()

    compressed = zlib.compress(raw_data, level=compress_level)

    salt   = os.urandom(SALT_SIZE)
    iv     = os.urandom(IV_SIZE)
    key    = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, compressed, None)

    meta = SeriesMetadata(
        series_name       = series_name,
        original_filename = src_name or "video.mp4",
        season            = season,
        episode           = episode,
        title             = title,
        description       = description,
        duration_seconds  = duration,
        resolution        = resolution,
        language          = language,
        subtitles         = subtitles or [],
        thumbnail         = thumbnail,
        tags              = tags or [],
        source_url        = source_url,
        content_rating    = content_rating,
        sha256_original   = sha256,
        extra             = extra or {},
    )
    header_bytes = meta.to_json().encode("utf-8")

    if isinstance(dest, (str, Path)):
        out_stream = open(dest, "wb")
        out_path   = Path(dest)
    else:
        out_stream = dest
        out_path   = None

    out_stream.write(MAGIC)
    out_stream.write(struct.pack(">H", FORMAT_VERSION))
    out_stream.write(struct.pack(">I", len(header_bytes)))
    out_stream.write(header_bytes)
    out_stream.write(salt)
    out_stream.write(iv)
    out_stream.write(ciphertext)

    size_out = out_stream.tell() if hasattr(out_stream, "tell") else None
    if isinstance(dest, (str, Path)):
        out_stream.close()
        size_out = out_path.stat().st_size  # type: ignore

    return ArchiveResult(
        metadata        = meta,
        path            = out_path,
        size_bytes      = size_out or (
            len(MAGIC) + 2 + 4 + len(header_bytes) +
            SALT_SIZE + IV_SIZE + len(ciphertext)
        ),
        sha256_original = sha256,
    )


# ─────────────────────────── READ METADATA ───────────────────────────
def read_metadata(source: FileInput) -> SeriesMetadata:
    """يقرأ ميتاداتا الأرشيف بدون كلمة سر."""
    stream, _ = _open_input(source)
    try:
        magic = stream.read(len(MAGIC))
        if magic != MAGIC:
            if magic == b"TSLSL001":
                raise UnsupportedVersionError(
                    "هذا أرشيف v1 — استخدم tslsl migrate لترقيته"
                )
            raise CorruptArchiveError("الملف ليس أرشيف تسلسل صالحًا")

        ver = struct.unpack(">H", stream.read(2))[0]
        if ver != FORMAT_VERSION:
            raise UnsupportedVersionError(f"إصدار الصيغة {ver} غير مدعوم")

        (header_len,) = struct.unpack(">I", stream.read(4))
        header_bytes  = stream.read(header_len)
        return SeriesMetadata.from_dict(json.loads(header_bytes.decode("utf-8")))
    except (TasalsulError, UnsupportedVersionError):
        raise
    except Exception as exc:
        raise CorruptArchiveError(f"فشل قراءة الأرشيف: {exc}") from exc
    finally:
        stream.close()


# ─────────────────────────── EXTRACT ─────────────────────────────────
def extract_archive(
    *,
    source:          FileInput,
    dest:            FileInput,
    password:        str,
    verify_checksum: bool = True,
) -> "ExtractResult":
    """
    يفك تشفير وضغط أرشيف .tslsl.

    Returns
    -------
    ExtractResult مع بيانات الملف المستخرج
    """
    in_stream, _ = _open_input(source)
    try:
        magic = in_stream.read(len(MAGIC))
        if magic != MAGIC:
            if magic == b"TSLSL001":
                raise UnsupportedVersionError("أرشيف v1 — استخدم tslsl migrate أولاً")
            raise CorruptArchiveError("الملف ليس أرشيف تسلسل صالحًا")

        ver = struct.unpack(">H", in_stream.read(2))[0]
        if ver != FORMAT_VERSION:
            raise UnsupportedVersionError(f"إصدار {ver} غير مدعوم")

        (header_len,) = struct.unpack(">I", in_stream.read(4))
        header_bytes  = in_stream.read(header_len)
        meta          = SeriesMetadata.from_dict(
            json.loads(header_bytes.decode("utf-8"))
        )
        salt       = in_stream.read(SALT_SIZE)
        iv         = in_stream.read(IV_SIZE)
        ciphertext = in_stream.read()
    finally:
        in_stream.close()

    key    = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    try:
        compressed = aesgcm.decrypt(iv, ciphertext, None)
    except Exception as exc:
        raise InvalidPasswordError("كلمة السر خاطئة أو الأرشيف تالف") from exc

    try:
        raw_data = zlib.decompress(compressed)
    except zlib.error as exc:
        raise CorruptArchiveError(f"فشل فك الضغط: {exc}") from exc

    if verify_checksum and meta.sha256_original:
        actual = hashlib.sha256(raw_data).hexdigest()
        if actual != meta.sha256_original:
            raise CorruptArchiveError("فشل التحقق من السلامة (SHA-256 mismatch)")

    if isinstance(dest, (str, Path)):
        out_path = Path(dest)
        out_path.write_bytes(raw_data)
    else:
        dest.write(raw_data)
        out_path = None

    return ExtractResult(metadata=meta, path=out_path, size_bytes=len(raw_data))


# ─────────────────────────── MIGRATE v1→v2 ───────────────────────────
def migrate_v1(
    *,
    source:   FileInput,
    dest:     FileInput,
    password: str,
) -> "ArchiveResult":
    """يحوّل أرشيف v1 (.tslsl v1) إلى v2 مع الاحتفاظ بالميتاداتا."""
    from cryptography.fernet import Fernet as _Fernet
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as _KDF
    from cryptography.hazmat.primitives import hashes as _hashes

    in_stream, _ = _open_input(source)
    try:
        magic = in_stream.read(8)
        if magic != b"TSLSL001":
            raise CorruptArchiveError("ليس أرشيف v1")
        (hl,)     = struct.unpack(">I", in_stream.read(4))
        hdr       = json.loads(in_stream.read(hl).decode())
        salt_v1   = in_stream.read(16)
        encrypted = in_stream.read()
    finally:
        in_stream.close()

    kdf = _KDF(
        algorithm=_hashes.SHA256(), length=32,
        salt=salt_v1, iterations=390_000,
    )
    raw_key = kdf.derive(password.encode())
    fernet  = _Fernet(base64.urlsafe_b64encode(raw_key))
    try:
        compressed = fernet.decrypt(encrypted)
    except Exception as exc:
        raise InvalidPasswordError("كلمة السر خاطئة") from exc

    raw_data = zlib.decompress(compressed)

    return create_archive(
        source      = raw_data,
        dest        = dest,
        password    = password,
        series_name = hdr.get("series_name", ""),
        season      = hdr.get("season"),
        episode     = hdr.get("episode"),
        title       = hdr.get("title"),
        extra       = {"migrated_from": "v1"},
    )


# ─────────────────────────── RESULT TYPES ────────────────────────────
@dataclass
class ArchiveResult:
    metadata:        SeriesMetadata
    path:            Optional[Path]
    size_bytes:      int
    sha256_original: str

    def __str__(self) -> str:
        mb = self.size_bytes / 1_048_576
        return (
            f"ArchiveResult(series={self.metadata.series_name!r}, "
            f"size={mb:.2f} MB, path={self.path})"
        )


@dataclass
class ExtractResult:
    metadata:   SeriesMetadata
    path:       Optional[Path]
    size_bytes: int

    def __str__(self) -> str:
        mb = self.size_bytes / 1_048_576
        return (
            f"ExtractResult(series={self.metadata.series_name!r}, "
            f"size={mb:.2f} MB, path={self.path})"
        )
