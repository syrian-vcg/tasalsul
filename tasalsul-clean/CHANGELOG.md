# Changelog

جميع التغييرات الملحوظة لهذا المشروع موثّقة هنا.
الصيغة مبنية على [Keep a Changelog](https://keepachangelog.com/ar/).

---

## [0.1.0] — 2026-06-26

### جديد
- **محرك v2 كامل**: AES-256-GCM بدلاً من Fernet
- **بث (streaming)**: `create_archive` و`extract_archive` تقبلان `bytes`, `BinaryIO`, أو `Path`
- **ميتاداتا موسّعة**: وصف، مدة، دقة، لغة، ترجمات، صورة مصغّرة، وسوم، تصنيف عمري
- **أمر `migrate`** في CLI لترقية أرشيفات v1 إلى v2
- **أمر `--json`** في `tslsl info` لمخرج JSON منظّم
- **GitHub Actions** لنشر تلقائي على PyPI عند وسم الإصدار
- **أيقونة `.tslsl`** SVG رسمية في `assets/tslsl-icon.svg`

### تحسينات
- اختبارات شاملة (35+ حالة اختبار)
- بنية حزمة `src/` layout
- توافق Python 3.9–3.12 وجميع أنظمة التشغيل

### تغييرات كاسرة
- صيغة الملف v2 (`TSLSL002`) — استخدم `tslsl migrate` لترقية الأرشيفات القديمة
