#!/usr/bin/env bash
# bump.sh — رفع إصدار جديد تلقائياً
# الاستخدام: bash bump.sh X.Y.Z

set -e

VERSION="${1:?استخدم: bash bump.sh X.Y.Z}"

echo "🔄 تحديث الإصدار إلى $VERSION ..."

sed -i "s/^version *= *\".*\"/version     = \"$VERSION\"/" pyproject.toml
sed -i "s/__version__ *= *\".*\"/__version__ = \"$VERSION\"/" src/tasalsul/__init__.py

echo "📝 Commit ..."
git add pyproject.toml src/tasalsul/__init__.py
git commit -m "chore: bump version to $VERSION"

echo "🏷️  إنشاء tag v$VERSION ..."
git tag "v$VERSION"

echo "🚀 Push ..."
git push origin main "v$VERSION"

echo "✅ تم! الـ workflow سيشتغل تلقائياً على GitHub Actions."
