# Seedance 2.5 提示词规范与 API 速查

> 来源：火山方舟官方《Doubao Seedance 2.5 提示词指南》《Seedance 2.5 教程》《创建视频生成任务 API》+ 原文实测经验。2026-11 核对。

---

## 1. 模型与能力边界

| 项 | 值 |
|---|---|
| 模型 ID | `doubao-seedance-2-5-260628` |
| 创建任务 | `POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks` |
| 查询任务 | `GET .../tasks/{task_id}`，成功后视频在 `content.video_url`（**仅保存 24 小时**） |
| 鉴权 | `Authorization: Bearer $ARK_API_KEY` |
| 输出时长 | `4~30` 秒整数，或 `-1` 自动；支持 30 秒连贯直出 |
| 分辨率 | `480p` / `720p` / `1080p`（1080p 为 10bit + H.265/HEVC） |
| 宽高比 | `16:9` 等，或 `adaptive`（跟随输入图）；自由比例范围 0.4–2.5 |
| 参考素材上限 | 30 图 + 10 视频 + 10 音频，合计 50 |
| 主体建议 | 1–5 个主体最稳；本流水线固定 **1 个主角**（三视图算同一主体） |
| 音频 | `generate_audio` 布尔；本流水线设 `false`（声音全部后期做） |

**开通条件**：火山方舟账户余额 > 200 元 / 购买节省计划 / 已购资源包。没有 key 或没开通时，本技能自动回退到 WorkBuddy 内置视频生成。

---

## 2. 任务类型与参数（全模态参考生视频）

`omni_reference_task_type`：`reference`（全新生视频，本技能用这个）/ `edit` / `extend` / `auto`。

推荐配置（本技能默认）：

```json
{
  "model": "doubao-seedance-2-5-260628",
  "content": [
    {"type": "text", "text": "<视频提示词>"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}, "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}, "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}, "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}, "role": "reference_image"}
  ],
  "ratio": "16:9",
  "duration": 30,
  "resolution": "1080p",
  "generate_audio": false,
  "omni_reference_task_type": "reference",
  "watermark": false
}
```

- 本地图片转 `data:image/png;base64,<...>`，`image/png` 必须小写。
- 也可用公网 URL，但本地文件走 base64 最稳。
- `role` 说明：`reference_image` = 参考图；`first_frame` / `last_frame` = 严格首/尾帧（会锁定宽高比）。**首尾帧模式与参考图模式互斥**，不要混用。
- 指定 `reference` 时不要同时传 `first_frame`，否则任务类型判定冲突会异步报错。

---

## 3. 提示词结构（官方「导演思维结构化 Prompt」）

```
① 素材绑定：一句话说明每张图/视频/音频「编号 + 用途」
② 一句话概述：主体 + 地点 + 事件 + 题材/风格 + 特殊运镜
③ 具体情节：按「镜头 N」或时间戳逐段写画面、动作、运镜、音效，尽量正向描述
④ 结尾：贯穿全片的机位、环境、声音、氛围 + 负向控制 + 画质尾句
```

### 3.1 素材指代（最容易翻车）

- 编号**按 content 中出现的顺序**，图片从 1 开始：`@图片1` / `@Image1`。
- **每个 `@图片N` 后面必须紧跟名词或括注**，不要把动词直接接在编号后面。
  - ✅ `@图片1 中的女子为全片唯一主角` / `@图片2（溪亭环境）用于参考…`
  - ❌ `@图片2 位于画面左侧`（数字+方位易被误切分）
- 不要只在图片里写标注文字来建立映射，必须在 prompt 文本里逐张绑定。
- 多角色时**按首次出场顺序**上传素材并同步编号，否则角色会串位。本技能固定单主角，规避此坑。

### 3.2 时间戳 vs 镜头号

- 时间戳以 1 秒为单位，支持 `0-3 秒…3-7 秒…`、`[1s-4s]…`、`第 5s…`；**时间轴必须连续，不能跳段**（不要写 `0-3s…5-6s…` 留下空档）。
- 不能用时间戳控制频率（「一秒摇头 3 次」无效）。
- 本技能**优先用「镜头一…镜头六」+ 每镜预计时长**，不强制等长；只在需要严格卡点时补时间戳。

### 3.3 关键帧参考（可选升级）

