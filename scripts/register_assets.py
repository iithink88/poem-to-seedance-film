#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 ImageGen 产出的图片归位成 manifest.json 约定的 4 个标准文件名。

约定：每次调用 ImageGen 时使用独立的 output_dir：
    <项目>/assets/gen_01  (主角三视图)
    <项目>/assets/gen_02  (场景 A)
    <项目>/assets/gen_03  (场景 B)
    <项目>/assets/gen_04  (场景 C)

用法:
    python register_assets.py --project <项目目录>
    python register_assets.py --project <项目目录> --from <含 4 张图片的目录>  # 用户自备素材，按文件名顺序映射
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--from", dest="src", default=None, help="用户自备素材目录（按文件名顺序取前 4 张）")
    args = ap.parse_args()

    root = Path(args.project).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    targets = [root / a["file"] for a in manifest["assets"]]

    picked = []
    if args.src:
        src = Path(args.src).resolve()
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS)
        if len(files) < 4:
            print(f"[FAIL] --from 目录中只找到 {len(files)} 张图片，需要 4 张", file=sys.stderr)
            return 3
        picked = files[:4]
    else:
        for i in range(1, 5):
            folder = root / "assets" / f"gen_{i:02d}"
            files = sorted((p for p in folder.glob("*") if p.suffix.lower() in EXTS),
                           key=lambda p: p.stat().st_mtime)
            if not files:
                print(f"[FAIL] {folder} 里没有图片；请确认第 {i} 次生图成功", file=sys.stderr)
                return 3
            picked.append(files[-1])

    for src, dst in zip(picked, targets):
        dst.parent.mkdir(parents=True, exist_ok=True)
        # 统一转 PNG，保证 base64 data URL 的 mime 稳定
        with Image.open(src) as im:
            im.convert("RGB").save(dst, "PNG")
        print(f"[OK] {src.name} -> {dst.relative_to(root)}")

    missing = [str(t) for t in targets if not t.is_file()]
    if missing:
        print("[FAIL] 以下文件仍缺失: " + ", ".join(missing), file=sys.stderr)
        return 4
    print("[OK] 4 张参考图全部就位：" + ", ".join(
        a["id"] + "=" + a["file"] for a in manifest["assets"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
