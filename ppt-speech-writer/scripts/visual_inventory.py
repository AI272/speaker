#!/usr/bin/env python3
"""Create a slide-by-slide visible-element inventory.

This combines structured extraction, rendered slide image paths, and optional
OCR output. The inventory is intended to guide speaker-note coverage.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _tesseract(image: Path) -> str:
    exe = shutil.which("tesseract")
    if not exe:
        return ""
    # Resolve symlinks: tesseract's leptonica fopenReadStream can fail to open a
    # path that traverses a symlinked directory (e.g. macOS /tmp -> /private/tmp).
    try:
        image = Path(image).resolve()
    except OSError:
        pass
    result = subprocess.run(
        [exe, str(image), "stdout"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return ""
    text = result.stdout.decode("utf-8", errors="ignore")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def run_ocr(image: Path) -> str:
    """OCR the entire rendered slide image."""
    return _tesseract(image)


def picture_regions(shapes: list[dict], slide_w_emu, slide_h_emu, img_w: int, img_h: int) -> list[dict]:
    """Map picture/media bounding boxes (EMU) to pixel crop boxes on the rendered image."""
    if not (slide_w_emu and slide_h_emu and img_w and img_h):
        return []
    scale_x = img_w / slide_w_emu
    scale_y = img_h / slide_h_emu
    regions: list[dict] = []
    for shape in shapes:
        kind = str(shape.get("kind", "")).upper()
        if "PICTURE" not in kind and "MEDIA" not in kind:
            continue
        bbox = shape.get("bbox_emu") or {}
        left, top, width, height = bbox.get("left"), bbox.get("top"), bbox.get("width"), bbox.get("height")
        if None in (left, top, width, height):
            continue
        x0 = max(0, int(left * scale_x))
        y0 = max(0, int(top * scale_y))
        x1 = min(img_w, int((left + width) * scale_x))
        y1 = min(img_h, int((top + height) * scale_y))
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        regions.append(
            {
                "shape_index": shape.get("shape_index"),
                "name": shape.get("name"),
                "box": [x0, y0, x1, y1],
            }
        )
    return regions


def ocr_regions(image: Path, shapes: list[dict], slide_w_emu, slide_h_emu) -> tuple[str, list[dict], str]:
    """OCR only the picture/media regions of a slide.

    Returns (combined_text, per_region_results, scope_used). Falls back to a
    full-image OCR when Pillow is unavailable or slide geometry is missing, so
    OCR evidence is never silently dropped.
    """
    try:
        from PIL import Image
    except ImportError:
        return run_ocr(image), [], "full (Pillow unavailable)"

    with Image.open(image) as im:
        img_w, img_h = im.size
        regions = picture_regions(shapes, slide_w_emu, slide_h_emu, img_w, img_h)
        if not regions:
            return "", [], "image-regions (no picture regions)"
        results: list[dict] = []
        for region in regions:
            crop = im.crop(tuple(region["box"]))
            tmp_path = Path(tempfile.mkstemp(suffix=".png")[1])
            try:
                crop.save(tmp_path)
                text = _tesseract(tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)
            if text:
                results.append(
                    {"shape_index": region["shape_index"], "name": region["name"], "text": text}
                )
    combined = "\n".join(r["text"] for r in results)
    return combined, results, "image-regions"


def slide_image(rendered_dir: Path, slide_num: int) -> Path | None:
    candidates = [
        rendered_dir / f"slide-{slide_num:03d}.png",
        rendered_dir / f"slide-{slide_num}.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    images = sorted(rendered_dir.glob("*.png"))
    if 1 <= slide_num <= len(images):
        return images[slide_num - 1]
    return None


def summarize_shape(shape: dict) -> dict:
    item = {
        "shape_index": shape.get("shape_index"),
        "name": shape.get("name"),
        "kind": shape.get("kind"),
        "bbox_emu": shape.get("bbox_emu"),
    }
    for key in ("text", "tables", "chart", "visual_note"):
        if key in shape:
            item[key] = shape[key]
    return item


def build_inventory(extract: dict, rendered_dir: Path, use_ocr: bool, ocr_scope: str) -> dict:
    slide_w = extract.get("slide_width_emu")
    slide_h = extract.get("slide_height_emu")
    slides = []
    for slide in extract.get("slides", []):
        num = int(slide["slide"])
        image = slide_image(rendered_dir, num)
        shapes = [summarize_shape(shape) for shape in slide.get("shapes", [])]
        has_visual_object = any(
            "PICTURE" in str(shape.get("kind", "")).upper()
            or "CHART" in str(shape.get("kind", "")).upper()
            or shape.get("chart")
            or shape.get("tables")
            for shape in shapes
        )
        ocr_text = ""
        ocr_region_results: list[dict] = []
        scope_used = "off"
        if use_ocr and image:
            if ocr_scope == "image-regions":
                ocr_text, ocr_region_results, scope_used = ocr_regions(image, shapes, slide_w, slide_h)
            else:
                ocr_text = run_ocr(image)
                scope_used = "full"
        slides.append(
            {
                "slide": num,
                "title": slide.get("title", ""),
                "rendered_image": str(image) if image else "",
                "needs_direct_visual_inspection": bool(has_visual_object or ocr_text),
                "structured_elements": shapes,
                "raw_ooxml_text_not_in_shapes": slide.get("raw_ooxml_text_not_in_shapes", []),
                "ocr_scope": scope_used,
                "ocr_text": ocr_text,
                "ocr_regions": ocr_region_results,
                "coverage_checklist": [
                    "title and text boxes",
                    "tables and important cells",
                    "chart axes, legend, labels, series, visible values",
                    "images, screenshots, diagrams, SmartArt, icons, and annotations",
                    "citations, footnotes, and small labels",
                ],
            }
        )
    return {
        "deck": extract.get("deck", ""),
        "slide_count": extract.get("slide_count", len(slides)),
        "rendered_dir": str(rendered_dir),
        "slides": slides,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build visible-element inventory for a rendered .pptx.")
    parser.add_argument("--extract", required=True, type=Path)
    parser.add_argument("--rendered-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ocr", choices=["auto", "off"], default="auto")
    parser.add_argument(
        "--ocr-scope",
        choices=["image-regions", "full"],
        default="image-regions",
        help="image-regions OCRs only picture/media crops (text boxes already come from XML); full OCRs the whole slide.",
    )
    args = parser.parse_args(argv)

    if not args.extract.exists():
        sys.stderr.write(f"Extract JSON not found: {args.extract}\n")
        return 1
    data = json.loads(args.extract.read_text(encoding="utf-8"))
    inventory = build_inventory(data, args.rendered_dir, args.ocr == "auto", args.ocr_scope)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
