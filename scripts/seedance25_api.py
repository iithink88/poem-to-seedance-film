#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火山方舟 Doubao Seedance 2.5 直连：4 张参考图 + 视频提示词 -> 30s 视频，轮询并下载到 video/raw.*

用法:
    set ARK_API_KEY=xxx            (Windows CMD)
    $env:ARK_API_KEY="xxx"         (PowerShell)
    python seedance25_api.py --project <项目目录>
    python seedance25_api.py --project <项目目录> --dry-run   # 只打印请求体摘要，不发送

前置: 火山方舟账户已开通 Seedance 2.5（余额 > 200 元 / 节省计划 / 资源包）。
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
MODEL = "doubao-seedance-2-5-260628"
TERMINAL_OK = {"succeeded"}
TERMINAL_BAD = {"failed", "cancelled", "canceled", "expired", "error", "rejected"}


def log(msg: str) -> None:
    print(f"[seedance2.5] {msg}", flush=True)


def http_json(method: str, url: str, api_key: str, payload=None, timeout=90):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def image_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    # 官方要求 data:image/png;base64,... 且 mime 小写
    mime = mime.lower()
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def deep_find(obj, keys):
    """在嵌套响应里找第一个非空字段。"""
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if v:
                return v
        for v in obj.values():
            found = deep_find(v, keys)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = deep_find(v, keys)
            if found:
                return found
    return None


def download(url: str, dest: Path, timeout=300) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="build_prompts.py 产出的项目目录")
    ap.add_argument("--duration", type=int, default=None, help="覆盖时长（4~30）")
    ap.add_argument("--resolution", default=None, help="覆盖分辨率 480p/720p/1080p")
    ap.add_argument("--poll", type=int, default=20, help="轮询间隔秒，默认 20")
    ap.add_argument("--max-wait", type=int, default=2400, help="最长等待秒，默认 2400")
    ap.add_argument("--dry-run", action="store_true", help="只打印请求体摘要")
    args = ap.parse_args()

    root = Path(args.project).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    ark = manifest["ark"]
    video = manifest["video"]

    prompt_path = root / video["prompt_file"]
    prompt = prompt_path.read_text(encoding="utf-8").strip()

    missing = [p for p in video["reference_images"] if not (root / p).is_file()]
    if missing:
        log("缺少参考图，请先完成资产生成：" + ", ".join(missing))
        return 3

    content = [{"type": "text", "text": prompt}]
    for rel in video["reference_images"]:
        data_url = image_to_data_url(root / rel)
        content.append({
            "type": "image_url",
            "image_url": {"url": data_url},
            "role": "reference_image",
        })

    payload = {
        "model": MODEL,
        "content": content,
        "ratio": ark.get("ratio", "16:9"),
        "duration": args.duration or ark.get("duration", 30),
        "resolution": args.resolution or ark.get("resolution", "1080p"),
        "generate_audio": bool(ark.get("generate_audio", False)),
        "omni_reference_task_type": ark.get("omni_reference_task_type", "reference"),
        "watermark": bool(ark.get("watermark", False)),
    }

    if args.dry_run:
        preview = {k: (v if k != "content" else
                       [{"type": "text", "text": f"<{len(prompt)} 字提示词>"}]
                       + [{"type": "image_url", "role": "reference_image",
                           "image_url": {"url": f"<data url #{i+1}, {len(c['image_url']['url'])} chars>"}}
                          for i, c in enumerate(content[1:])])
                   for k, v in payload.items()}
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("ARK_API_KEY", "").strip()
    if not api_key:
        log("未设置 ARK_API_KEY 环境变量。请设置后重试，或改用 WorkBuddy 内置视频生成回退方案。")
        return 4

    log(f"提交任务：{payload['duration']}s / {payload['ratio']} / {payload['resolution']} / "
        f"{len(content)-1} 张参考图 / 提示词 {len(prompt)} 字")
    try:
        created = http_json("POST", ENDPOINT, api_key, payload)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        log(f"创建任务失败 HTTP {e.code}: {body}")
        return 5
    except Exception as e:
        log(f"创建任务失败: {e}")
        return 5

    task_id = deep_find(created, ("id", "task_id", "taskId"))
    if not task_id:
        log(f"未解析到任务 ID：{json.dumps(created, ensure_ascii=False)[:800]}")
        return 5
    log(f"任务已提交 task_id={task_id}")

    start = time.time()
    status = ""
    result = {}
    while time.time() - start < args.max_wait:
        try:
            result = http_json("GET", f"{ENDPOINT}/{task_id}", api_key, timeout=60)
        except Exception as e:
            log(f"查询异常（将重试）: {e}")
            time.sleep(args.poll)
            continue
        status = str(deep_find(result, ("status", "state")) or "unknown").lower()
        elapsed = int(time.time() - start)
        log(f"[{elapsed}s] status={status}")
        if status in TERMINAL_OK:
            break
        if status in TERMINAL_BAD:
            log("任务失败：" + json.dumps(result, ensure_ascii=False)[:1200])
            return 6
        time.sleep(args.poll)
    else:
        log(f"等待超时（{args.max_wait}s），最后一次状态={status}。可稍后用 task_id 手动查询。")
        return 7

    video_url = deep_find(result, ("video_url", "url"))
    if not video_url or not str(video_url).startswith("http"):
        log("任务成功但未找到可下载的视频 URL：" + json.dumps(result, ensure_ascii=False)[:1200])
        return 6

    ext = ".mov" if ".mov" in str(video_url).lower() else ".mp4"
    dest = root / "video" / f"raw{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"下载视频 -> {dest}")
    try:
        download(video_url, dest)
    except Exception as e:
        log(f"下载失败（URL 仅保留 24 小时）: {e}")
        return 8

    size_mb = dest.stat().st_size / 1024 / 1024
    log(f"完成：{dest} ({size_mb:.1f} MB)。请尽快做后期，视频 URL 24 小时后失效。")
    (root / "video" / "source.json").write_text(
        json.dumps({"backend": "ark-seedance-2.5", "task_id": task_id,
                    "model": MODEL, "file": f"video/raw{ext}"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
