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
from pathlib import Path


def run_ocr(image: Path) -> str:
    exe = shutil.which("tesseract")
    if not exe:
        return ""
    result = subprocess.run(
        [exe, str(image), "stdout"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return "\n".join(line.strip() for line in result.stdout.splitlines() if line.strip())


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


def build_inventory(extract: dict, rendered_dir: Path, use_ocr: bool) -> dict:
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
        ocr_text = run_ocr(image) if use_ocr and image else ""
        slides.append(
            {
                "slide": num,
                "title": slide.get("title", ""),
                "rendered_image": str(image) if image else "",
                "needs_direct_visual_inspection": bool(has_visual_object or ocr_text),
                "structured_elements": shapes,
                "raw_ooxml_text_not_in_shapes": slide.get("raw_ooxml_text_not_in_shapes", []),
                "ocr_text": ocr_text,
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
    args = parser.parse_args(argv)

    if not args.extract.exists():
        sys.stderr.write(f"Extract JSON not found: {args.extract}\n")
        return 1
    data = json.loads(args.extract.read_text(encoding="utf-8"))
    inventory = build_inventory(data, args.rendered_dir, args.ocr == "auto")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
