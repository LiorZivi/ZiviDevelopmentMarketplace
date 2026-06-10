#!/usr/bin/env python3
"""
Export each slide of a PPTX as a PNG image so it can be embedded in a LinkedIn article.

Usage:
    python export_slides.py --input output/learn/Topic.pptx \
        --output-dir output/learn/images --prefix Topic [--width 1920]

This is a best-effort helper. Rendering a .pptx to images has no pure-Python solution that
works everywhere, so we try the high-fidelity options first and degrade gracefully:

  1. Microsoft PowerPoint COM automation (Windows + PowerPoint installed, via pywin32).
     This is the most faithful renderer and is usually present on Windows work machines.
  2. LibreOffice headless (`soffice`) -> PDF, then PyMuPDF (`fitz`) -> PNG per page.
     A cross-platform fallback for machines without PowerPoint.
  3. If neither is available, print SKIP_EXPORT with manual-export guidance and exit 0.

Exiting 0 on skip is deliberate: missing a renderer must never block the rest of the skill.
The LinkedIn article is still written with image placeholders, and the user can export the
slides by hand (PowerPoint: File > Export > PNG).

Output files are named `{prefix}-slide-01.png`, `{prefix}-slide-02.png`, ... in deck order.
The script prints a manifest line per image (`SLIDE 01 -> <path>`) and a final
`EXPORTED <n>` (or `SKIP_EXPORT`) so the caller knows which files exist.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile


def _pad(n):
    return f"{n:02d}"


def export_with_powerpoint(input_path, out_dir, prefix, width):
    """Strategy 1: drive an installed Microsoft PowerPoint via COM (Windows only)."""
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except Exception:
        return None  # pywin32 not installed -> let the caller try the next strategy

    try:
        pythoncom.CoInitialize()
    except Exception:
        pass

    height = int(round(width * 9 / 16))  # decks are 16:9
    app = None
    pres = None
    try:
        app = win32com.client.Dispatch("PowerPoint.Application")
        # Opening windowless keeps the deck off-screen; some builds reject it, so retry visibly.
        try:
            pres = app.Presentations.Open(
                os.path.abspath(input_path), ReadOnly=True, WithWindow=False
            )
        except Exception:
            try:
                app.Visible = 1
            except Exception:
                pass
            pres = app.Presentations.Open(os.path.abspath(input_path), ReadOnly=True)

        paths = []
        count = int(pres.Slides.Count)
        for idx in range(1, count + 1):
            dest = os.path.abspath(os.path.join(out_dir, f"{prefix}-slide-{_pad(idx)}.png"))
            pres.Slides.Item(idx).Export(dest, "PNG", width, height)
            paths.append(dest)
        return paths or None
    except Exception as exc:  # PowerPoint not installed or automation blocked
        sys.stderr.write(f"PowerPoint COM export failed: {exc}\n")
        return None
    finally:
        try:
            if pres is not None:
                pres.Close()
        except Exception:
            pass
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _find_soffice():
    cmd = shutil.which("soffice") or shutil.which("soffice.exe")
    if cmd:
        return cmd
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def export_with_libreoffice(input_path, out_dir, prefix, width):
    """Strategy 2: LibreOffice converts the deck to PDF, then PyMuPDF rasterizes each page."""
    soffice = _find_soffice()
    if not soffice:
        return None
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None

    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp,
                 os.path.abspath(input_path)],
                check=True, capture_output=True, timeout=180,
            )
        except Exception as exc:
            sys.stderr.write(f"LibreOffice conversion failed: {exc}\n")
            return None

        pdfs = glob.glob(os.path.join(tmp, "*.pdf"))
        if not pdfs:
            return None

        doc = fitz.open(pdfs[0])
        try:
            paths = []
            for i, page in enumerate(doc, start=1):
                page_width = page.rect.width or 720.0
                zoom = width / page_width
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                dest = os.path.abspath(os.path.join(out_dir, f"{prefix}-slide-{_pad(i)}.png"))
                pix.save(dest)
                paths.append(dest)
            return paths or None
        finally:
            doc.close()


def main():
    parser = argparse.ArgumentParser(description="Export PPTX slides to PNG images.")
    parser.add_argument("--input", required=True, help="Path to the .pptx file")
    parser.add_argument("--output-dir", required=True, help="Directory to write PNGs into")
    parser.add_argument("--prefix", required=True, help="Filename prefix, e.g. the Topic name")
    parser.add_argument("--width", type=int, default=1920, help="Image width in pixels")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"SKIP_EXPORT: presentation not found at {args.input}")
        print("Generate the .pptx first, or export slides manually once it exists.")
        return 0

    os.makedirs(args.output_dir, exist_ok=True)

    for strategy in (export_with_powerpoint, export_with_libreoffice):
        paths = strategy(args.input, args.output_dir, args.prefix, args.width)
        if paths:
            for i, path in enumerate(paths, start=1):
                print(f"SLIDE {_pad(i)} -> {path}")
            print(f"EXPORTED {len(paths)}")
            return 0

    print("SKIP_EXPORT: no slide renderer available.")
    print("Install Microsoft PowerPoint (Windows) or LibreOffice + PyMuPDF to auto-export slides.")
    print("Manual export: open the .pptx, then File > Export > Change File Type > PNG > Save Every Slide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
