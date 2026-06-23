# PPT Speech Writer 工作逻辑说明

本文件说明 `ppt-speech-writer` 这个 skill 的内部逻辑：它由哪些部分组成、数据如何流动、每个脚本做什么、写稿的规则是怎样的。目的是让任何人读完就能明白「输入一个 .pptx，最后怎么变成带演讲稿的 .pptx + 排练文档」。

---

## 1. 定位

| 项 | 内容 |
|---|---|
| 输入 | 一个真实的 `.pptx` 演示文稿 |
| 输出 | ① 注入了讲稿的 `.pptx` ② 完整排练文档（.docx / .md） ③ 视觉审阅包（JSON，可选 Markdown） |
| 核心主张 | 讲稿必须**接地于每一个可见的幻灯片元素**，不能凭文本框臆测 |

一句话：把"看 PPT 写讲稿"这件事，拆成**先把每页看清楚（证据采集）→ 再基于证据写稿 → 最后写回 PPT 备注**三大阶段。

---

## 2. 三条贯穿全程的设计原则

1. **Grounding Contract（证据接地）**
   一页只有在以下证据都检查过之后才算"读过"：结构化提取、整页渲染图、图片区域 OCR、可见元素清单、对图表/图示的视觉审阅。无法可靠判读的元素必须先问用户，绝不杜撰图表数值、坐标轴、标签或截图文字。

2. **Language Lock（语言锁定）**
   不从聊天语言推断输出语言。写任何文字前显式确认唯一输出语言（英 / 中 / 跟随 PPT / 指定），之后整份交付物保持一致，技术术语保留规范写法但句法跟随所选语言。

3. **输出紧凑**
   中间证据用 compact JSON、OCR 只在图片区域、最终在聊天里只给"摘要 + 文件路径"，不默认贴整份逐页讲稿。

---

## 3. 整体流水线（数据流）

```
                      deck.pptx
                          │
          ┌───────────────┴────────────────┐
          ▼                                 ▼
  read_slides.py --mode compact      render_slides.py
          │                                 │
          ▼                                 ▼
   slide_extract.json              rendered_slides/*.png
  (文本/表格/图表/图片/            (soffice 优先，qlmanage 兜底，
   原始OOXML/页面尺寸)              统一命名 slide-001.png …)
          │                                 │
          └───────────────┬─────────────────┘
                          ▼
              visual_inventory.py --ocr-scope image-regions
                          │   （结构化元素 + 渲染图 + 仅图片区域 OCR）
                          ▼
                 visual_inventory.json
                          │
                          ▼
              vision_review.py --format compact
                          │   （生成审阅包：顶层只放一次 prompt/schema）
                          ▼
              vision_review_packet.json
                          │
                  ⟨人工 / 视觉模型 逐页判读图表、图示、截图⟩
                          ▼
                  vision_review.json   ← 视觉证据落地
                          │
                          ▼
        ┌──── 写稿阶段（依据全部证据）──────────────┐
        │  · Deck 理解简报 / 叙事弧                  │
        │  · 每页两版：display 版 + clean 版          │
        │  · 术语表（glossary 开关）                  │
        └───────────────┬───────────────────────────┘
                 ┌───────┴────────┐
                 ▼                ▼
        display_document.json   notes.json
                 │                │
                 ▼                ▼
        write_display_docx.py   inject_notes.py --mode replace
                 │                │
                 ▼                ▼
        <stem>-display.docx   <stem>-with-notes.pptx
        （或 .md 兜底）        （讲稿写入备注面板）
```

关键点：**用户面向的成品在输出根目录，所有中间 JSON 和渲染图都放在 `work/` 子目录**。

---

## 4. 目录布局

```
<deck-stem>-speaker-output/
├── <deck-stem>-with-notes.pptx        # 成品①：带讲稿的 PPT
├── <deck-stem>-display.docx           # 成品②：完整排练文档
├── <deck-stem>-display.md             # 仅当没有 python-docx 时的兜底
├── <deck-stem>-vision-review.md       # 可选：需要可读审阅文档时才生成
└── work/                              # 中间证据，全部隐藏在这里
    ├── slide_extract.json
    ├── visual_inventory.json
    ├── vision_review_packet.json
    ├── vision_review.json
    ├── display_document.json
    ├── notes.json
    └── rendered_slides/
```

