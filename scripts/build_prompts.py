#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec.json -> 全套提示词 / 分镜表 / 字幕 / 时间轴 / manifest（纯确定性渲染，不调用任何模型）

用法:
    python build_prompts.py <spec.json> [--out <项目目录>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_spec import validate  # noqa: E402

ASSET_FILES = {
    "图片1": ("assets/01_character.png", "01_主角三视图.txt"),
    "图片2": ("assets/02_scene_A.png", "02_场景A.txt"),
    "图片3": ("assets/03_scene_B.png", "03_场景B.txt"),
    "图片4": ("assets/04_scene_C.png", "04_场景C.txt"),
}

DEFAULT_TAIL = (
    "全片保持人物面容、发型、发饰与服装一致，前后使用同一载具与道具，光色与时间段连贯；"
    "镜头之间自然直接切换，通过视线、动作与行进方向建立连贯关系，不使用图片变形、溶解或幻灯片效果。"
    "人物为正常人眼、不发光，手指与道具接触自然。4K 细节，画面稳定无突变。"
    "无对白、无旁白、无背景音乐、无字幕、无文字与水印，原词朗读和配乐留待后期添加。"
    "{duration}s，{resolution}。"
)

CN_NUM = ["一", "二", "三", "四", "五", "六"]


# --------------------------------------------------------------------------- #
# 渲染器
# --------------------------------------------------------------------------- #
def render_character(spec: dict) -> str:
    p = spec["protagonist"]
    props = "、".join(p["props"]) if p["props"] else "无"
    preset_cn = spec.get("_preset_cn", "东方古典")
    hair_extra = "" if "三个角度" in p["hair"] else "三个角度保持发型形状、发量与发饰位置完全一致。"
    return f"""{preset_cn}短片主角定妆设定图，写实摄影质感。同一位成年人物的全身三视图，横向排列，从左到右分别为正面、左侧面、背面。三个人像是同一个角色的不同角度，身高、体型、服装、发型和配饰完全一致。

【人物形象】
{p['identity']}。{p['face']}。

【发型与配饰】
{p['hair']}。{hair_extra}{p['taboo']}。

【统一服装】
{p['outfit']}

【道具关联】
本片会出现的道具：{props}。道具不出现在这张三视图中，仅在视频中出现，但需与服装气质统一。

【姿势与构图】
三个视角均自然站立，身体直立、双肩放松，双臂略微离开身体，双手自然下垂，不遮挡腰部服装结构。正面朝向镜头，侧面严格转向左侧，背面完全背向镜头，不回头。
三个全身人像等比例、等大小、等间距，头顶和脚底分别对齐。从头顶到鞋底完整入画，人物之间不重叠，衣袖不越入相邻人物区域。

【背景与光线】
干净的浅暖灰色无缝背景，无场景、无道具。均匀柔和的摄影棚光线，肤色自然，衣料颜色准确，暗部清楚，便于辨认五官、发型和服装结构。不使用强逆光、浅景深虚化或浓重滤镜。

整体为精致自然的古装角色定妆照，不是插画、游戏角色或服装效果图。画面无文字、无角度标签、无水印。

【色彩校准】
本片服装色系为{spec['palette']['garment']}，光色为{spec['palette']['light']}，环境主色为{spec['palette']['environment']}。三视图只负责准确还原衣料与配饰固有色，使用均匀柔和摄影棚光，不预演影片的逆光氛围，避免色偏。

避免：三个不同人物、不同衣服、不同发型、夸张身材、浓妆、复杂珠翠、透明内搭、赤脚、手部变形、肢体缺失、人物裁切、视角混乱、画面文字与水印、强逆光、浓重滤镜、场景与道具。"""


_ENV_REPL = [
    ("穿透发丝与细薄纱衣袖", "照亮荷叶边缘与水面薄雾"),
    ("面部有自然柔和补光，肤色温润通透", "暗部柔和有层次，色彩温润通透"),
    ("真实皮肤纹理、", ""),
    ("在发梢、纱袖边缘与水面", "在荷叶边缘、苇叶与水面"),
    ("微风持续轻动衣袖、碎发、纱帘与枝叶", "微风持续轻动荷叶、苇叶与水边枝叶"),
    ("人物为正常人眼、不发光，情绪用微表情表达，不使用任何特效化表现。", ""),
    ("情绪克制留余韵", "画面空阔留余韵"),
    ("含蓄安静的诗意与浪漫气息", "含蓄安静的环境诗意与浪漫气息"),
]


def _env_style(text: str) -> str:
    """场景定样图必须无人物：把风格块里的人物/服装词替换为纯环境词，避免模型画出人。"""
    for a, b in _ENV_REPL:
        text = text.replace(a, b)
    return text.strip()


def render_scene(spec: dict, sc: dict) -> str:
    pal = spec["palette"]
    return f"""{spec.get('_preset_cn','东方古典')}环境定样图，写实古装电影质感，16:9 横屏，无人物、无鸟。场景 {sc['key']}「{sc['name']}」，用途：{sc['role']}。

【空间与内容】
{sc['detail']}
空间关系清楚、可走通，与前一场景和下一场景在位置上连贯。

【光线与色板】
{sc['light']}。全片色彩呼应：服装{pal['garment']}、光色{pal['light']}、点缀{pal['accent']}；本图环境主色为{pal['environment']}。亮部通透、暗部有层次，{pal['environment']}不发黄、不褪成灰白。本图不出现任何人物与衣物。

【质感】
{_env_style(spec['style_block'])}

{_env_style(spec['beauty_block'])}

【本图避免】
{sc['avoid']}；另避免任何人物、动物、宫殿、仙侠建筑、现代设施、大面积浓雾、密集花海、粗重橙黄滤镜、文字、水印、logo。"""


SCENE_TO_IMAGE = {"A": "图片2", "B": "图片3", "C": "图片4"}


def _shot_block(spec: dict, sh: dict, scene_by_key: dict) -> str:
    ref_name = SCENE_TO_IMAGE[sh["ref_scene"]]
    sc = scene_by_key[sh["ref_scene"]]
    idx = int(sh["n"]) - 1
    parts = [
        f"【镜头{CN_NUM[idx]}，{sh['name']}｜约 {sh['seconds']}s｜{sh['size']}】",
        f"参考@{ref_name}（{sc['name']}）的空间结构与光色。静帧起始：{sh['start']}。",
        f"主体动作：{sh['action']}。",
        f"摄影机：{sh['camera']}。",
        f"结束状态：{sh['end']}。",
    ]
    if sh.get("sound"):
        parts.append(f"本镜声音：{sh['sound']}。")
    parts.append(f"与下一镜的衔接：{sh['link']}。")
    return " ".join(parts)


def render_video(spec: dict, shots: list, duration: int, segment: str = "") -> str:
    scene_by_key = {s["key"]: s for s in spec["scenes"]}
    pal = spec["palette"]
    p = spec["protagonist"]
    head = (
        f"生成视频：生成一支 {duration} 秒的{spec.get('_preset_cn','东方古典')}诗意短片，"
        f"完整表现{spec['dynasty']}·{spec['author']}《{spec['title']}》的情景。{segment}"
    )

    binding = f"""【参考素材 · 素材绑定】
@图片1 中的{p['identity'].split('，')[0]}为全片唯一主角，保持她的面容、发型、发饰与服装在全片完全一致。
@图片2（{scene_by_key['A']['name']}）用于参考开场环境的亭台、石阶、水面与{spec['time']}光色。
@图片3（{scene_by_key['B']['name']}）用于参考中段环境的空间层次、载具、水路与行进构图。
@图片4（{scene_by_key['C']['name']}）用于参考结尾的开阔水面与天空。
@图片2、@图片3、@图片4 均为无人物环境定样图，人物身份一律以@图片1 中的女子为准。不要复制人物资产图的白底、拼板排版或重复人像。前后使用同一载具与同一套道具，保持衣服、道具和光色连贯。"""

    style = f"""【整体风格】
{spec['style_block']}

{spec['beauty_block']}

服装：{pal['garment']}；环境：{pal['environment']}；光色：{pal['light']}；点缀：{pal['accent']}。{spec['time']}，{spec['season']}，{spec['place']}。"""

    cont = spec["continuity"].strip().rstrip("。；;")
    continuity = f"""【贯穿全片的一致性】
{cont}。不整体染成浓重橙黄色，绿植保持{pal['environment']}。人物为正常人眼、不发光，情绪用微表情与克制动作表达，不使用任何特效化表现。"""

    mood = f"【情绪与节奏】\n{spec['mood_arc']}。按以下 {len(shots)} 个镜头自然分配 {duration} 秒节奏，不要求每镜等长，一镜一个主要动作。"

    blocks = "\n\n".join(_shot_block(spec, sh, scene_by_key) for sh in shots)

    tail = spec.get("video_tail") or DEFAULT_TAIL
    tail = tail.format(duration=duration, resolution=spec["resolution"])

    closing = f"""【镜头与声音】
镜头之间自然直接切换，通过视线、动作与行进方向建立连贯关系，不使用图片变形、溶解或幻灯片效果。
生成期只保留{spec['sound_bed']}。

【避免】
{spec['negative_global']}

{tail}"""

    return "\n\n".join([head, binding, style, continuity, mood, blocks, closing])


def _short(text: str, n: int) -> str:
    """压缩到 n 个字符，尽量在标点处收尾。"""
    text = re.sub(r"\s+", "", text or "")
    if len(text) <= n:
        return text
    cut = text[:n]
    for p in ("；", "，", "。", "、"):
        i = cut.rfind(p)
        if i > n * 0.7:
            return cut[:i + 1]
    return cut


def _seg(text: str, n: int) -> str:
    """压缩成不带句末标点的短语，供统一分隔符拼接。"""
    return _short(text, n).rstrip("，。；、：,.!?")


def render_video_compact(spec: dict, shots: list, duration: int, segment: str = "") -> str:
    """
    内置视频生成后端（如 minimax-video-h3）专用：prompt <= 2000 字符。
    结构仍遵守 Seedance 2.5 官方「素材绑定 → 概述 → 分镜 → 负向尾句」，但砍掉冗余复述。
    """
    sc = {s["key"]: s for s in spec["scenes"]}
    pal = spec["palette"]
    p = spec["protagonist"]
    head = (
        f"生成 {duration} 秒{spec.get('_preset_cn','东方古典')}写实诗意短片，"
        f"表现{spec['author']}《{spec['title']}》。{spec['aspect_ratio']}，{spec['resolution']}。{segment}"
    )
    binding = (
        f"【参考素材】@图片1 中的{p['identity'].split('，')[0]}为全片唯一主角，面容、发型、发饰与服装始终一致；"
        f"@图片2（{sc['A']['name']}）参考开场环境；@图片3（{sc['B']['name']}）参考中段空间与载具；"
        f"@图片4（{sc['C']['name']}）参考结尾水面与天空。三张环境图均无人物，"
        f"不要复制人物资产图的白底、拼板排版或重复人像。前后同一载具、同一套道具。"
    )
    style = (
        f"【风格】{_short(spec['style_block'], 190)}"
        f"极致唯美：夕照在发梢与纱袖边缘形成细碎柔光，微风轻动衣袖碎发，水面碎金涟漪，"
        f"空气感清润，含蓄留余韵。人物为正常人眼、不发光，情绪用微表情表达。"
        f"服装{pal['garment']}，环境{pal['environment']}，光色{pal['light']}。"
    )
    cont = f"【一致性】{_short(spec['continuity'], 110)}不整体染成浓重橙黄。"

    scene_img = {"A": "@图片2", "B": "@图片3", "C": "@图片4"}
    lines = [f"【{len(shots)}镜｜共{duration}秒｜一镜一个主要动作｜自然直接切换，不用溶解或幻灯片转场】"]
    for sh in shots:
        one = (
            f"镜头{sh['n']} {sh['size']}（约{sh['seconds']}s，参考{scene_img[sh['ref_scene']]}）："
            f"{_seg(sh['start'], 60)}；{_seg(sh['action'], 110)}；{_seg(sh['camera'], 32)}。"
        )
        lines.append(one)

    closing = (
        f"【声音与避免】只保留{_short(spec['sound_bed'], 40)}；"
        f"无对白、无旁白、无背景音乐、无字幕、无文字与水印。"
        f"避免换脸换衣、手部变形穿模、道具跳变、木桨自行划动、鸟体变形、"
        f"突然增加人物或鸟群、浓重橙黄滤镜、高饱和塑料感、宫殿仙侠与现代设施、花哨转场。"
        f"画面稳定无突变，4K 细节，{duration}s，{spec['resolution']}。"
    )
    text = "\n".join([head, binding, style, cont] + lines + [closing])

    # 兜底：仍有超长则逐步收紧每镜动作描述
    if len(text) > 1950:
        lines2 = []
        for sh in shots:
            lines2.append(
                f"镜头{sh['n']} {sh['size']}（约{sh['seconds']}s，参考{scene_img[sh['ref_scene']]}）："
                f"{_seg(sh['start'], 40)}；{_seg(sh['action'], 70)}；{_seg(sh['camera'], 18)}。"
            )
        text = "\n".join([head, binding, style, cont] + lines2 + [closing])
    return text[:1950]


def render_storyboard(spec: dict) -> str:
    t = 0.0
    rows = []
    for sh in spec["shots"]:
        s, e = t, t + sh["seconds"]
        t = e
        rows.append(
            f"| {sh['n']} | {s:.0f}–{e:.0f}s / {sh['seconds']}s | {sh['name']} | {sh['size']} | "
            f"{sh['start']} | {sh['action']} | {sh['camera']} | {sh['end']} | {sh['link']} | "
            f"{sh['line'] or '—'} | {sh['risk'] or '—'} |"
        )
    table = (
        "| 镜号 | 时间 | 镜名 | 景别 | 静帧起始状态 | 主体动作 | 摄影机运动 | 结束状态 | 与下一镜衔接 | 对应诗句 | 风险点 |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(rows)
    )
    adaptations = "\n".join(f"- {a}" for a in spec["adaptations"]) or "- 无新增改编"
    poem = "\n".join(spec["poem_lines"])
    return f"""# {spec['title']} · 分镜表

- **原作**：{spec['dynasty']}·{spec['author']}｜{spec['genre']}
- **风格预设**：`{spec['preset']}`（{spec.get('_preset_cn','')}）
- **规格**：{spec['duration']}s / {spec['aspect_ratio']} / {spec['resolution']} / 写实电影质感
- **时间地点**：{spec['time']}，{spec['season']}，{spec['place']}

## 原文

{poem}

## 故事梗概

{spec['story']}

**情绪弧线**：{spec['mood_arc']}

**改编边界**（原文意象之外新增的内容）：
{adaptations}

## 分镜（时长为设计值，可按实测调整）

{table}

## 最容易生成失败的镜头

""" + "\n".join(
        f"- **镜头{sh['n']}·{sh['name']}**：{sh['risk']}" for sh in spec["shots"] if sh.get("risk")
    ) + f"""

## 一致性声明

{spec['continuity']}

> 生成期无对白、无旁白、无配乐、无字幕；原词朗读、字幕与氛围音乐在后期合成阶段加入。
"""


def srt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_timeline(spec: dict) -> list:
    t = 0.0
    out = []
    for sh in spec["shots"]:
        s, e = t, t + sh["seconds"]
        t = e
        out.append({
            "n": sh["n"],
            "start": round(s, 2),
            "end": round(e, 2),
            "seconds": sh["seconds"],
            "name": sh["name"],
            "subtitle": sh.get("subtitle", ""),
            "line": sh.get("line", ""),
        })
    return out


def render_srt(timeline: list) -> str:
    chunks, i = [], 1
    for item in timeline:
        text = (item["subtitle"] or "").strip()
        if not text:
            continue
        s = min(item["start"] + 0.35, item["end"] - 0.4)
        e = item["end"] - 0.25
        if e <= s:
            s, e = item["start"], item["end"]
        chunks.append(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{text}\n")
        i += 1
    return "\n".join(chunks)


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


# --------------------------------------------------------------------------- #
PRESET_CN = {
    "songyin_wanyue": "宋韵江南婉约",
    "shanshui_tianyuan": "山水田园清旷",
    "jiye_jilv": "羁旅夜泊清冷",
    "hanjiang_guji": "寒江极简孤绝",
    "yueye_xiangsi": "月夜怀人温柔",
    "haofang_jianghe": "豪放江河苍茫",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="spec.json 路径")
    ap.add_argument("--out", default=None, help="项目输出目录，默认 spec.json 所在目录")
    ap.add_argument("--force", action="store_true", help="spec 校验有错误时仍继续（不推荐）")
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["_preset_cn"] = PRESET_CN.get(spec["preset"], "东方古典")

    errors, warnings = validate(spec)
    for w in warnings:
        print(f"[WARN] {w}")
    if errors and not args.force:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        print("spec 校验失败；请先修正，或用 --force 强制生成。", file=sys.stderr)
        return 1

    root = Path(args.out).resolve() if args.out else spec_path.parent
    (root / "prompts").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(parents=True, exist_ok=True)
    (root / "video").mkdir(parents=True, exist_ok=True)
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)

    # 1. 生图提示词
    char_prompt = render_character(spec)
    char_file = "prompts/01_主角三视图.txt"
    (root / char_file).write_text(char_prompt, encoding="utf-8")

    scene_files = {}
    for sc in spec["scenes"]:
        # 场景 A/B/C -> 02 / 03 / 04
        fn = f"prompts/{2 + 'ABC'.index(sc['key']):02d}_场景{sc['key']}_{safe(sc['name'])}.txt"
        (root / fn).write_text(render_scene(spec, sc), encoding="utf-8")
        scene_files[sc["key"]] = fn

    # 2. 视频提示词（主 + 两段降级）
    main_video = render_video(spec, spec["shots"], spec["duration"])
    main_video_file = "prompts/05_Seedance2.5_视频提示词_30s.txt"
    (root / main_video_file).write_text(main_video, encoding="utf-8")

    seg_a = render_video(
        spec, spec["shots"][:3], 15,
        segment="本段为整片上半段（镜头一至三），结尾不停顿收束，保持动作与方向可继续。",
    )
    seg_b = render_video(
        spec, spec["shots"][3:], 15,
        segment="本段为整片下半段（镜头四至六），开头直接承接上一段的视线与行进方向，不重演开场。",
    )
    (root / "prompts/06_降级_分段A_15s.txt").write_text(seg_a, encoding="utf-8")
    (root / "prompts/07_降级_分段B_15s.txt").write_text(seg_b, encoding="utf-8")

    # 2b. 内置视频生成后端专用精简版（prompt <= 2000 字符，如 minimax-video-h3）
    compact = render_video_compact(spec, spec["shots"], spec["duration"])
    compact_a = render_video_compact(
        spec, spec["shots"][:3], 15, "本段为上半段，结尾不停顿收束。")
    compact_b = render_video_compact(
        spec, spec["shots"][3:], 15, "本段为下半段，开头承接上一段的视线与行进方向。")
    (root / "prompts/08_内置后端_精简_30s.txt").write_text(compact, encoding="utf-8")
    (root / "prompts/09_内置后端_精简_分段A_15s.txt").write_text(compact_a, encoding="utf-8")
    (root / "prompts/10_内置后端_精简_分段B_15s.txt").write_text(compact_b, encoding="utf-8")
    compact_len = len(compact)

    # 3. 分镜表 / 字幕 / 时间轴 / 朗读稿
    timeline = build_timeline(spec)
    (root / "分镜表.md").write_text(render_storyboard(spec), encoding="utf-8")
    (root / "captions.srt").write_text(render_srt(timeline), encoding="utf-8")
    (root / "timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "朗读稿.txt").write_text("\n".join(spec["narration"]["lines"]), encoding="utf-8")

    # 4. manifest
    ref_images = [ASSET_FILES[k][0] for k in ("图片1", "图片2", "图片3", "图片4")]
    assets = []
    kinds = ["character", "scene_A", "scene_B", "scene_C"]
    prompt_files = [char_file] + [scene_files[k] for k in "ABC"]
    for i, (key, (f, _)) in enumerate(ASSET_FILES.items()):
        assets.append({
            "id": key,
            "kind": kinds[i],
            "file": f,
            "prompt_file": prompt_files[i],
            "size": "1536x1024" if i == 0 else "1536x1024",
            "quality": "high",
        })

    manifest = {
        "title": spec["title"],
        "author": spec["author"],
        "preset": spec["preset"],
        "duration": spec["duration"],
        "aspect_ratio": spec["aspect_ratio"],
        "resolution": spec["resolution"],
        "assets": assets,
        "image_gen": {
            "note": "依次用 ImageGen 生成 4 张；prompt 读取各 prompt_file；size=1536x1024, quality=high；按 file 字段重命名保存",
            "size": "1536x1024",
            "quality": "high",
        },
        "video": {
            "prompt_file": main_video_file,
            "reference_images": ref_images,
            "seconds": spec["duration"],
            "aspect_ratio": spec["aspect_ratio"],
            "resolution": spec["resolution"],
            "enable_audio": False,
            "output_dir": "video",
            "fallback": [
                {"prompt_file": "prompts/06_降级_分段A_15s.txt", "seconds": 15, "out": "video/part_A.mp4"},
                {"prompt_file": "prompts/07_降级_分段B_15s.txt", "seconds": 15, "out": "video/part_B.mp4"},
            ],
        },
        "builtin_video": {
            "note": "平台内置 VideoGen 后端（如 minimax-video-h3）prompt 上限 2000 字符，必须用精简版提示词；完整版只用于方舟/即梦",
            "max_prompt_chars": 2000,
            "prompt_file": "prompts/08_内置后端_精简_30s.txt",
            "prompt_chars": compact_len,
            "fallback": [
                {"prompt_file": "prompts/09_内置后端_精简_分段A_15s.txt", "seconds": 15},
                {"prompt_file": "prompts/10_内置后端_精简_分段B_15s.txt", "seconds": 15},
            ],
        },
        "ark": {
            "model": "doubao-seedance-2-5-260628",
            "endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            "content_roles": ["text"] + ["reference_image"] * 4,
            "ratio": spec["aspect_ratio"],
            "duration": spec["duration"],
            "resolution": spec["resolution"],
            "generate_audio": False,
            "omni_reference_task_type": "reference",
            "watermark": False,
        },
        "post": {
            "voice": spec["narration"]["voice"],
            "rate": spec["narration"].get("rate", "-10%"),
            "srt": "captions.srt",
            "timeline": "timeline.json",
            "bgm": True,
            "final_copy": f"成片_{safe(spec['title'])}.mp4",
        },
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 已生成到 {root}")
    print(f"  · 4 条生图提示词 + 1 条 30s 视频提示词 + 2 条 15s 降级提示词")
    print(f"  · 分镜表.md / captions.srt / timeline.json / 朗读稿.txt / manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
