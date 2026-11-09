---
name: poem-to-seedance-film
description: 古诗词 AI 短片全自动流水线（Seedance 2.5 / 东方写实浪漫美学）。用户输入一个古诗名、一句诗或全诗，自动完成：原文校订与意象解析 → 六镜分镜表 → 主角三视图 + 3 张场景定样图提示词 → 自动生成 4 张参考资产 → 组装符合 Seedance 2.5 官方规范的 @图片N 多图参考 30 秒视频提示词 → 自动生成视频 → 自动配音、烧字幕、配氛围音乐、合成最终 MP4。触发词：古诗做成视频、诗词短片、古诗词 AI 短片、Seedance 古诗、三视图、把《XX》拍成短片、诗配画视频、浪漫古风短片。默认全程自动执行，不向用户提确认问题。
---

# 古诗词 → Seedance 2.5 短片 · 全自动流水线

> 目标：**用户只给一个诗名（或一句诗），中间不打断，直接交出成片 MP4。**
> 方法来自公众号《实测 Seedance 2.5 制作古诗词 AI 短片，有点浪漫！》的完整实测流程，并按火山方舟《Seedance 2.5 提示词指南》做了规范化与踩坑加固。

---

## 绝对纪律

1. **不提问、不停下等确认。** 所有选择（风格预设、人物、场景、镜头、音色）由你自动决定，在最终报告里说明即可。
2. **不伪装成功。** 任何一步失败都要走降级链；仍失败就如实报告已完成到哪一步、卡在哪、产物在哪，绝不编造视频。
3. **只创作一次。** 你唯一的创作工作是写 `spec.json`；之后所有提示词由脚本确定性渲染，**不要手写或临时改写提示词**，避免风格漂移。
4. **先告知消耗，再开工。** 首次调用生成类工具前，用一句话说明：本次约生成 4 张图（约 20–40 积分）与 30 秒视频（约 300–600 积分，按 5s 50–100 积分估算）；若走火山方舟则按方舟计费。**这是告知，不是询问，说完立刻继续。**
5. **中文输出**，所有交付文件用 UTF-8。

---

## 路径约定

```
SKILL_DIR = <本技能安装目录>       # 默认 ~/.workbuddy/skills/poem-to-seedance-film
PY        = <WorkBuddy 托管 Python> # 见 INSTALL.md「准备 Python 环境」；Linux/macOS 通常为 python3
PROJECT   = <当前工作区>/poem-films/<安全化的诗名>_<YYYYMMDD_HHMMSS>
```

- `SKILL_DIR`：技能根目录，安装时由用户放到 `~/.workbuddy/skills/` 下；**不要写死某个用户名**。
- `PY`：优先用 WorkBuddy 托管 venv 解释器（Windows 常见为
  `%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe`），
  找不到时退回 `python3` / `python`，只要装了 `numpy`、`pillow`、`edge-tts` 即可。
- 用 `date +%Y%m%d_%H%M%S` 取时间戳（不要自己算）。项目目录建好后，后续所有相对路径都相对 `PROJECT`。

---

## 流水线（按顺序执行，不要跳步）

### 阶段 0 · 开工告知

输出一句话，例如：
> 「开始全自动制作《XXX》：将生成 4 张参考图 + 30 秒视频（生图约 20–40 积分、视频约 300–600 积分；若配置了 ARK_API_KEY 则按火山方舟计费），全程不再打断。」

然后立刻进入阶段 1。

### 阶段 1 · 解析输入 → 写 `spec.json`