---

## 5. 各脚本逻辑（输入 → 处理 → 输出）

### 5.1 `read_slides.py` — 结构化提取
- **作用**：从 `.pptx` 直接读取结构化证据。
- **输入**：`deck.pptx`，`--mode {full,compact}`，`--output`。
- **处理**：
  - 用 `python-pptx` 遍历每页形状，提取文本框、占位符、表格（行列）、图表（标题/分类/系列/数值/坐标轴/图例）、图片与媒体元数据、已有备注。
  - 直接解析 OOXML，捞出 `python-pptx` 拿不到的文字（部分 SmartArt、组合形状）。
  - 记录每页尺寸 `slide_width_emu` / `slide_height_emu`（供后续区域 OCR 做 EMU→像素换算）。
- **compact 模式**：丢掉冗余的 `raw_ooxml_text` 全量转储（保留 `raw_ooxml_text_not_in_shapes`）、丢掉非图形形状的 `name`/`bbox`，但**保留图片的 bbox**（区域 OCR 要用），JSON 明显变小。
- **输出**：`slide_extract.json`。

### 5.2 `render_slides.py` — 整页渲染
- **作用**：把每页渲染成 PNG，作为"看图"证据。
- **处理**：优先 `soffice/libreoffice --convert-to png`；失败回退 macOS `qlmanage`；都失败则报告限制。最后把文件名统一规范成 `slide-001.png`、`slide-002.png`…
- **输出**：`work/rendered_slides/*.png`。

### 5.3 `visual_inventory.py` — 可见元素清单 + 区域 OCR
- **作用**：把结构化证据 + 渲染图 + OCR 合成"每页该讲什么"的清单。
- **输入**：`--extract`、`--rendered-dir`、`--output`、`--ocr {auto,off}`、`--ocr-scope {image-regions,full}`。
- **区域 OCR 逻辑（默认 `image-regions`）**：
  - 文本框/表格/图表文字已在 XML 里拿到，无需再 OCR。
  - 只把**图片/媒体**形状的 bbox（EMU）按页面尺寸换算成渲染图上的像素框，裁剪出来单独 OCR。
  - 结果按形状写进 `ocr_regions`，合并文本放 `ocr_text`，实际用的范围记在 `ocr_scope`。
  - 缺 Pillow、缺页面尺寸、或某页没有图片区域时，自动回退整页 OCR，并如实记录回退原因。
  - 健壮性：OCR 输出按字节安全解码（防非 UTF-8 崩溃）；图片路径先 `resolve()`（防 macOS `/tmp` 等软链接路径打不开）。
- **输出**：`visual_inventory.json`，每页含 `needs_direct_visual_inspection`（是否需要人眼/视觉模型复核）和 `coverage_checklist`（覆盖清单）。

### 5.4 `vision_review.py` — 视觉审阅包
- **作用**：为"需要看图判读"的页生成一个确定性的审阅模板，让视觉模型/人来填。脚本本身**不声称理解图像**。
- **输入**：`--inventory`、`--output`、`--format {compact,full}`、可选 `--markdown`。
- **compact 逻辑（默认）**：把审阅 prompt 和结果 schema **提到顶层只写一次**（`review_prompt` / `review_result_schema`），每页不再重复——这是体积优化的关键；每页只保留 `structured_evidence`、`ocr_text`、`ocr_regions`、`requires_vision_review`。
- **full 模式**：保留旧行为（每页内联 prompt 和模板），向后兼容。
- **下一步**：用视觉模型/浏览器截图/人工逐页填好审阅结果，落地成 `vision_review.json`。若无任何视觉手段，**停在这里并告知用户哪些页无法安全判读**。
- **输出**：`vision_review_packet.json`（+ 可选 Markdown）。

