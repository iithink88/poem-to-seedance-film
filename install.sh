#!/usr/bin/env bash
# poem-to-seedance-film installer for macOS / Linux
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="poem-to-seedance-film"
TARGET="$HOME/.workbuddy/skills/$SKILL_NAME"

echo "== poem-to-seedance-film installer =="
echo "Source : $SRC"
echo "Target : $TARGET"

if [ ! -f "$SRC/SKILL.md" ]; then
  echo "ERROR: SKILL.md not found next to this script. Keep the extracted folder intact." >&2
  exit 1
fi

if [ -d "$TARGET" ]; then
  STAMP="$(date +%Y%m%d_%H%M%S)"
  mv "$TARGET" "$TARGET.bak-$STAMP"
  echo "Existing install backed up to: $TARGET.bak-$STAMP"
fi

mkdir -p "$TARGET"
for item in SKILL.md README.md INSTALL.md LICENSE scripts references examples; do
  if [ -e "$SRC/$item" ]; then
    cp -R "$SRC/$item" "$TARGET/"
    echo "  copied $item"
  fi
done

echo
echo "Installed. Checking dependencies..."
if command -v python3 >/dev/null 2>&1; then
  echo "  Python : OK ($(python3 --version 2>&1))"
else
  echo "  Python : NOT FOUND - install Python 3.10+"
fi

if command -v ffmpeg >/dev/null 2>&1; then
  echo "  ffmpeg : OK"
else
  echo "  ffmpeg : NOT FOUND - install ffmpeg (with libass)"
fi

echo
echo "Done. Restart WorkBuddy, then say: 把《山居秋暝》做成古诗词短片"
echo "Full guide: INSTALL.md"
