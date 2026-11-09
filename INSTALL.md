# 安装说明（给拿到这个压缩包的朋友）

这个技能让 WorkBuddy 在你输入一句「把《XXX》做成古诗词短片」后，自动完成分镜、主角三视图、场景定样图、视频提示词、视频生成、朗读字幕配乐与成片合成。

> 全程自动，不需要你会剪视频。但**会消耗积分**：约 4 张图（20–40 积分）+ 30 秒视频（300–600 积分）；若配置火山方舟则按方舟计费。

---

## 一、先确认环境

| 依赖 | 用途 | 怎么检查 |
|---|---|---|
| WorkBuddy | 运行技能、调用图像/视频生成 | 已安装即可 |
| Python 3.10+ | 跑 5 个脚本 | `python3 --version`（Windows 可用 WorkBuddy 托管 venv） |
| `numpy` / `pillow` / `edge-tts` | 氛围音乐合成、图片归位、原词朗读 | `python3 -c "import numpy,PIL,edge_tts"` |
| `ffmpeg` / `ffprobe` | 字幕烧录、混音、拼接 | `ffmpeg -version` |
| ffmpeg 带 `libass` | 中文字幕 | `ffmpeg -filters \| grep subtitles` 能看到 `subtitles` 即可 |
| 中文字体 | 字幕 | Windows 微软雅黑 / macOS 苹方 / Linux Noto Sans CJK |

装 Python 依赖（建议用虚拟环境，不要全局 pip）：

```bash
python3 -m venv .venv
.venv/Scripts/pip install numpy pillow edge-tts      # Windows
# .venv/bin/pip install numpy pillow edge-tts        # macOS / Linux
```

ffmpeg：Windows 可从 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 下载并加入 PATH；
macOS `brew install ffmpeg`；Linux `sudo apt install ffmpeg`。

---

## 二、安装技能（二选一）

### 方式 A · 一键脚本（推荐）

**Windows**：在解压后的文件夹里右键 `install.ps1` → 「使用 PowerShell 运行」；或在 PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

**macOS / Linux**：

```bash
bash install.sh
```

脚本会把整个技能复制到 `~/.workbuddy/skills/poem-to-seedance-film/`，并检查依赖是否齐全。**不会覆盖**已有同名目录（会先备份为 `.bak-时间戳`）。

### 方式 B · 手动复制

把本文件夹（含 `SKILL.md`、`scripts/`、`references/`、`examples/`）整个复制到：

```
Windows : %USERPROFILE%\.workbuddy\skills\poem-to-seedance-film\
macOS   : ~/.workbuddy/skills/poem-to-seedance-film/
Linux   : ~/.workbuddy/skills/poem-to-seedance-film/
```

> 注意：`SKILL.md` 必须在技能**根目录**，不要多套一层文件夹。

### 重启 / 刷新

安装后重启 WorkBuddy（或在技能管理里刷新），让它重新扫描技能目录。

---

## 三、验证安装

在 WorkBuddy 里说一句：

> 把《山居秋暝》做成古诗词短片，先只给提示词别生成视频

如果它输出了 `spec.json`、分镜表和 10 条提示词，说明安装成功。去掉后半句就会真正生成成片。

---

## 四、可选：接真·Seedance 2.5

默认走平台内置视频生成（零配置，但模型由平台决定、实测为 `minimax-video-h3`，单次最长 15 秒，技能会自动分两段再拼成 30 秒）。

要 30 秒一次连贯直出的**真 Seedance 2.5**，在终端临时设置环境变量后启动 WorkBuddy：

```powershell
$env:ARK_API_KEY="你的火山方舟 API Key"
```

```bash
export ARK_API_KEY="你的火山方舟 API Key"
```

前置条件：火山方舟账户已开通 Seedance 2.5（账户余额 > 200 元 / 购买节省计划 / 已购资源包）。

> ⚠️ **安全提醒**：API Key 只放在环境变量里，**不要写进任何文件、不要提交到 Git 仓库、不要发给别人**。本仓库所有文档里的 `ARK_API_KEY` 只是变量名，不含任何真实密钥。用完后建议在方舟控制台撤销并轮换。

---

## 五、常见问题

| 问题 | 处理 |
|---|---|
| 提示找不到脚本 / 路径错误 | 确认技能目录里直接就是 `SKILL.md`；`SKILL_DIR` 由安装位置决定，不要写死别人机器的用户名 |
| 字幕变方框或乱码 | 用 `--font-name "PingFang SC"`（macOS）或 `"Noto Sans CJK SC"`（Linux）；Windows 默认微软雅黑 |
| 提示 `subtitles` 滤镜不存在 | 换一个带 `libass` 的 ffmpeg 构建 |
| 视频生成报 600s 超时 | 内置后端把 `resolution` 降到 `768P`；`2K` + 15s 实测会超时 |
| 提示词超 2000 字报错 | 内置后端要用 `prompts/08|09|10_内置后端_精简_*.txt`，完整版是给方舟/即梦用的 |
| 成片左上角有角标 | 后期加 `--delogo "6,6,120,48"` |
| 朗读没声音 | `edge-tts` 需联网；无网络会自动跳过朗读，字幕与成片仍正常 |
| 生成结果不稳定 | 生图生视频本来就要抽卡，技能内置重试与降级；重跑一次即可 |

---

## 六、来源与许可

- 制作流程与原始提示词思路来自公众号 **「挖挖说AI」**《实测 Seedance 2.5 制作古诗词 AI 短片，有点浪漫！（附完整提示词）》，
  `references/golden-prompts.md` 中的原文内容版权归原作者所有，仅作学习交流引用。
- Seedance 2.5 规范整理自火山方舟官方文档。
- 本仓库脚本代码采用 MIT 许可，详见 `LICENSE`。
- 演示图片与成片由 AI 模型生成，仅供效果展示。
