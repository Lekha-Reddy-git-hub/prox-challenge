"""
Knowledge Extraction Script for Vulcan OmniPro 220
Converts PDF manuals to structured knowledge base using PyMuPDF + Claude Vision.

Usage:
    python knowledge/extract.py              # Extract PNGs only (no API needed)
    python knowledge/extract.py --vision     # Also run Claude Vision extraction (needs API key)
"""

import os
import sys
import json
import base64
import argparse
import fitz  # PyMuPDF

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

KNOWLEDGE_DIR = os.path.join(PROJECT_ROOT, "knowledge")
PAGES_DIR = os.path.join(KNOWLEDGE_DIR, "pages")
FILES_DIR = os.path.join(PROJECT_ROOT, "files")

# Section mapping: page ranges → section names and applicable processes
SECTION_MAP = [
    {"pages": [1], "section": "Cover", "processes": []},
    {"pages": list(range(2, 7)), "section": "Safety", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [7], "section": "Specifications", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [8], "section": "Controls - Front Panel", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [9], "section": "Controls - Interior", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [10, 11], "section": "Setup - General", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [12, 13], "section": "Wire Feed Mechanism", "processes": ["MIG", "Flux-Core"]},
    {"pages": [14, 15, 16], "section": "Polarity Setup", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [17, 18], "section": "Gas Setup", "processes": ["MIG", "TIG"]},
    {"pages": list(range(19, 24)), "section": "MIG Welding Setup & Operation", "processes": ["MIG"]},
    {"pages": [24, 25, 26], "section": "TIG Welding Setup & Operation", "processes": ["TIG"]},
    {"pages": [27, 28], "section": "Stick Welding Setup & Operation", "processes": ["Stick"]},
    {"pages": [29], "section": "Duty Cycles", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [30, 31], "section": "TIG Welding Tips & Settings", "processes": ["TIG"]},
    {"pages": [32, 33], "section": "Stick Welding Tips & Settings", "processes": ["Stick"]},
    {"pages": list(range(34, 38)), "section": "Welding Tips - Wire", "processes": ["MIG", "Flux-Core"]},
    {"pages": list(range(38, 41)), "section": "Welding Tips - Stick", "processes": ["Stick"]},
    {"pages": [41], "section": "Maintenance", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [42, 43, 44], "section": "Troubleshooting", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [45], "section": "Wiring Schematic", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [46, 47], "section": "Parts List", "processes": ["MIG", "Flux-Core", "TIG", "Stick"]},
    {"pages": [48], "section": "Warranty", "processes": []},
]


def get_section_for_page(page_num: int) -> dict:
    """Get section info for a given page number (1-indexed)."""
    for section in SECTION_MAP:
        if page_num in section["pages"]:
            return {"section": section["section"], "processes": section["processes"]}
    return {"section": "Unknown", "processes": []}


def extract_pngs():
    """Convert all PDF pages to PNG images."""
    os.makedirs(PAGES_DIR, exist_ok=True)

    # Owner's manual (48 pages)
    print("Extracting owner's manual pages...")
    doc = fitz.open(os.path.join(FILES_DIR, "owner-manual.pdf"))
    for i in range(doc.page_count):
        page = doc[i]
        # Render at 2x for readability (150 DPI default * 2 = 300 DPI)
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        output_path = os.path.join(PAGES_DIR, f"page-{i+1:02d}.png")
        pix.save(output_path)
        print(f"  page-{i+1:02d}.png ({pix.width}x{pix.height})")
    doc.close()

    # Quick start guide (2 pages)
    print("Extracting quick start guide pages...")
    doc = fitz.open(os.path.join(FILES_DIR, "quick-start-guide.pdf"))
    for i in range(doc.page_count):
        page = doc[i]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        output_path = os.path.join(PAGES_DIR, f"quickstart-{i+1:02d}.png")
        pix.save(output_path)
        print(f"  quickstart-{i+1:02d}.png ({pix.width}x{pix.height})")
    doc.close()

    # Selection chart (1 page)
    print("Extracting selection chart...")
    doc = fitz.open(os.path.join(FILES_DIR, "selection-chart.pdf"))
    for i in range(doc.page_count):
        page = doc[i]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        output_path = os.path.join(PAGES_DIR, f"selection-chart.png")
        pix.save(output_path)
        print(f"  selection-chart.png ({pix.width}x{pix.height})")
    doc.close()