1. 建目录：`mkdir -p "<PROJECT>/prompts" "<PROJECT>/assets" ...`（`build_prompts.py` 也会建，可省略）。
2. **校订原文**：用户给诗名时查 `references/poem-library.md`；不在库里就凭知识写出，拿不准的字句用联网搜索核对，绝不编造。用户给的句子/全诗以用户版本为准（含异文，如「一滩鸥鹭」）。
3. **选预设**：读 `references/style-bible.md` §4，按情绪题材自动选一个 `preset`，不选 `songyin_wanyue` 以外的默认值也不询问。
4. **写 spec**：严格按 `references/spec-schema.md`，把结构化的创作内容写进 `<PROJECT>/spec.json`。可直接复制 `examples/如梦令_spec.json` 作为骨架再改。
   - `style_block` / `beauty_block` / `negative_global` 从 `style-bible.md` §1–§3 **逐字复制**，按预设微调光色。
   - `protagonist.outfit` 使用该预设的「服装一致性长句」。
   - `scenes` 恰好 3 个（A 开场 / B 行进 / C 结尾），B 必须写清运动方向，C 必须留天空。
   - `shots` 恰好 6 个，`seconds` 之和 = 30；一镜一个主动作；`link` 交代衔接；第 6 镜写「本镜不出现人物」。
   - `continuity` 把运动方向、道具静止、光色一致写成一句话（对应原文「船桨自己在划」的坑）。
   - `narration.lines` 与 `poem_lines` 一致。
5. **校验**：
   ```bash
   "$PY" "<SKILL_DIR>/scripts/validate_spec.py" "<PROJECT>/spec.json"
   ```
   有 `[FAIL]` 就自动修正 spec 再校验一次；最多两次，仍不过就在报告里说明并继续（不中断流水线）。

### 阶段 2 · 渲染全套提示词（纯脚本，不调用模型）

```bash
"$PY" "<SKILL_DIR>/scripts/build_prompts.py" "<PROJECT>/spec.json" --out "<PROJECT>"
```

产出（不要改写）：
`prompts/01_主角三视图.txt`、`prompts/02|03|04_场景*.txt`、`prompts/05_Seedance2.5_视频提示词_30s.txt`、`prompts/06|07_降级_分段A|B_15s.txt`（完整版，给方舟）、`prompts/08_内置后端_精简_30s.txt`、`prompts/09|10_内置后端_精简_分段A|B_15s.txt`（≤2000 字，给内置后端）、`分镜表.md`、`captions.srt`、`timeline.json`、`朗读稿.txt`、`manifest.json`。

> 场景图提示词已自动把风格块里的「发丝/纱袖/面部补光」等人物词替换成纯环境词，避免与「无人物」约束冲突把人画进环境定样图。

### 阶段 3 · 自动生成 4 张参考资产

读 `manifest.json` 的 `assets[].prompt_file`，**依次**用图像生成工具生成 4 张（可并行发起 4 个调用）：

| # | prompt | `output_dir` | `size` | `quality` |
|---|---|---|---|---|
| 1 | `prompts/01_主角三视图.txt` | `<PROJECT>/assets/gen_01` | `1536x1024` | `high` |
| 2 | `prompts/02_场景A_*.txt` | `<PROJECT>/assets/gen_02` | `1536x1024` | `high` |
| 3 | `prompts/03_场景B_*.txt` | `<PROJECT>/assets/gen_03` | `1536x1024` | `high` |
| 4 | `prompts/04_场景C_*.txt` | `<PROJECT>/assets/gen_04` | `1536x1024` | `high` |

> **`output_dir` 必须一图一目录**，`register_assets.py` 靠这个把图片归位。

归位：
```bash
"$PY" "<SKILL_DIR>/scripts/register_assets.py" --project "<PROJECT>"
```
得到 `assets/01_character.png` … `assets/04_scene_C.png`。

**失败处理**：某张图生成失败 → 把该条提示词删掉末尾「避免」长清单后重试 1 次；仍失败 → 用同目录其他图复制占位**不算通过**，必须如实报告并用「跳过该参考图」的方式继续（视频提示词里的 @图片N 编号要相应调整，此时直接改用文生视频并在报告注明质量风险）。

> 用户若已自备人物/场景图：跳过本阶段，改用
> `register_assets.py --project "<PROJECT>" --from "<用户图片目录>"`（按文件名顺序取前 4 张）。

### 阶段 4 · 自动生成视频

**先判断后端**：检查环境变量 `ARK_API_KEY` 是否设置（只判断是否存在，不要把值打印出来）。

#### 4A 有 `ARK_API_KEY` → 真·Seedance 2.5 直连（首选）

