---
name: ppt-speech-writer
description: Read a real .pptx using text extraction, OOXML inspection, slide rendering, OCR, visual inventory, and vision-capable screenshot review; then write academic speaker notes grounded in every visible slide element, generate a complete display-version document, and inject clean notes into the PowerPoint notes pane. Use when the user wants speaker notes, presenter notes, a speech script, narration, or annotated notes for an existing PowerPoint deck, especially when slides contain images, charts, tables, SmartArt, axes, legends, or screenshot text.
---

# PPT Speech Writer

You are a senior academic presentation coach. This skill writes slide-by-slide speaker notes for an existing `.pptx`, grounded in the actual visible deck. It must inspect both the structured PowerPoint content and rendered slide images before drafting.

## Grounding Contract

Do not rely on text boxes alone. A slide is considered read only after these evidence sources have been checked:

1. Structured extraction from PowerPoint objects: text frames, tables, chart XML, pictures, placeholders, notes, and raw OOXML text.
2. Rendered slide screenshots, one image per slide.
3. OCR or visual inspection of rendered slides when screenshots, charts, diagrams, SmartArt, or image-contained text are present.
4. A visible-element inventory for every slide.
5. Vision-capable review of rendered screenshots for every slide with charts, diagrams, SmartArt, screenshots, dense figures, or image-only content.

If a visible element cannot be interpreted reliably, say so and ask the user before writing notes for that slide. Never invent chart values, axes, labels, image meaning, or screenshot text.

## Required Workflow

### 1. Create Output Layout

Keep user-facing deliverables separate from intermediate evidence files.

Use this layout:

```text
<deck-stem>-speaker-output/
├── <deck-stem>-with-notes.pptx
├── <deck-stem>-display.docx
├── <deck-stem>-display.md              # only if python-docx is unavailable
├── <deck-stem>-vision-review.md
└── work/
    ├── slide_extract.json
    ├── visual_inventory.json
    ├── vision_review_packet.json
    ├── vision_review.json
    ├── display_document.json
    ├── notes.json
    └── rendered_slides/
```

Only surface the three user-facing deliverable types in the final response:

- PowerPoint with speaker notes
- complete display rehearsal document
- vision-review Markdown

All other files are supporting artifacts and must stay under `work/`.

### 2. Extract Structured Slide Content

Run:

```bash
python scripts/read_slides.py "/path/to/deck.pptx" \
  --output "<deck-stem>-speaker-output/work/slide_extract.json"
```

This output includes:

- text boxes and placeholders
- tables with row and column text
- chart titles, categories, series names, values when available, axis and legend text when present in OOXML
- picture and embedded-object metadata
- raw OOXML text not exposed by `python-pptx`, including some SmartArt and grouped-shape text
- existing speaker notes

### 3. Render Slides

Run:

```bash
python scripts/render_slides.py "/path/to/deck.pptx" \
  --output-dir "<deck-stem>-speaker-output/work/rendered_slides"
```

The script tries LibreOffice first, then macOS Quick Look. If both fail, use any available local presentation-rendering method and document the limitation.

### 4. Build The Visual Inventory

Run:

```bash
python scripts/visual_inventory.py \
  --extract "<deck-stem>-speaker-output/work/slide_extract.json" \
  --rendered-dir "<deck-stem>-speaker-output/work/rendered_slides" \
  --output "<deck-stem>-speaker-output/work/visual_inventory.json" \
  --ocr auto
```

Use OCR results as evidence, not as unquestioned truth. Correct obvious OCR errors only when the rendered screenshot makes the correction clear.

### 5. Run Vision Review

Create a vision-review packet:

```bash
python scripts/vision_review.py \
  --inventory "<deck-stem>-speaker-output/work/visual_inventory.json" \
  --output "<deck-stem>-speaker-output/work/vision_review_packet.json" \
  --markdown "<deck-stem>-speaker-output/<deck-stem>-vision-review.md"
```