### 5.5 `write_display_docx.py` — 排练文档
- **作用**：把 `display_document.json` 渲染成一份完整的排练 Word 文档。
- **内容**：标题/路径、Deck 理解简报、叙事弧、逐页 display 讲稿、术语表（glossary 开时）、时间表、覆盖说明、注入日志。
- **降级**：没有 `python-docx` 时自动写成同名 `.md`。

### 5.6 `inject_notes.py` — 写回 PPT 备注
- **作用**：把"干净版"讲稿写进 `.pptx` 的备注面板。
- **输入**：`--input`（原 PPT）、`--output`、`--notes notes.json`、`--mode {replace,append,skip-if-present}`。
- **notes.json 形状**：`[{"slide": 1, "notes": "干净讲稿"}, …]`，校验页号、查重、对越界页号告警。
- **注入后**：把注入日志写回 `display_document.json` 并重跑 `write_display_docx.py`，保证排练文档完整。

---

## 6. 写稿逻辑

### 6.1 两个版本（同源）
- **display 版**（给用户看）：带 `[Slide X - Title]` 标签、`[PAUSE]`、`[EMPHASIS: 术语]`、以及一句"过渡到下一页"。
- **clean 版**（写进 PPT）：无标签、无分隔线、无停顿/强调标记、无过渡句——就是纯口语讲稿。

### 6.2 文风（Slide Prose Style）
- 每页**首句就是内容层面的论点/发现/方法作用**，不是"这一页展示了…"。
- 禁用一批描述幻灯片对象的开场白（中英文都有清单）。
- 句子尽量短（<20 词），避免"如我们所见""接下来"之类填充语。
- 图表说清表头/坐标轴/图例/具体数值；表格说清行列含义和关键对比；截图读出 UI/文档状态；图示讲清节点/箭头/流向；公式讲清变量与作用。

### 6.3 术语表开关（glossary）
信息收集阶段确认 `on/off`（默认 on）。`off` 时全流程跳过"Key Parameters And Methods"表，最终摘要也不提术语表。

---

## 7. 覆盖质检（注入前的关卡）

注入讲稿前逐项核对，违反就先修：

- 每页都有清单条目、都有渲染图（或记录了渲染失败）；
- 视觉复杂的页都有 `vision_review.json` 条目；图片/截图密集页做过 OCR 或视觉检查；
- 每个清单元素要么在讲稿里覆盖、要么明确标"无需讲"；图表坐标轴/图例/关键数值、表格表头/关键对比都处理了；
- 口头主张不超出该页证据；
- 术语表仅在开关为 on 时存在，且每个术语都有定义；
- 成品根目录只放面向用户的交付物，中间文件都在 `work/`；clean 版无任何标记；`notes.json` 覆盖 1..N 页。

---

## 8. 最终交付（聊天里的输出）

默认**只给摘要 + 文件路径**，不贴整份逐页讲稿：

1. 一句话简报：主旨、页数、输出语言、glossary 开关；
2. 三类成品的路径（PPT、排练文档、视觉审阅包；Markdown 仅在生成时列出）；
3. 不确定视觉元素的覆盖说明；
4. 提示中间证据都在 `work/`；
5. 提示"回复 show notes 可贴出完整逐页讲稿"。

---

## 9. 依赖与降级策略

优先用已装工具，未经同意不装包。各依赖缺失时的降级：

| 依赖 | 用途 | 缺失时 |
|---|---|---|
| `python-pptx` | 读取 PPT 对象 / 注入备注 | 提取与注入无法进行（硬依赖） |
| LibreOffice / `soffice` | 高质量渲染 | 回退 `qlmanage` |
| macOS `qlmanage` | 渲染兜底 | 用其它本地渲染并记录限制 |
| `tesseract` | OCR | 跳过 OCR，靠 XML + 视觉审阅 |
| `Pillow` | 裁剪图片区域 | 区域 OCR 回退整页 OCR |
| 视觉模型/截图工具 | 判读图表/图示/截图 | 停在审阅步骤前，告知哪些页不可靠 |
| `python-docx` | 生成 .docx | 写成 .md 兜底 |

原则：缺依赖就用现有最强证据继续，并明确报告限制。