```bash
"$PY" "<SKILL_DIR>/scripts/seedance25_api.py" --project "<PROJECT>"
```
脚本会：4 图转 base64 → `POST /api/v3/contents/generations/tasks`（model `doubao-seedance-2-5-260628`，`role=reference_image`，`duration=30`，`ratio=16:9`，`resolution=1080p`，`generate_audio=false`，`omni_reference_task_type=reference`，`watermark=false`）→ 轮询 → 下载到 `video/raw.mp4|mov`。

失败（未开通 / 额度 / 参数校验）→ 如实记录原因，自动转 4B。

#### 4B 无 key 或 4A 失败 → 平台内置视频生成（零配置回退）

**实测（2026-11-08）内置后端为 `minimax-video-h3`，硬限制如下，必须遵守，不要按 Seedance 参数硬传：**

| 项 | 实测限制 |
|---|---|
| 模型 | `minimax-video-h3`（**不是** Seedance 2.5，无法指定） |
| prompt | **≤ 2000 字符**；完整版约 2870 字会直接报错 |
| seconds | **4–15**，30 秒不支持 |
| resolution | 仅 `768P` / `2K`；`1080p` 报错；**2K + 15s 实测 600s 超时**，用 `768P` |
| enable_audio | 模型**强制带音频**，`enable_audio=false` 会报错，**不要传这个参数** |
| 角标 | 生成视频左上角带平台角标，后期用 `--delogo` 去除 |
| 输出 | 1344×768 / H.264+AAC / 约 15.08s |

因此 4B **直接走 2×15s 降级**，且必须使用精简提示词：

```
prompt           = prompts/09_内置后端_精简_分段A_15s.txt  → 第 1 段
                   prompts/10_内置后端_精简_分段B_15s.txt  → 第 2 段
reference_images = ["<PROJECT>/assets/01_character.png", "...02_scene_A.png",
                    "...03_scene_B.png", "...04_scene_C.png"]   # 绝对路径，顺序不可变，两段都传同一套
seconds          = 15
aspect_ratio     = "16:9"
resolution       = "768P"
output_dir       = "<PROJECT>/video/partA" 和 "<PROJECT>/video/partB"   # 一图一目录，避免混淆
```

把两段分别复制/重命名为 `<PROJECT>/video/part_A.mp4`、`part_B.mp4`，后期脚本会自动拼接成 30 秒。
若只想出单段，用 `prompts/08_内置后端_精简_30s.txt` 但把 `seconds` 改为 15（提示词里的 30s 字样需同步改）。

> ⚠️ 完整版 `prompts/05_...30s.txt` 是给**方舟/即梦**用的 Seedance 2.5 提示词，不要喂给内置后端。
> 内置后端模型不可指定、不是 Seedance 2.5，且分段生成会带来一定一致性风险——这两点必须在最终报告里如实说明。

#### 4C 通用降级

- 30s 方舟失败 → 用 `prompts/06_降级_分段A_15s.txt` / `07_降级_分段B_15s.txt` 生成两段 15s（完整版提示词），后期拼接。
- 内置后端某段超时 → 先降 `resolution` 到 `768P`；仍失败则减参考图到 2 张（`图片1` + 该段主场景图），并同步调整提示词里的 `@图片N` 编号。
- **分段提示词已预生成，不要临时改写。**

### 阶段 5 · 后期全自动合成

```bash
# 内置后端（带平台角标）必须带 --delogo；方舟直连可省略
"$PY" "<SKILL_DIR>/scripts/finalize.py" --project "<PROJECT>" --delogo "6,6,120,48"
```

自动完成：
- `edge-tts` 逐镜朗读原词（音色/语速取 `manifest.post`），按 `timeline.json` 卡进每个镜头
- 程序化生成无版权古风氛围垫音（五声音阶拨弦 + 低频 + 风声，numpy）
- 烧录中文字幕（`Microsoft YaHei`，字幕路径自动落到 ASCII 临时目录，规避中文路径问题）
- 混音 + H.264 重编码 → `output/final.mp4`
- 复制为 `成片_<诗名>.mp4`，写 `post_report.json`

