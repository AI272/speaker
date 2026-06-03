#!/usr/bin/env python3
"""Render a .pptx deck to per-slide PNG images.

LibreOffice/soffice is preferred. On macOS, qlmanage is used as a fallback.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)


def render_with_soffice(deck: Path, output_dir: Path) -> bool:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return False
    output_dir.mkdir(parents=True, exist_ok=True)
    result = run([exe, "--headless", "--convert-to", "png", "--outdir", str(output_dir), str(deck)])
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return False
    return bool(list(output_dir.glob("*.png")))


def render_with_qlmanage(deck: Path, output_dir: Path) -> bool:
    exe = shutil.which("qlmanage")
    if not exe:
        return False
    output_dir.mkdir(parents=True, exist_ok=True)
    result = run([exe, "-t", "-s", "1600", "-o", str(output_dir), str(deck)])
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return False
    images = list(output_dir.glob("*.png"))
    if len(images) == 1:
        images[0].rename(output_dir / "slide-preview.png")
    return bool(list(output_dir.glob("*.png")))


def normalize_names(output_dir: Path) -> None:
    images = sorted(output_dir.glob("*.png"))
    for idx, image in enumerate(images, start=1):
        target = output_dir / f"slide-{idx:03d}.png"
        if image.name != target.name and not target.exists():
            image.rename(target)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render .pptx slides to PNG images.")
    parser.add_argument("deck", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    if not args.deck.exists():
        sys.stderr.write(f"File not found: {args.deck}\n")
        return 1
    if render_with_soffice(args.deck, args.output_dir):
        normalize_names(args.output_dir)
        print(f"rendered with soffice/libreoffice: {args.output_dir}")
        return 0
    if render_with_qlmanage(args.deck, args.output_dir):
        normalize_names(args.output_dir)
        print(f"rendered with qlmanage: {args.output_dir}")
        return 0
    sys.stderr.write("No supported renderer found. Install LibreOffice or use a platform renderer.\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
