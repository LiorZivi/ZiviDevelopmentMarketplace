#!/usr/bin/env python3
"""
Converts a structured markdown file into a branded PowerPoint presentation.

Usage:
    python md_to_pptx.py --input output/ramp-up/Topic.md --output output/ramp-up/Topic.pptx

The markdown must follow the output template structure:
    # Title           -> title slide
    ## Section        -> section slide
    ### Subsection    -> content slide
    | tables |        -> table slide
    - bullets         -> bullet content
"""

import argparse
import re
import sys
import os

# Add parent dir to path so we can import from themes/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pptx_engine import PptxEngine


def parse_markdown(md_text):
    """Parse structured markdown into a list of sections and content blocks."""
    lines = md_text.split("\n")
    blocks = []
    current_block = None
    in_code_block = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Track code block boundaries — skip all lines inside code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            i += 1
            continue
        if in_code_block:
            i += 1
            continue

        # H1 title
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            # Look for subtitle (next non-empty line that starts with >)
            subtitle = ""
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and lines[j].strip().startswith(">"):
                subtitle = lines[j].strip().lstrip("> ").strip()
            blocks.append({"type": "title", "title": title, "subtitle": subtitle})
            i = j + 1 if subtitle else i + 1
            continue

        # H2 section
        if line.startswith("## ") and not line.startswith("### "):
            if current_block:
                blocks.append(current_block)
            section_title = line[3:].strip()
            # Remove leading numbers like "1. " or "1) "
            section_title = re.sub(r"^\d+[\.\)]\s*", "", section_title)
            current_block = {
                "type": "section",
                "title": section_title,
                "subsections": [],
            }
            i += 1
            continue

        # H3 subsection
        if line.startswith("### "):
            sub_title = line[4:].strip()
            sub_title = re.sub(r"^\d+[\.\)]\s*", "", sub_title)
            if current_block and current_block["type"] == "section":
                current_block["subsections"].append({
                    "title": sub_title,
                    "bullets": [],
                    "tables": [],
                })
            i += 1
            continue

        # Table detection
        if "|" in line and line.strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            table = _parse_table(table_lines)
            if table:
                _add_table_to_current(current_block, table)
            continue

        # Bullet points
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            bullet_text = stripped[2:].strip()
            # Clean markdown formatting
            bullet_text = _clean_md(bullet_text)
            _add_bullet_to_current(current_block, bullet_text)
            i += 1
            continue

        # Numbered list items
        num_match = re.match(r"^\s*\d+[\.\)]\s+(.+)", stripped)
        if num_match:
            bullet_text = _clean_md(num_match.group(1))
            _add_bullet_to_current(current_block, bullet_text)
            i += 1
            continue

        # Bold paragraph (treat as bullet)
        if stripped.startswith("**") and stripped.endswith("**"):
            bullet_text = _clean_md(stripped)
            _add_bullet_to_current(current_block, bullet_text)
            i += 1
            continue

        # H4/H5 headings — treat as bold bullet under current subsection
        h4_match = re.match(r"^#{4,5}\s+(.+)", line)
        if h4_match:
            bullet_text = _clean_md(h4_match.group(1))
            if bullet_text:
                _add_bullet_to_current(current_block, bullet_text)
            i += 1
            continue

        # Non-empty text that's not a heading/list/table — treat as a bullet
        if stripped and not stripped.startswith("---"):
            bullet_text = _clean_md(stripped)
            if bullet_text:
                _add_bullet_to_current(current_block, bullet_text)
            i += 1
            continue

        i += 1

    if current_block:
        blocks.append(current_block)

    return blocks