**降级**：字幕烧录失败 → 自动输出无字幕成片并保留 `字幕.srt`；TTS 失败 → 保留纯音乐/静音成片；ffmpeg 缺失 → 直接交付 `video/raw.mp4` + `字幕.srt` 并说明。都不要中断。

可选参数：`--no-tts` / `--no-bgm` / `--no-subtitle` / `--voice zh-CN-YunxiNeural` / `--bgm-gain 0.15` / `--delogo "x,y,w,h"`（去平台角标，内置后端建议 `6,6,120,48`）。

### 阶段 6 · 质检与交付

1. 用 ffmpeg 抽 3 帧做人工抽查（首 / 中 / 尾），有明显换脸、变形、字幕错乱时如实写进报告，不掩饰：
   ```bash
   ffmpeg -y -v error -ss 2 -i "<PROJECT>/output/final.mp4" -frames:v 1 "<PROJECT>/output/qc_01.png"
   ```
2. 用文件呈现工具打开：① `成片_<诗名>.mp4` ② `分镜表.md` ③ `prompts/05_Seedance2.5_视频提示词_30s.txt` ④ `字幕.srt`。
3. 最终报告用表格说明：

| 项 | 结果 |
|---|---|
| 输入 | 诗名/诗句 |
| 风格预设 | `xxx`（一句话说明为何选它） |
| 视频后端 | 方舟 Seedance 2.5 / 平台内置视频生成（注明模型不可指定）/ 2×15s 降级 |
| 成片 | 绝对路径、时长、大小 |
| 提示词包 | `prompts/` 目录，10 条（含 3 条内置后端精简版） |
| 参考资产 | 4 张，路径 |
| 后期 | 朗读音色、字幕是否烧录、BGM |
| 已知问题 | 抽卡瑕疵 / 后端限制 / 失败步骤（没有就写「无」） |

---

## 参考文件索引

| 文件 | 何时读 |
|---|---|
| `references/style-bible.md` | 写 spec 前必读：美学铁律、6 套预设、三视图/场景骨架、踩坑表、画质尾句 |
| `references/spec-schema.md` | 写 spec 时对照字段 |
| `references/poem-library.md` | 校订原文 |
| `references/golden-prompts.md` | 想核对原文提示词写法时 |
| `references/seedance25-spec.md` | 需要调 API 参数 / 排查任务报错时 |
| `examples/如梦令_spec.json` | 完整可跑的黄金 spec 骨架 |

## 脚本索引

| 脚本 | 作用 |
|---|---|
| `validate_spec.py` | 校验 spec（字段、6 镜、秒数合计、字幕、风格块） |
| `build_prompts.py` | spec → 7 条提示词 + 分镜表 + 字幕 + 时间轴 + manifest |
| `register_assets.py` | 4 张生成图归位为 `assets/01..04_*.png` |
| `seedance25_api.py` | 火山方舟 Seedance 2.5 直连（含 `--dry-run`） |
| `finalize.py` | 朗读 + 字幕 + BGM + 拼接 → 成片 |

---

## 只出提示词、不消耗积分的调试模式

用户说「只给提示词」「先看看方案」「别生成视频」时，只执行阶段 1–2，交付 `prompts/` 与 `分镜表.md`，并在报告里给出后续命令。也可加 `--dry-run` 预览方舟请求体：

```bash
"$PY" "<SKILL_DIR>/scripts/seedance25_api.py" --project "<PROJECT>" --dry-run
```

---

## 环境依赖

- Python 3.10+，装 `numpy` / `pillow` / `edge-tts`；优先用 WorkBuddy 托管 venv（见 `INSTALL.md`）
- `ffmpeg` / `ffprobe` 在 PATH 中，且带 `libass`（`ffmpeg -filters | grep subtitles` 可验证）
- 中文字体：Windows 用微软雅黑（`C:/Windows/Fonts/msyh.ttc`）；macOS/Linux 用系统自带中文字体，
  `finalize.py` 会自动探测字体目录，也可用 `--font-name` 指定
- 可选：`ARK_API_KEY` 环境变量 + 火山方舟已开通 Seedance 2.5
- 安装与依赖检查见仓库根目录 `INSTALL.md`
