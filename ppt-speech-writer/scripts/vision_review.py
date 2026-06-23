#!/usr/bin/env python3
"""Build a vision-review packet from a visual inventory.

This script does not claim to understand images. It prepares a deterministic
review packet that a vision-capable agent or human reviewer can use to inspect
rendered slide screenshots and record grounded visual findings.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REVIEW_PROMPT = """Inspect the rendered slide image and complete this review.
Use only what is visible in the screenshot and the structured evidence below.
Do not infer hidden data or author intent beyond the slide.

Return:
1. layout_summary
2. visible_text_not_in_xml
3. charts_axes_legends_values
4. tables_and_key_cells
5. diagrams_smartart_arrows_flow
6. screenshots_or_images
7. decorative_or_low_priority_elements
8. uncertain_elements
9. coverage_requirements_for_speaker_notes
"""


RESULT_TEMPLATE = {
    "layout_summary": "",
    "visible_text_not_in_xml": [],
    "charts_axes_legends_values": [],
    "tables_and_key_cells": [],
    "diagrams_smartart_arrows_flow": [],
    "screenshots_or_images": [],
    "decorative_or_low_priority_elements": [],
    "uncertain_elements": [],
    "coverage_requirements_for_speaker_notes": [],
}


def compact_elements(slide: dict) -> list[dict]:
    out = []
    for item in slide.get("structured_elements", []):
        compact = {
            "shape_index": item.get("shape_index"),
            "kind": item.get("kind"),
            "name": item.get("name"),
        }
        for key in ("text", "tables", "chart", "visual_note"):
            if key in item:
                compact[key] = item[key]
        out.append(compact)
    return out


def build_packet(inventory: dict, compact: bool = True) -> dict:
    slides = []
    for slide in inventory.get("slides", []):
        entry = {
            "slide": slide.get("slide"),
            "title": slide.get("title", ""),
            "rendered_image": slide.get("rendered_image", ""),
            "requires_vision_review": bool(slide.get("needs_direct_visual_inspection", False)),
            "structured_evidence": compact_elements(slide),
            "raw_ooxml_text_not_in_shapes": slide.get("raw_ooxml_text_not_in_shapes", []),
            "ocr_text": slide.get("ocr_text", ""),
        }
        if slide.get("ocr_regions"):
            entry["ocr_regions"] = slide["ocr_regions"]
        if not compact:
            entry["review_prompt"] = REVIEW_PROMPT
            entry["review_result_template"] = dict(RESULT_TEMPLATE)
        slides.append(entry)
    packet = {
        "deck": inventory.get("deck", ""),
        "slide_count": inventory.get("slide_count", len(slides)),
        "instruction": "Use a vision-capable reviewer to fill review_result_schema for slides where requires_vision_review is true.",
        "review_prompt": REVIEW_PROMPT,
        "review_result_schema": dict(RESULT_TEMPLATE),
        "slides": slides,
    }
    return packet


def write_markdown(packet: dict, path: Path) -> None:
    lines = [
        "# Vision Review Packet",
        "",
        f"Deck: {packet.get('deck', '')}",
        f"Slide count: {packet.get('slide_count', '')}",
        "",
        "## Review Prompt (applies to every slide below)",
        "",
        packet.get("review_prompt", REVIEW_PROMPT),
        "",
    ]
    for slide in packet.get("slides", []):
        lines.extend(
            [
                f"## Slide {slide.get('slide')} - {slide.get('title', '')}",
                "",
                f"Rendered image: {slide.get('rendered_image', '')}",
                f"Requires vision review: {slide.get('requires_vision_review')}",
                "",
                "### OCR Text",
                "",
                slide.get("ocr_text", "") or "(none)",
                "",
                "### Structured Evidence",
                "",
                "```json",
                json.dumps(slide.get("structured_evidence", []), ensure_ascii=False, indent=2),
                "```",
                "",
                "### Review Result",
                "",
                "Fill this section after visual inspection.",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create a vision-review packet from visual_inventory.json.")
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--markdown", type=Path, help="optional; the compact JSON packet is the primary output.")
    parser.add_argument(
        "--format",
        choices=["compact", "full"],
        default="compact",
        help="compact hoists the shared review prompt/schema to the top level instead of repeating them per slide.",
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        sys.stderr.write(f"Inventory not found: {args.inventory}\n")
        return 1
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    packet = build_packet(inventory, compact=args.format == "compact")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(packet, args.markdown)
    print(f"saved: {args.output}")
    if args.markdown:
        print(f"saved: {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
