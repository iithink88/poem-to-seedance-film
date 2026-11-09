#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后期全自动合成：原词朗读(edge-tts) + 逐镜字幕烧录 + 程序化古风氛围音乐 + 拼接 -> 成片 MP4

用法:
    python finalize.py --project <项目目录>
    python finalize.py --project <项目目录> --no-bgm --no-tts
    python finalize.py --project <项目目录> --voice zh-CN-YunjianNeural

输入:  video/raw.mp4|raw.mov  或  video/part_A.mp4 + part_B.mp4（自动拼接）
输出:  output/final.mp4 + 成片_<诗名>.mp4 + 字幕.srt + post_report.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100


# --------------------------------------------------------------------------- #
def log(m: str) -> None:
    print(f"[finalize] {m}", flush=True)


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, **kw)


def ffprobe_duration(path: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    try:
        return float(r.stdout.decode().strip())
    except Exception:
        return 0.0


def decode_audio(path: Path) -> np.ndarray:
    r = run(["ffmpeg", "-v", "error", "-i", str(path),
             "-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(SR), "-ac", "1", "pipe:1"])
    if r.returncode != 0:
        raise RuntimeError(f"解码音频失败: {r.stderr.decode('utf-8', 'replace')[:400]}")
    return np.frombuffer(r.stdout, dtype=np.int16).copy()


def write_wav(path: Path, arr: np.ndarray) -> None:
    arr = np.asarray(arr, dtype=np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(arr.tobytes())


def fit_to(arr: np.ndarray, n: int) -> np.ndarray:
    """把 PCM 段压/放缩到恰好 n 个采样（小幅变速，用于卡进镜头）。"""
    if len(arr) == 0:
        return np.zeros(n, dtype=np.int16)
    if len(arr) == n:
        return arr.astype(np.int16)
    if len(arr) < n:
        out = np.zeros(n, dtype=np.int16)
        out[:len(arr)] = arr
        return out
    idx = np.linspace(0, len(arr) - 1, n)
    return np.interp(idx, np.arange(len(arr)), arr.astype(np.float64)).astype(np.int16)


# --------------------------------------------------------------------------- #
def make_bgm(duration: float, preset: str, seed: int = 7) -> np.ndarray:
    """程序化生成无版权古风氛围垫音：五声音阶拨弦 + 低频持续音 + 极轻风声。"""
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n, dtype=np.float64) / SR
    out = np.zeros(n, dtype=np.float64)

    # 低频持续音（按预设移调，冷色调用更低更稀）
    base = 110.0 if preset in ("jiye_jilv", "hanjiang_guji") else 130.81
    out += 0.018 * np.sin(2 * np.pi * base * t)
    out += 0.010 * np.sin(2 * np.pi * base * 1.5 * t + 0.6)

    # 极轻风声：先在低采样率上做一阶低通，再插值回 44.1k，避免逐样本 Python 循环
    factor = 64
    m = max(2, n // factor + 2)
    noise = rng.standard_normal(m)
    lp = np.zeros(m)
    acc = 0.0
    for i, v in enumerate(noise):
        acc += 0.06 * (v - acc)
        lp[i] = acc
    wind = np.interp(np.linspace(0, m - 1, n), np.arange(m), lp)
    wind *= (0.55 + 0.45 * np.sin(2 * np.pi * 0.07 * t))
    wind /= (np.max(np.abs(wind)) + 1e-9)
    out += 0.012 * wind

    # 五声音阶拨弦（C D E G A），每个音 1.6~2.4s 衰减
    scale = [261.63, 293.66, 329.63, 392.00, 440.00, 523.25]
    if preset in ("jiye_jilv", "hanjiang_guji"):
        scale = [196.00, 220.00, 261.63, 293.66, 329.63, 392.00]
    step = 3.1 if preset not in ("haofang_jianghe",) else 2.4
    pos = 0.8
    while pos < duration - 0.5:
        f = scale[int(rng.integers(0, len(scale)))]
        length = min(2.2, duration - pos)
        k = int(length * SR)
        tt = np.arange(k) / SR
        env = np.exp(-3.0 * tt) * (1 - np.exp(-60 * tt))
        tone = (np.sin(2 * np.pi * f * tt)
                + 0.35 * np.sin(2 * np.pi * 2 * f * tt)
                + 0.12 * np.sin(2 * np.pi * 3 * f * tt)) * env
        s = int(pos * SR)
        amp = 0.055 if preset not in ("hanjiang_guji",) else 0.035
        out[s:s + k] += amp * tone
        pos += step + float(rng.uniform(-0.4, 0.5))

    # 首尾淡入淡出
    fade = int(min(1.5, duration / 4) * SR)
    if fade > 0:
        env = np.ones(n)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        out *= env

    peak = np.max(np.abs(out)) + 1e-9
    return (out / peak * 0.55 * 32767).astype(np.int16)


# --------------------------------------------------------------------------- #
async def tts_one(text: str, voice: str, rate: str, dest: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(dest))


def build_narration(root: Path, timeline: list, voice: str, rate: str,
                    total_samples: int) -> tuple[np.ndarray, int]:
    """逐镜朗读：把每个有字幕的镜头对应诗句用 edge-tts 合成，放到该镜起始处。"""
    track = np.zeros(total_samples, dtype=np.int16)
    tmp = Path(tempfile.mkdtemp(prefix="poemfilm_tts_"))
    made = 0
    try:
        for item in timeline:
            text = (item.get("subtitle") or "").strip().rstrip("，。！？、；：,.!?")
            if not text:
                continue
            mp3 = tmp / f"line_{item['n']:02d}.mp3"
            try:
                asyncio.run(tts_one(text, voice, rate, mp3))
                pcm = decode_audio(mp3)
            except Exception as e:
                log(f"镜头{item['n']} 朗读失败，跳过该句: {e}")
                continue
            start = int((item["start"] + 0.30) * SR)
            room = int((item["seconds"] - 0.55) * SR)
            if room < SR // 2:
                room = SR // 2
            pcm = fit_to(pcm, min(len(pcm), room))
            end = min(start + len(pcm), total_samples)
            if end > start:
                # 轻微淡入淡出，避免爆音
                seg = pcm[:end - start].astype(np.float64)
                f = min(600, len(seg) // 8)
                if f > 0:
                    seg[:f] *= np.linspace(0, 1, f)
                    seg[-f:] *= np.linspace(1, 0, f)
                track[start:end] = seg.astype(np.int16)
                made += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return track, made


# --------------------------------------------------------------------------- #
def concat_parts(root: Path) -> Path | None:
    parts = sorted((root / "video").glob("part_*.mp4"))
    if len(parts) < 2:
        return None
    lst = root / "video" / "concat.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
    dest = root / "video" / "raw.mp4"
    r = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-c", "copy", str(dest)])
    if r.returncode != 0 or not dest.is_file():
        log("无损拼接失败，改用重编码拼接")
        r = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lst), "-c:v", "libx264", "-crf", "18", "-c:a", "aac", str(dest)])
    if r.returncode != 0:
        log("拼接失败：" + r.stderr.decode("utf-8", "replace")[:500])
        return None
    log(f"已拼接 {len(parts)} 段 -> {dest.name}")
    return dest


def esc_filter_path(p: Path) -> str:
    s = p.as_posix()
    return s.replace(":", "\\:").replace("'", "\\'")


def detect_fonts_dir() -> str:
    """自动探测字体目录，返回已为 ffmpeg 滤镜转义的路径；找不到则返回空串。"""
    if os.name == "nt":
        return "C\\:/Windows/Fonts"
    for d in ("/System/Library/Fonts", "/usr/share/fonts",
              "/usr/local/share/fonts", str(Path.home() / ".fonts")):
        if Path(d).is_dir():
            return d.replace(":", "\\:")
    return ""


def burn(root: Path, video: Path, mix_wav: Path, srt: Path, out: Path,
         duration: float, delogo: str = "", font_name: str = "Microsoft YaHei") -> tuple[bool, str]:
    """烧字幕并混音；字幕失败时自动降级为无字幕成片。"""
    # 用纯 ASCII 临时路径，规避 libass 在中文路径下打不开字体/字幕的问题
    tmpdir = Path(tempfile.mkdtemp(prefix="poemfilm_srt_"))
    tmp_srt = tmpdir / "captions.srt"
    shutil.copyfile(srt, tmp_srt)
    fonts = detect_fonts_dir()
    fonts_part = f":fontsdir='{fonts}'" if fonts else ""
    sub_filter = (
        f"subtitles=filename='{esc_filter_path(tmp_srt)}'{fonts_part}:"
        f"force_style='FontName={font_name},FontSize=26,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BorderStyle=1,Outline=1.4,Shadow=0.8,"
        f"Alignment=2,MarginV=54'"
    )
    common = ["-y", "-v", "error", "-i", str(video), "-i", str(mix_wav),
              "-map", "0:v:0", "-map", "1:a:0",
              "-c:v", "libx264", "-preset", "medium", "-crf", "18",
              "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"]

    vf = (delogo + "," if delogo else "") + sub_filter
    r = run(["ffmpeg"] + common + ["-vf", vf, str(out)])
    if r.returncode == 0 and out.is_file() and out.stat().st_size > 10000:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return True, "字幕烧录成功" + ("（已去除角标）" if delogo else "")
    reason = r.stderr.decode("utf-8", "replace")[:400]
    log(f"字幕烧录失败，降级为无字幕成片。原因: {reason}")
    r2 = run(["ffmpeg"] + common + (["-vf", delogo] if delogo else []) + [str(out)])
    shutil.rmtree(tmpdir, ignore_errors=True)
    if r2.returncode != 0:
        return False, r2.stderr.decode("utf-8", "replace")[:400]
    return False, f"字幕未烧录（已保留独立 srt）；原因: {reason}"


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--voice", default=None, help="覆盖朗读音色")
    ap.add_argument("--rate", default=None, help="覆盖语速，如 -10%")
    ap.add_argument("--no-tts", action="store_true")
    ap.add_argument("--no-bgm", action="store_true")
    ap.add_argument("--no-subtitle", action="store_true")
    ap.add_argument("--bgm-gain", type=float, default=0.22)
    ap.add_argument("--delogo", default=None,
                    help="去除平台角标，格式 x,y,w,h（如 4,4,170,64）；方舟直连无水印时可省略")
    ap.add_argument("--font-name", default="Microsoft YaHei",
                    help="字幕字体名；macOS 可填 PingFang SC，Linux 可填 Noto Sans CJK SC")
    args = ap.parse_args()

    delogo = ""
    if args.delogo:
        try:
            x, y, w, h = [int(v) for v in args.delogo.replace(",", ":").split(":")]
            delogo = f"delogo=x={x}:y={y}:w={w}:h={h}"
        except Exception:
            log(f"--delogo 参数格式错误：{args.delogo}，已忽略")
            delogo = ""

    root = Path(args.project).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    srt = root / manifest["post"]["srt"]
    voice = args.voice or manifest["post"]["voice"]
    rate = args.rate or manifest["post"].get("rate", "-10%")

    raws = sorted(list((root / "video").glob("raw.*")))
    video = raws[0] if raws else concat_parts(root)
    if not video or not video.is_file():
        log("找不到 video/raw.mp4|raw.mov，也没有 part_A/B 可拼接。请先完成视频生成。")
        return 3

    duration = ffprobe_duration(video)
    if duration <= 0:
        log("无法读取视频时长，ffprobe 失败")
        return 4
    log(f"源视频 {video.name}｜{duration:.2f}s")

    n = int(duration * SR)
    narration = np.zeros(n, dtype=np.int16)
    made = 0
    if not args.no_tts:
        narration, made = build_narration(root, timeline, voice, rate, n)
        write_wav(root / "audio" / "narration.wav", narration)
        log(f"朗读合成完成：{made} 句 / 音色 {voice} / 语速 {rate}")
    else:
        log("已跳过朗读（--no-tts）")

    if not args.no_bgm:
        bgm = make_bgm(duration, manifest["preset"])
        log("氛围音乐已生成（程序化五声音阶，无版权）")
    else:
        bgm = np.zeros(n, dtype=np.int16)

    mix = (narration.astype(np.float64) + bgm.astype(np.float64) * args.bgm_gain)
    mix = np.clip(mix, -32767, 32767).astype(np.int16)
    mix_wav = root / "audio" / "mix.wav"
    write_wav(mix_wav, mix)
    write_wav(root / "audio" / "bgm.wav", bgm)

    (root / "字幕.srt").write_text(srt.read_text(encoding="utf-8"), encoding="utf-8")

    out = root / "output" / "final.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.no_subtitle:
        extra = ["-vf", delogo] if delogo else []
        r = run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(mix_wav),
                 "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-crf", "18",
                 "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"]
                + extra + [str(out)])
        sub_ok, sub_msg = False, "用户指定不烧字幕" if r.returncode == 0 else "混音失败"
    else:
        sub_ok, sub_msg = burn(root, video, mix_wav, srt, out, duration, delogo,
                               args.font_name)

    if not out.is_file() or out.stat().st_size < 10000:
        log("成片生成失败：" + sub_msg)
        return 5

    final_name = manifest["post"].get("final_copy") or f"成片_{manifest['title']}.mp4"
    final_copy = root / final_name
    shutil.copyfile(out, final_copy)

    report = {
        "source_video": str(video.relative_to(root)),
        "duration": round(duration, 2),
        "narration_lines": made,
        "voice": voice,
        "rate": rate,
        "bgm": not args.no_bgm,
        "delogo": delogo or None,
        "subtitle_burned": sub_ok,
        "subtitle_note": sub_msg,
        "final": str(final_copy),
    }
    (root / "post_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"成片完成 -> {final_copy}（{final_copy.stat().st_size/1024/1024:.1f} MB）")
    log(sub_msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