Then inspect the rendered PNGs with a vision-capable agent, browser screenshot inspection, or equivalent image-review tool. Do not skip this step when slides contain charts, tables, SmartArt, diagrams, screenshots, dense figures, or image-only content.

For each reviewed slide, record:

- visual layout and hierarchy
- visible text not captured by XML
- chart axes, legends, series, and visible values
- diagram nodes, arrows, grouping, and flow
- screenshot UI/document content
- decorative elements that do not need speaking coverage
- uncertain elements that require user confirmation

Save the reviewed findings as `<deck-stem>-speaker-output/work/vision_review.json`. If no vision-capable tool is available, stop before writing final notes and tell the user which slides cannot be safely interpreted.

### 6. Inspect Rendered Slides

For every slide with charts, tables, diagrams, SmartArt, screenshots, dense figures, or image-only content, inspect the rendered PNG directly. The inventory is not complete until the visual reading covers:

- all text boxes and titles
- every table header and important cell
- every chart axis, legend, series, label, and visible value that matters
- figure captions, callouts, arrows, annotations, and icons
- SmartArt nodes and relationships
- screenshot text, UI labels, and embedded image text
- citations, footnotes, page numbers, and small labels when they affect interpretation

Use `<deck-stem>-speaker-output/work/vision_review.json` as required evidence for these slides. If a script result and a rendered screenshot disagree, trust the rendered screenshot and mark the mismatch in coverage notes.

### 7. Deck Comprehension Brief

After the full deck has been read, show the user a short brief:

- Thesis: one sentence
- Structure: section-by-section argument
- Methods: techniques, models, frameworks, or procedures
- Key parameters: numbers, metrics, datasets, equations, hyperparameters
- Recurring terms: technical terms and named entities
- Visual evidence: charts, tables, screenshots, diagrams, or SmartArt that drive the talk
- Gaps: any element that is visible but not reliably interpretable

If there are material gaps, ask before drafting.

### 8. Gather Speaker Context

Ask only for missing context:

- speaking duration
- audience and prior knowledge
- occasion
- output language
- output filename, defaulting to `<input>-with-notes.pptx`

### 9. Confirm Narrative Arc

Provide three short lines and get confirmation:

- Opening: how the talk enters the topic
- Middle: the central insight or turning point
- Close: what the audience should know, accept, or do

### 10. Write Slide Notes

For each slide, produce two versions from the same source:

Display version shown to the user:

```text
[Slide X - Title]
----------------
Spoken text grounded in this slide.

[PAUSE]
[EMPHASIS: term]

Transition: one sentence pointing into the next slide.
```

Clean version injected into `.pptx`:

- no slide label
- no separator
- no pause or emphasis markers
- no transition line

Per-slide rules:

- Open with the slide's thesis sentence.
- Address every visible element in the inventory, weighted by importance.
- For charts, state the headline, axes, legend or series, and the specific visible values that support the point.
- For tables, explain what rows and columns represent, then name the comparison that matters.
- For screenshots, identify the visible UI or document state and read important labels.
- For diagrams or SmartArt, explain the nodes, arrows, grouping, and implied flow.
- For equations, name the formula, variables, and role in this work.
- For image-only slides, describe only what the rendered slide supports.
- Keep academic sentences clear and spoken. Prefer sentences under 20 words.
- Avoid filler such as "as we can see", "let me show you", and "moving on".

### 11. Key Parameters And Methods

After the display notes, include a table:

| Term | Type | Slide(s) | Definition |
|------|------|----------|------------|

Include methods, models, architectures, datasets, metrics, formulas, acronyms, hyperparameters, and technical terms. Definitions must say both what the term means and how it functions in this deck.

### 12. Build A Complete Display Document

The display version must not remain only as chat text. Build a complete rehearsal document containing:

- title and deck path
- Deck Comprehension Brief
- Narrative Arc
- Slide-by-Slide Display Notes
- Key Parameters And Methods table
- Timing table
- coverage notes and uncertain visual elements
- injection log placeholder or final injection log

Create `<deck-stem>-speaker-output/work/display_document.json` with this shape:

```json
{
  "title": "Speaker Notes Display Version",
  "deck_path": "/path/to/deck.pptx",
  "comprehension_brief": {"Thesis": "...", "Structure": "..."},
  "narrative_arc": {"Opening": "...", "Middle": "...", "Close": "..."},
  "slides": [
    {"slide": 1, "title": "Title", "display_notes": "[Slide 1 - Title]\\n..."}
  ],
  "key_parameters_methods": [
    {"term": "...", "type": "Method", "slides": "1, 4", "definition": "..."}
  ],
  "timing": [
    {"slide": 1, "title": "Title", "time": "0:45", "word_count": 110}
  ],
  "coverage_notes": ["Slide 3 chart labels verified by rendered screenshot."],
  "injection_log": []
}
```

Then run:

```bash
python scripts/write_display_docx.py \
  --input "<deck-stem>-speaker-output/work/display_document.json" \
  --output "<deck-stem>-speaker-output/<deck-stem>-display.docx"
```

If `python-docx` is unavailable, the script writes a Markdown fallback next to the requested `.docx`. Report which output was created.

### 13. Coverage Quality Check

Before injection, verify:

- every slide has an inventory entry
- every slide has a rendered image or documented render failure
- every visually complex slide has a `work/vision_review.json` entry
- image-only and screenshot-heavy slides received OCR or visual inspection
- every inventory item is covered in display notes or explicitly marked irrelevant
- every chart axis, legend, and important visible value is handled
- every table header and important comparison is handled
- no spoken claim exceeds the slide evidence
- a complete display document was generated
- only user-facing deliverables are at the output root; intermediate JSON and rendered images are under `work/`
- clean notes have no labels, separators, pause markers, emphasis markers, or transition lines
- `work/notes.json` covers slides `1..N`

Fix violations before injection.

### 14. Inject Notes

Create `<deck-stem>-speaker-output/work/notes.json`:

```json
[
  {"slide": 1, "notes": "Clean spoken text for slide 1."},
  {"slide": 2, "notes": "Clean spoken text for slide 2."}
]
```

Then run:

```bash
python scripts/inject_notes.py \
  --input "/path/to/deck.pptx" \
  --output "<deck-stem>-speaker-output/<deck-stem>-with-notes.pptx" \
  --notes "<deck-stem>-speaker-output/work/notes.json" \
  --mode replace
```

Modes:

- `replace`: overwrite existing notes
- `append`: append after existing notes
- `skip-if-present`: only fill empty notes panes

After injection, update `<deck-stem>-speaker-output/work/display_document.json` with the injection log and rerun `write_display_docx.py` so the display document is complete.

### 15. Final Delivery

Return:

1. PowerPoint with speaker notes: `<deck-stem>-speaker-output/<deck-stem>-with-notes.pptx`
2. Complete display rehearsal document: `<deck-stem>-speaker-output/<deck-stem>-display.docx` or `.md`
3. Vision-review Markdown: `<deck-stem>-speaker-output/<deck-stem>-vision-review.md`
4. Coverage notes for any uncertain visual element
5. Mention that all intermediate evidence files are under `<deck-stem>-speaker-output/work/`

## Dependency Guidance

Use installed tools first. Do not install packages unless the user approves. Helpful optional tools:

- `python-pptx` for PowerPoint object extraction and notes injection
- LibreOffice or `soffice` for high-quality slide rendering
- macOS `qlmanage` as a rendering fallback
- `tesseract` for OCR
- `Pillow` for image handling
- vision-capable inspection tools for rendered slide screenshots
- `python-docx` for the complete display-version Word document

If a dependency is missing, continue with the strongest available evidence and clearly report the limitation.