def extract_text_basic():
    """Extract basic text from PDFs using PyMuPDF (no API needed)."""
    print("\nExtracting basic text from owner's manual...")
    doc = fitz.open(os.path.join(FILES_DIR, "owner-manual.pdf"))

    sections = []
    for section_def in SECTION_MAP:
        section_text = ""
        for page_num in section_def["pages"]:
            page = doc[page_num - 1]
            section_text += page.get_text() + "\n"

        sections.append({
            "section": section_def["section"],
            "processes": section_def["processes"],
            "pages": section_def["pages"],
            "content": section_text.strip(),
            "has_images": True,  # All pages have visual content
        })

    doc.close()

    # Save sections
    sections_path = os.path.join(KNOWLEDGE_DIR, "sections.json")
    with open(sections_path, "w", encoding="utf-8") as f:
        json.dump(sections, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(sections)} sections to sections.json")

    # Build search index
    index = {}
    keywords_map = {
        "safety": ["Safety"],
        "specifications": ["Specifications"],
        "specs": ["Specifications"],
        "controls": ["Controls - Front Panel", "Controls - Interior"],
        "front panel": ["Controls - Front Panel"],
        "interior": ["Controls - Interior"],
        "lcd": ["Controls - Front Panel"],
        "display": ["Controls - Front Panel"],
        "setup": ["Setup - General", "MIG Welding Setup & Operation", "TIG Welding Setup & Operation", "Stick Welding Setup & Operation"],
        "wire feed": ["Wire Feed Mechanism"],
        "wire": ["Wire Feed Mechanism", "Welding Tips - Wire"],
        "drive roller": ["Wire Feed Mechanism"],
        "tension": ["Wire Feed Mechanism"],
        "polarity": ["Polarity Setup"],
        "dcep": ["Polarity Setup"],
        "dcen": ["Polarity Setup"],
        "electrode positive": ["Polarity Setup"],
        "electrode negative": ["Polarity Setup"],
        "gas": ["Gas Setup"],
        "shielding gas": ["Gas Setup"],
        "argon": ["Gas Setup", "TIG Welding Setup & Operation"],
        "co2": ["Gas Setup"],
        "c25": ["Gas Setup"],
        "mig": ["MIG Welding Setup & Operation", "Polarity Setup", "Duty Cycles", "Welding Tips - Wire"],
        "flux": ["Polarity Setup", "Duty Cycles", "Welding Tips - Wire"],
        "flux-core": ["Polarity Setup", "Duty Cycles", "Welding Tips - Wire"],
        "tig": ["TIG Welding Setup & Operation", "Polarity Setup", "Duty Cycles", "TIG Welding Tips & Settings"],
        "stick": ["Stick Welding Setup & Operation", "Polarity Setup", "Duty Cycles", "Stick Welding Tips & Settings", "Welding Tips - Stick"],
        "duty cycle": ["Duty Cycles"],
        "duty": ["Duty Cycles"],
        "amperage": ["Duty Cycles", "Specifications"],
        "voltage": ["Duty Cycles", "Specifications"],
        "120v": ["Duty Cycles", "Specifications"],
        "240v": ["Duty Cycles", "Specifications"],
        "troubleshoot": ["Troubleshooting"],
        "problem": ["Troubleshooting"],
        "porosity": ["Troubleshooting", "Welding Tips - Wire", "Welding Tips - Stick"],
        "spatter": ["Troubleshooting", "Welding Tips - Wire"],
        "undercut": ["Troubleshooting", "Welding Tips - Wire", "Welding Tips - Stick"],
        "burn through": ["Troubleshooting", "Welding Tips - Wire"],
        "arc": ["Troubleshooting"],
        "wiring": ["Wiring Schematic"],
        "schematic": ["Wiring Schematic"],
        "wiring schematic": ["Wiring Schematic"],
        "parts": ["Parts List"],
        "part number": ["Parts List"],
        "maintenance": ["Maintenance"],
        "clean": ["Maintenance"],
        "warranty": ["Warranty"],
        "weld diagnosis": ["Welding Tips - Wire", "Welding Tips - Stick"],
        "bead": ["Welding Tips - Wire", "Welding Tips - Stick"],
        "settings": ["MIG Welding Setup & Operation", "TIG Welding Tips & Settings", "Stick Welding Tips & Settings"],
        "material thickness": ["Welding Tips - Wire", "TIG Welding Tips & Settings", "Stick Welding Tips & Settings"],
    }

    for keyword, section_names in keywords_map.items():
        matching_pages = []
        for section_def in SECTION_MAP:
            if section_def["section"] in section_names:
                matching_pages.extend(section_def["pages"])
        index[keyword] = sorted(list(set(matching_pages)))

    index_path = os.path.join(KNOWLEDGE_DIR, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print(f"  Saved {len(index)} index entries to index.json")


def extract_with_vision():
    """Use Claude Vision to extract structured content from page images."""
    from anthropic import Anthropic

    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

    client = Anthropic()

    print("\nRunning Claude Vision extraction...")

    vision_sections = []
    tables_data = {}

    for section_def in SECTION_MAP:
        section_name = section_def["section"]
        pages = section_def["pages"]

        # Skip cover and warranty — not critical
        if section_name in ["Cover", "Warranty"]:
            continue

        print(f"  Processing: {section_name} (pages {pages})...")

        # Build image content for this section
        content_parts = [
            {
                "type": "text",
                "text": f"""Analyze this manual page(s) from the Vulcan OmniPro 220 welding system owner's manual.
Section: {section_name}
Pages: {pages}

Extract ALL information in structured format:
1. **Text content**: All readable text, preserving structure and hierarchy
2. **Tables**: Extract as JSON arrays with column headers and row data. Be EXACT with numbers.
3. **Diagrams/Images**: Describe what is shown, including spatial relationships (what connects to what, which socket is where, cable routing)
4. **Warnings/Safety**: Flag any safety warnings or critical notes
5. **Key specifications**: Any numerical specs (amperage, voltage, duty cycle percentages, wire sizes, etc.)

For tables, use this exact format:
```json
{{"table_name": "...", "columns": [...], "rows": [...]}}
```

Be EXTREMELY precise with numbers. A wrong duty cycle or amperage value could be dangerous."""
            }
        ]

        for page_num in pages:
            img_path = os.path.join(PAGES_DIR, f"page-{page_num:02d}.png")
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    img_data = base64.standard_b64encode(f.read()).decode("utf-8")
                content_parts.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_data,
                    }
                })

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": content_parts}]
            )

            extracted = response.content[0].text

            vision_sections.append({
                "section": section_name,
                "processes": section_def["processes"],
                "pages": pages,
                "extracted_content": extracted,
            })

            # Look for tables in the response
            if "```json" in extracted:
                import re
                json_blocks = re.findall(r'```json\s*(.*?)\s*```', extracted, re.DOTALL)
                for block in json_blocks:
                    try:
                        table = json.loads(block)
                        if isinstance(table, dict) and "table_name" in table:
                            tables_data[table["table_name"]] = table
                        elif isinstance(table, list):
                            for item in table:
                                if isinstance(item, dict) and "table_name" in item:
                                    tables_data[item["table_name"]] = item
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            print(f"    ERROR: {e}")
            vision_sections.append({
                "section": section_name,
                "processes": section_def["processes"],
                "pages": pages,
                "extracted_content": f"EXTRACTION FAILED: {str(e)}",
            })

    # Also process selection chart
    print("  Processing: Selection Chart...")
    chart_path = os.path.join(PAGES_DIR, "selection-chart.png")
    if os.path.exists(chart_path):
        with open(chart_path, "rb") as f:
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """This is the welding process selection chart for the Vulcan OmniPro 220.
Extract ALL information as structured data:
- What process to use for what material/thickness
- Any decision flowchart logic
- All numerical values (thickness ranges, amperage recommendations, wire sizes, etc.)
Format tables as JSON."""
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_data,
                            }
                        }
                    ]
                }]
            )

            vision_sections.append({
                "section": "Selection Chart",
                "processes": ["MIG", "Flux-Core", "TIG", "Stick"],
                "pages": ["selection-chart"],
                "extracted_content": response.content[0].text,
            })
        except Exception as e:
            print(f"    ERROR: {e}")

    # Also process quick start guide
    print("  Processing: Quick Start Guide...")
    for i in [1, 2]:
        qs_path = os.path.join(PAGES_DIR, f"quickstart-{i:02d}.png")
        if os.path.exists(qs_path):
            with open(qs_path, "rb") as f:
                img_data = base64.standard_b64encode(f.read()).decode("utf-8")

            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""This is page {i} of the quick start guide for the Vulcan OmniPro 220.