def _clean_md(text):
    """Remove markdown formatting for slide text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # italic
    text = re.sub(r"`(.+?)`", r"\1", text)  # inline code
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)  # links
    return text.strip()


def _parse_table(lines):
    """Parse markdown table lines into headers and rows."""
    if len(lines) < 2:
        return None

    def split_row(line):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        return [_clean_md(c) for c in cells if c.strip()]

    headers = split_row(lines[0])

    # Skip separator row (---|----|---)
    data_start = 1
    if data_start < len(lines) and re.match(r"^[\|\s\-:]+$", lines[data_start]):
        data_start = 2

    rows = []
    for line in lines[data_start:]:
        row = split_row(line)
        if row and len(row) == len(headers):
            rows.append(row)
        elif row:
            # Pad or truncate to match headers
            while len(row) < len(headers):
                row.append("")
            rows.append(row[:len(headers)])

    if not headers:
        return None
    return {"headers": headers, "rows": rows}


def _add_table_to_current(block, table):
    """Add a parsed table to the current block's active subsection or directly."""
    if block and block["type"] == "section" and block["subsections"]:
        block["subsections"][-1]["tables"].append(table)
    elif block and block["type"] == "section":
        # Table directly under a section (no subsection)
        block["subsections"].append({
            "title": "",
            "bullets": [],
            "tables": [table],
        })


def _add_bullet_to_current(block, bullet_text):
    """Add a bullet to the current block's active subsection or section directly."""
    if not bullet_text:
        return
    if block and block["type"] == "section" and block["subsections"]:
        block["subsections"][-1]["bullets"].append(bullet_text)
    elif block and block["type"] == "section":
        block["subsections"].append({
            "title": "",
            "bullets": [bullet_text],
            "tables": [],
        })


def _split_bullets_into_slides(bullets, max_per_slide=7):
    """Split a long bullet list into multiple slide-sized chunks."""
    if len(bullets) <= max_per_slide:
        return [bullets]
    chunks = []
    for i in range(0, len(bullets), max_per_slide):
        chunks.append(bullets[i:i + max_per_slide])
    return chunks


def _split_table_rows(table, max_rows=8):
    """Split a large table into multiple slides."""
    if len(table["rows"]) <= max_rows:
        return [table]
    tables = []
    for i in range(0, len(table["rows"]), max_rows):
        tables.append({
            "headers": table["headers"],
            "rows": table["rows"][i:i + max_rows],
        })
    return tables


def build_presentation(blocks, footer_text=""):
    """Convert parsed blocks into a PPTX using the engine."""
    # Find title
    title = "Presentation"
    subtitle = ""
    for b in blocks:
        if b["type"] == "title":
            title = b["title"]
            subtitle = b.get("subtitle", "")
            break

    engine = PptxEngine(
        title=title,
        subtitle=subtitle,
        footer_text=footer_text or title,
    )

    section_num = 0

    for block in blocks:
        if block["type"] == "title":
            continue  # Already handled by engine constructor

        if block["type"] == "section":
            section_num += 1
            engine.add_section_slide(section_num, block["title"])

            for sub in block["subsections"]:
                # Content slide with bullets
                if sub["bullets"]:
                    slide_title = sub["title"] or block["title"]
                    chunks = _split_bullets_into_slides(sub["bullets"])
                    for i, chunk in enumerate(chunks):
                        t = slide_title
                        if len(chunks) > 1:
                            t = f"{slide_title} ({i + 1}/{len(chunks)})"
                        engine.add_content_slide(t, chunk)

                # Table slides
                for table in sub["tables"]:
                    table_title = sub["title"] or block["title"]
                    split_tables = _split_table_rows(table)
                    for i, t in enumerate(split_tables):
                        tt = table_title
                        if len(split_tables) > 1:
                            tt = f"{table_title} ({i + 1}/{len(split_tables)})"
                        engine.add_table_slide(tt, t["headers"], t["rows"])

                # Subsection with no bullets and no tables — skip
                if not sub["bullets"] and not sub["tables"] and sub["title"]:
                    engine.add_content_slide(sub["title"], ["(Content to be added)"])

    # Closing slide
    engine.add_closing_slide(
        title="Key Takeaways",
        subtitle=title,
    )

    return engine


def main():
    parser = argparse.ArgumentParser(description="Convert structured markdown to PPTX")
    parser.add_argument("--input", required=True, help="Path to input .md file")
    parser.add_argument("--output", required=True, help="Path to output .pptx file")
    parser.add_argument("--footer", default="", help="Footer text (defaults to title)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        md_text = f.read()

    blocks = parse_markdown(md_text)
    engine = build_presentation(blocks, footer_text=args.footer)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    num_slides = engine.save(args.output)
    print(f"Generated {num_slides} slides -> {args.output}")


if __name__ == "__main__":
    main()
