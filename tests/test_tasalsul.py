"""اختبارات تسلسل v2."""

import io
import pytest
from tasalsul import (
    create_archive,
    extract_archive,
    read_metadata,
    migrate_v1,
    SeriesMetadata,
    ThumbnailMeta,
    SubtitleRef,
    InvalidPasswordError,
    CorruptArchiveError,
    UnsupportedVersionError,
)

FAKE_VIDEO = b"FAKE_VIDEO_CONTENT_" * 200
PASSWORD   = "كلمة_سر_آمنة_123"


# ── helpers ────────────────────────────────────────────────────────────
def make_archive(**kwargs):
    buf = io.BytesIO()
    kw  = dict(
        source      = FAKE_VIDEO,
        dest        = buf,
        password    = PASSWORD,
        series_name = "Breaking Bad",
        season      = 1,
        episode     = 1,
        title       = "Pilot",
    )
    kw.update(kwargs)
    create_archive(**kw)
    buf.seek(0)
    return buf.read()


# ── create / extract round-trip ────────────────────────────────────────
class TestRoundTrip:
    def test_bytes_in_out(self):
        arch   = make_archive()
        result = extract_archive(source=arch, dest=io.BytesIO(), password=PASSWORD)
        assert result.metadata.series_name == "Breaking Bad"

    def test_data_integrity(self):
        arch = make_archive()
        buf  = io.BytesIO()
        extract_archive(source=arch, dest=buf, password=PASSWORD)
        buf.seek(0)
        assert buf.read() == FAKE_VIDEO

    def test_file_paths(self, tmp_path):
        src = tmp_path / "ep.mp4"
        dst = tmp_path / "ep.tslsl"
        src.write_bytes(FAKE_VIDEO)
        create_archive(source=src, dest=dst, password=PASSWORD, series_name="Test")
        out = tmp_path / "out.mp4"
        extract_archive(source=dst, dest=out, password=PASSWORD)
        assert out.read_bytes() == FAKE_VIDEO

    def test_bytesio_in_file_out(self, tmp_path):
        dst = tmp_path / "ep.tslsl"
        create_archive(
            source=io.BytesIO(FAKE_VIDEO),
            dest=dst,
            password=PASSWORD,
            series_name="IO Test",
        )
        assert dst.exists()


# ── metadata ───────────────────────────────────────────────────────────
class TestMetadata:
    def test_read_without_password(self):
        arch = make_archive(
            description    = "حلقة رائعة",
            language       = "ar",
            resolution     = "1920x1080",
            duration       = 2700.5,
            tags           = ["drama", "crime"],
            content_rating = "PG-13",
        )
        meta = read_metadata(arch)
        assert meta.series_name    == "Breaking Bad"
        assert meta.season         == 1
        assert meta.episode        == 1
        assert meta.language       == "ar"
        assert meta.resolution     == "1920x1080"
        assert abs(meta.duration_seconds - 2700.5) < 0.01
        assert "drama" in meta.tags
        assert meta.content_rating == "PG-13"
        assert meta.format_version == 2
        assert meta.encryption     == "aes-256-gcm-pbkdf2"

    def test_thumbnail_embedded(self):
        thumb = ThumbnailMeta(data_b64="abc123", mime="image/jpeg",
                              width=320, height=180)
        arch = make_archive(thumbnail=thumb)
        meta = read_metadata(arch)
        assert meta.thumbnail.data_b64 == "abc123"
        assert meta.thumbnail.width    == 320

    def test_subtitles_embedded(self):
        subs = [SubtitleRef(language="ar", label="العربية", data_b64="c3Vic")]
        arch = make_archive(subtitles=subs)
        meta = read_metadata(arch)
        assert len(meta.subtitles) == 1
        assert meta.subtitles[0].language == "ar"

    def test_metadata_json_roundtrip(self):
        meta  = SeriesMetadata(series_name="Test", original_filename="v.mp4",
                               season=2, episode=5)
        meta2 = SeriesMetadata.from_json(meta.to_json())
        assert meta2.season  == 2
        assert meta2.episode == 5


# ── error handling ─────────────────────────────────────────────────────
class TestErrors:
    def test_wrong_password(self):
        arch = make_archive()
        with pytest.raises(InvalidPasswordError):
            extract_archive(source=arch, dest=io.BytesIO(), password="خاطئة")

    def test_corrupt_archive(self):
        arch = bytearray(make_archive())
        arch[50] ^= 0xFF
        with pytest.raises((CorruptArchiveError, Exception)):
            read_metadata(bytes(arch))

    def test_corrupt_payload(self):
        arch = bytearray(make_archive())
        arch[-10] ^= 0xFF
        with pytest.raises((InvalidPasswordError, CorruptArchiveError)):
            extract_archive(source=bytes(arch), dest=io.BytesIO(), password=PASSWORD)

    def test_invalid_magic(self):
        with pytest.raises(CorruptArchiveError):
            read_metadata(b"NOTVALID" + b"\x00" * 100)

    def test_v1_magic_gives_unsupported_error(self):
        import struct, json, zlib, base64
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        salt   = b"\x00" * 16
        kdf    = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                             salt=salt, iterations=390_000)
        key    = base64.urlsafe_b64encode(kdf.derive(PASSWORD.encode()))
        fernet = Fernet(key)
        comp   = zlib.compress(FAKE_VIDEO)
        enc    = fernet.encrypt(comp)
        hdr    = json.dumps({"series_name": "x", "original_filename": "x.mp4",
                             "sha256_original": ""}).encode()
        v1 = b"TSLSL001" + struct.pack(">I", len(hdr)) + hdr + salt + enc
        with pytest.raises(UnsupportedVersionError):
            read_metadata(v1)


# ── migrate v1→v2 ──────────────────────────────────────────────────────
class TestMigrate:
    def _make_v1(self):
        import struct, json, zlib, base64
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        salt  = b"\xAB" * 16
        kdf   = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                            salt=salt, iterations=390_000)
        key   = base64.urlsafe_b64encode(kdf.derive(PASSWORD.encode()))
        f     = Fernet(key)
        comp  = zlib.compress(FAKE_VIDEO)
        enc   = f.encrypt(comp)
        hdr   = json.dumps({
            "series_name": "Old Show", "original_filename": "ep.mp4",
            "season": 1, "episode": 2, "title": None,
            "sha256_original": "", "compression": "zlib",
            "encryption": "fernet", "created_at": "2024-01-01T00:00:00",
            "extra": {},
        }).encode()
        return b"TSLSL001" + struct.pack(">I", len(hdr)) + hdr + salt + enc

    def test_migrate_preserves_data(self):
        v1   = self._make_v1()
        dest = io.BytesIO()
        migrate_v1(source=v1, dest=dest, password=PASSWORD)
        dest.seek(0)
        v2   = dest.read()
        meta = read_metadata(v2)
        assert meta.series_name    == "Old Show"
        assert meta.format_version == 2

        buf = io.BytesIO()
        extract_archive(source=v2, dest=buf, password=PASSWORD,
                        verify_checksum=False)
        buf.seek(0)
        assert buf.read() == FAKE_VIDEO