Extract ALL information including setup steps, safety warnings, and any diagrams/labels."""
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_data,
                                }
                            }
                        ]
                    }]
                )

                vision_sections.append({
                    "section": f"Quick Start Guide - Page {i}",
                    "processes": ["MIG", "Flux-Core", "TIG", "Stick"],
                    "pages": [f"quickstart-{i}"],
                    "extracted_content": response.content[0].text,
                })
            except Exception as e:
                print(f"    ERROR: {e}")

    # Save vision-extracted sections
    vision_path = os.path.join(KNOWLEDGE_DIR, "sections_vision.json")
    with open(vision_path, "w", encoding="utf-8") as f:
        json.dump(vision_sections, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved {len(vision_sections)} vision-extracted sections to sections_vision.json")

    # Save extracted tables
    if tables_data:
        tables_path = os.path.join(KNOWLEDGE_DIR, "tables.json")
        with open(tables_path, "w", encoding="utf-8") as f:
            json.dump(tables_data, f, indent=2, ensure_ascii=False)
        print(f"  Saved {len(tables_data)} tables to tables.json")


def main():
    parser = argparse.ArgumentParser(description="Extract knowledge from Vulcan OmniPro 220 manuals")
    parser.add_argument("--vision", action="store_true", help="Run Claude Vision extraction (requires ANTHROPIC_API_KEY)")
    args = parser.parse_args()

    print("=" * 60)
    print("Vulcan OmniPro 220 Knowledge Extraction")
    print("=" * 60)

    # Step 1: Always extract PNGs
    extract_pngs()

    # Step 2: Always extract basic text
    extract_text_basic()

    # Step 3: Optionally run vision extraction
    if args.vision:
        extract_with_vision()
    else:
        print("\nSkipping Vision extraction (use --vision flag to enable)")
        print("Note: Vision extraction costs ~$1-2 in API calls but produces much better results.")

    print("\n" + "=" * 60)
    print("Extraction complete!")
    print(f"  Pages: {PAGES_DIR}")
    print(f"  Sections: {os.path.join(KNOWLEDGE_DIR, 'sections.json')}")
    print(f"  Index: {os.path.join(KNOWLEDGE_DIR, 'index.json')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