若要把 6 张分镜图作为严格关键帧，prompt 第一句必须写「**以图片 3 至图片 8 的顺序作为关键帧**」。本技能默认只传 4 张（1 人 + 3 场景），走「参考图」模式，不锁画面，给模型留出运镜空间——这也是原文实测跑通的做法。

---

## 4. 官方已知问题与对策

| 现象 | 对策 |
|---|---|
| 情绪过度响应 → 瞳孔发蓝/红光 | 提示词最高优先级写「人物为正常人眼、不发光」，环境光只作用于面部轮廓；把「狂喜/极度震惊」改成「惊叹/微微一怔」 |
| 字幕约束不生效 | 「不要字幕」仍可能出字幕；避免在台词后复述词语并追加语气描述。本技能生成期**完全不写台词**，从根上规避 |
| 画面中文字拼错 | 本技能全片不出现文字，规避 |
| 角色对应错误 | 按首次出场顺序绑定编号；单主角 |
| 2.0 与 2.5 风格差异大 | 不要混用两个模型的片段；本技能一次直出 30s，不混 |
| 抽卡不稳定 | 生图生视频都要抽卡；本技能对失败做自动重试与降级，不伪装成功 |

---

## 5. 与原文案例的对应关系

原文成功提示词的结构完全符合官方规范：

```
【参考素材】@图片1 主角 / @图片2 溪亭 / @图片3 荷塘  → ① 素材绑定
【整体风格】写实古装电影质感…                      → ② 概述 + 风格
【镜头一】…【镜头六】…                             → ③ 情节分段
【镜头与声音】…避免…无对白…30s，1080p              → ④ 结尾 + 负向 + 规格
```

本技能 `build_prompts.py` 生成的提示词严格复刻这个结构，并额外注入：
- 官方「正常人眼不发光」硬约束
- 原文踩坑 #2 的道具静止声明
- 原文踩坑 #3 的「不复制白底拼板」声明
- 风格圣经的 `style_block` / `beauty_block` / `negative_global`

---

## 6. WorkBuddy 内置视频生成（无 key 时的回退）

`VideoGen` 工具参数映射：

| Seedance 概念 | VideoGen 参数 |
|---|---|
| 4 张参考图 | `reference_images: [4 个本地绝对路径]` |
| 文本提示词 | `prompt` |
| `duration: 30` | `seconds: 30` |
| `ratio: "16:9"` | `aspect_ratio: "16:9"` |
| `resolution: "1080p"` | `resolution: "1080p"` |
| `generate_audio: false` | `enable_audio: false` |
| 输出目录 | `output_dir: <项目目录>/video` |

⚠️ `VideoGen` **没有 model 参数**，具体模型由平台决定，不能保证是 Seedance 2.5。生成的提示词本身仍是完整合规的 Seedance 2.5 提示词，可直接复制到即梦/方舟控制台使用。若必须严格用 Seedance 2.5 出片，配置 `ARK_API_KEY` 走 `seedance25_api.py`。

### 内置后端实测限制（2026-11-08 跑《如梦令》验证）

`VideoGen` 当前落到 `minimax-video-h3`，与 Seedance 2.5 **不是同一个模型**，参数差异很大：

| 参数 | 实测行为 |
|---|---|
| `prompt` | 上限 **2000 字符**，超出直接报 `prompt must not exceed 2000 characters` |
| `seconds` | **4–15**，传 30 报 `seconds must be between 4 and 15` |
| `resolution` | 仅 `768P`、`2K`；传 `1080p` 报 `not supported`；**2K+15s 实测 600s 超时且未落盘**，`768P` 稳定 |
| `enable_audio` | 模型强制生成音频，传 `false` 报 `always generates audio and cannot disable it` → **省略该参数** |
| `reference_images` | 4 张可用；工具返回 `mode: image-to-video`，但实测没有把三视图白底拼板搬进画面 |
| 产物 | 1344×768 / H.264+AAC / 15.08s / 左上角带平台角标 |

**正确调用**（两段，共用同一套 4 张参考图）：
`prompt=prompts/09、10 精简版` + `seconds=15` + `resolution="768P"` + `aspect_ratio="16:9"` + 4 张参考图，不传 `enable_audio`。
后期用 `finalize.py --delogo "6,6,120,48"` 去角标，并自动把两段拼成 30 秒。

**降级链**：方舟 30s 一次直出 → 失败则 2×15s（`06`/`07` 完整版）→ 内置后端 2×15s（`09`/`10` 精简版）→ 内置后端减参考图到 2 张 → ffmpeg 拼接。
