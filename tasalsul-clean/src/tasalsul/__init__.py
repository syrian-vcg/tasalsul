"""
تسلسل (Tasalsul) — أرشيف مضغوط ومشفّر للمسلسلات.
صيغة .tslsl v2: AES-256-GCM + zlib + ميتاداتا موسّعة.

Quick start
-----------
>>> from tasalsul import create_archive, extract_archive, read_metadata
>>> result = create_archive(
...     source="episode.mp4",
...     dest="episode.tslsl",
...     password="سري",
...     series_name="Breaking Bad",
...     season=1, episode=1,
... )
>>> meta = read_metadata("episode.tslsl")
>>> print(meta.series_name)
"""

from .engine import (
    create_archive,
    extract_archive,
    read_metadata,
    migrate_v1,
    ArchiveResult,
    ExtractResult,
    SeriesMetadata,
    SubtitleRef,
    ThumbnailMeta,
    TasalsulError,
    InvalidPasswordError,
    CorruptArchiveError,
    UnsupportedVersionError,
    FORMAT_VERSION,
    MAGIC,
)

__version__ = "0.1.0"
__author__  = "Tasalsul Contributors"
__license__ = "MIT"

__all__ = [
    "create_archive",
    "extract_archive",
    "read_metadata",
    "migrate_v1",
    "ArchiveResult",
    "ExtractResult",
    "SeriesMetadata",
    "SubtitleRef",
    "ThumbnailMeta",
    "TasalsulError",
    "InvalidPasswordError",
    "CorruptArchiveError",
    "UnsupportedVersionError",
    "FORMAT_VERSION",
    "MAGIC",
    "__version__",
]
