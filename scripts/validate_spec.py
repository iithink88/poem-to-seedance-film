#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 spec.json。用法: python validate_spec.py <spec.json>"""
import json
import sys
from pathlib import Path

PRESETS = {
    "songyin_wanyue", "shanshui_tianyuan", "jiye_jilv",
    "hanjiang_guji", "yueye_xiangsi", "haofang_jianghe",
}

TOP_REQUIRED = [
    "schema_version", "title", "author", "dynasty", "genre", "preset",
    "poem_lines", "duration", "aspect_ratio", "resolution", "story",
    "mood_arc", "adaptations", "time", "season", "place", "palette",
    "protagonist", "scenes", "shots", "style_block", "beauty_block",
    "negative_global", "sound_bed", "narration", "continuity",
]

SHOT_REQUIRED = [
    "n", "seconds", "name", "size", "start", "action", "camera",
    "end", "link", "ref_scene", "line", "subtitle", "sound", "risk",
]


def validate(spec):
    errors, warnings = [], []

    for k in TOP_REQUIRED:
        if k not in spec or spec[k] in (None, "", []):
            errors.append(f"缺少顶层字段: {k}")

    if spec.get("schema_version") != 1:
        errors.append("schema_version 必须为 1")
    if spec.get("preset") and spec["preset"] not in PRESETS:
        errors.append(f"preset 非法: {spec['preset']}，应为 {sorted(PRESETS)}")

    d = spec.get("duration")
    if not isinstance(d, int) or not (4 <= d <= 30):
        errors.append("duration 必须是 4~30 的整数")

    # 主角
    p = spec.get("protagonist") or {}
    for k in ("identity", "face", "hair", "outfit", "props", "taboo"):
        if not p.get(k):
            errors.append(f"protagonist 缺少: {k}")

    # 场景
    scenes = spec.get("scenes") or []
    if len(scenes) != 3:
        errors.append(f"scenes 必须恰好 3 个，当前 {len(scenes)}")
    else:
        for i, sc in enumerate(scenes):
            want = "ABC"[i]
            if sc.get("key") != want:
                errors.append(f"scenes[{i}].key 应为 {want}")
            for k in ("name", "role", "detail", "light", "avoid"):
                if not sc.get(k):
                    errors.append(f"scenes[{i}] 缺少: {k}")
        if "方向" not in scenes[1].get("detail", ""):
            warnings.append("场景B 的 detail 建议明确写出运动方向（如「朝右前方」）")
        if "天空" not in scenes[2].get("detail", ""):
            warnings.append("场景C 的 detail 建议留出开阔天空")

    # 镜头
    shots = spec.get("shots") or []
    if len(shots) != 6:
        errors.append(f"shots 必须恰好 6 个，当前 {len(shots)}")
    else:
        total = 0
        for i, sh in enumerate(shots, 1):
            for k in SHOT_REQUIRED:
                if k not in sh:
                    errors.append(f"shots[{i-1}] 缺少: {k}")
            if sh.get("n") != i:
                errors.append(f"shots[{i-1}].n 应为 {i}")
            sec = sh.get("seconds")
            if not isinstance(sec, int) or sec < 2:
                errors.append(f"shots[{i-1}].seconds 应为 >=2 的整数")
            else:
                total += sec
            if sh.get("ref_scene") not in ("A", "B", "C"):
                errors.append(f"shots[{i-1}].ref_scene 应为 A/B/C")
            act = sh.get("action", "")
            if act.count("，") > 6:
                warnings.append(f"镜头{i} action 偏长，注意「一镜一个主要动作」")
        if isinstance(d, int) and total != d:
            errors.append(f"6 镜秒数合计 {total} != duration {d}")
        subtitled = sum(1 for sh in shots if sh.get("subtitle"))
        if subtitled < 4:
            errors.append(f"至少 4 镜要有字幕，当前 {subtitled}")
        if not any("不出现人物" in "".join(str(sh.get(k, "")) for k in ("start", "action", "end"))
                   or "无人物" in "".join(str(sh.get(k, "")) for k in ("start", "action", "end"))
                   for sh in shots):
            warnings.append("建议至少一镜写「本镜不出现人物」用于结尾舒展")

    # 朗读
    nar = spec.get("narration") or {}
    if not nar.get("voice"):
        errors.append("narration.voice 缺失")
    if not nar.get("lines"):
        errors.append("narration.lines 缺失")
    elif not isinstance(nar["lines"], list):
        errors.append("narration.lines 应为数组")

    # 风格块
    for k in ("style_block", "beauty_block", "negative_global"):
        if len(spec.get(k, "")) < 40:
            errors.append(f"{k} 过短，必须从 style-bible.md 复制完整段落")
    if "不发光" not in spec.get("beauty_block", ""):
        errors.append("beauty_block 必须包含官方硬约束「人物为正常人眼、不发光」")

    # 字幕文案与诗句一致性提醒
    poem = "".join(spec.get("poem_lines") or [])
    for i, sh in enumerate(shots, 1):
        sub = (sh.get("subtitle") or "").rstrip("，。！？、；：,.!?")
        if sub and sub not in poem:
            warnings.append(f"镜头{i} 字幕「{sub}」不在原诗中，确认是否为有意改编")

    return errors, warnings


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_spec.py <spec.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[FAIL] 无法读取 spec: {e}", file=sys.stderr)
        return 3

    errors, warnings = validate(spec)
    for w in warnings:
        print(f"[WARN] {w}")
    if errors:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        print(f"\n校验失败：{len(errors)} 个错误，{len(warnings)} 条提醒", file=sys.stderr)
        return 1
    print(f"[OK] spec 校验通过：{spec.get('title')}｜{len(spec.get('shots', []))} 镜 / "
          f"{spec.get('duration')}s｜{len(warnings)} 条提醒")
    return 0


if __name__ == "__main__":
    sys.exit(main())
