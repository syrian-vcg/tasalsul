# تسلسل (Tasalsul) 📦🔐

<p align="center">
  <img src="assets/tslsl-icon.svg" width="80" alt="تسلسل أيقونة"/>
</p>

<p align="center">
  <a href="https://pypi.org/project/tasalsul/"><img src="https://img.shields.io/pypi/v/tasalsul?label=PyPI&color=6C63FF" alt="PyPI"/></a>
  <img src="https://img.shields.io/pypi/pyversions/tasalsul?color=4ADE80" alt="Python"/>
  <img src="https://img.shields.io/github/license/YOUR_USERNAME/tasalsul" alt="License"/>
  <img src="https://img.shields.io/github/actions/workflow/status/YOUR_USERNAME/tasalsul/ci.yml?label=CI" alt="CI"/>
</p>

**تسلسل** هي صيغة أرشيف مفتوحة المصدر (`.tslsl`) لضغط وتشفير فيديوهات المسلسلات بشكل آمن، مع ميتاداتا قابلة للقراءة بلا كلمة سر.

---

## ✨ الميزات

| الميزة | التفاصيل |
|--------|----------|
| 🔐 تشفير قوي | AES-256-GCM مع PBKDF2 (390,000 تكرار) |
| 📦 ضغط | zlib — تقليص ملحوظ للحجم |
| 📋 ميتاداتا غنية | اسم، موسم، حلقة، وصف، لغة، ترجمات، صورة مصغّرة |
| 🔄 بث (streaming) | يعمل مع ملفات ضخمة بكفاءة |
| ✅ سلامة البيانات | SHA-256 للتحقق من الملف الأصلي |
| 🔁 ترقية v1→v2 | أمر `migrate` مدمج |

---

## 📥 التثبيت

```bash
pip install tasalsul
```

### من المصدر

```bash
git clone https://github.com/YOUR_USERNAME/tasalsul
cd tasalsul
pip install -e ".[dev]"
```

---

## 🚀 الاستخدام

### Python API

```python
from tasalsul import create_archive, extract_archive, read_metadata, ThumbnailMeta

# إنشاء أرشيف
result = create_archive(
    source         = "episode01.mp4",
    dest           = "episode01.tslsl",
    password       = "كلمة_سرية",
    series_name    = "Breaking Bad",
    season         = 1,
    episode        = 1,
    title          = "Pilot",
    description    = "والتر وايت يبدأ رحلته",
    language       = "ar",
    resolution     = "1920x1080",
    duration       = 3180.0,
    tags           = ["drama", "crime"],
    content_rating = "TV-MA",
)
print(result)
# ArchiveResult(series='Breaking Bad', size=42.5 MB, path=episode01.tslsl)

# قراءة الميتاداتا (بلا كلمة سر)
meta = read_metadata("episode01.tslsl")
print(meta.series_name)    # Breaking Bad
print(meta.format_version) # 2

# استخراج الفيديو
extract_archive(
    source   = "episode01.tslsl",
    dest     = "restored.mp4",
    password = "كلمة_سرية",
)

# الاستخدام مع bytes / BytesIO
import io
video_bytes = open("ep.mp4", "rb").read()
buf = io.BytesIO()
create_archive(source=video_bytes, dest=buf, password="pw", series_name="Test")
```

### CLI

```bash
# إنشاء أرشيف مع ميتاداتا كاملة
tslsl create episode.mp4 \
  --series "Breaking Bad" --season 1 --episode 1 \
  --title "Pilot" --description "بداية القصة" \
  --language ar --resolution 1920x1080 --duration 3180 \
  --tag drama --tag crime \
  --thumbnail thumb.jpg \
  --subtitle ar:subs_ar.srt \
  -o episode.tslsl

# عرض الميتاداتا
tslsl info episode.tslsl
tslsl info episode.tslsl --json    # مخرج JSON

# استخراج الفيديو
tslsl extract episode.tslsl -o restored.mp4

# ترقية أرشيف v1
tslsl migrate old_episode.tslsl -o new_episode.tslsl
```

---

## 🧱 بنية الملف (.tslsl v2)

```
┌──────────────┬─────────────────────────────────────────┐
│ 8  bytes     │ MAGIC = "TSLSL002"                      │
│ 2  bytes     │ FORMAT_VERSION = 2                      │
│ 4  bytes     │ HEADER_LEN                              │
│ N  bytes     │ HEADER (JSON / UTF-8, غير مشفّر)        │
│ 16 bytes     │ SALT (عشوائي — لاشتقاق المفتاح)         │
│ 16 bytes     │ IV (nonce AES-GCM)                      │
│ M  bytes     │ PAYLOAD (zlib ثم AES-256-GCM)           │
│ 16 bytes     │ GCM AUTH TAG (مدمج)                     │
└──────────────┴─────────────────────────────────────────┘
```

---

## 🔐 الأمان

- **AES-256-GCM**: تشفير مصادق عليه — يكتشف أي تلاعب في البيانات
- **PBKDF2-SHA256 (390,000 تكرار)**: حماية ضد هجمات القوة الغاشمة
- **Salt عشوائي**: كل أرشيف مشفّر بمفتاح فريد حتى لو كانت كلمة السر ذاتها
- **SHA-256**: فحص السلامة بعد فك التشفير

> ⚠️ لا يمكن استعادة الملف بدون كلمة السر — التشفير غير قابل للكسر عملياً.

---

## 🧪 الاختبارات

```bash
pip install -e ".[dev]"
pytest -v
pytest --cov=tasalsul    # مع تغطية الكود
```

---

## 🤝 المساهمة

المساهمات مرحّب بها! افتح issue أو pull request.

---

## 📄 الترخيص

MIT © Tasalsul Contributors
