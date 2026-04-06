"""
Knowledge base query functions for the Vulcan OmniPro 220.
Loads pre-extracted manual content and provides structured search.
"""

import json
import os
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

# Load knowledge base at module level
_sections = []
_tables = {}
_index = {}
_vision_sections = []


def _load():
    global _sections, _tables, _index, _vision_sections

    sections_path = KNOWLEDGE_DIR / "sections.json"
    if sections_path.exists():
        with open(sections_path, "r", encoding="utf-8") as f:
            _sections = json.load(f)

    tables_path = KNOWLEDGE_DIR / "tables.json"
    if tables_path.exists():
        with open(tables_path, "r", encoding="utf-8") as f:
            _tables = json.load(f)

    index_path = KNOWLEDGE_DIR / "index.json"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            _index = json.load(f)

    vision_path = KNOWLEDGE_DIR / "sections_vision.json"
    if vision_path.exists():
        with open(vision_path, "r", encoding="utf-8") as f:
            _vision_sections = json.load(f)


_load()


def search_manual(query: str, process_filter: str | None = None) -> list[dict]:
    """Search the manual knowledge base by keyword/topic."""
    query_lower = query.lower()
    results = []
    matched_sections = set()

    # First, check index for keyword matches
    for keyword, pages in _index.items():
        if keyword in query_lower or query_lower in keyword:
            for section in _sections:
                if section["section"] in matched_sections:
                    continue
                if any(p in pages for p in section["pages"]):
                    if process_filter and process_filter not in section.get("processes", []):
                        continue
                    matched_sections.add(section["section"])
                    # Prefer vision-extracted content if available
                    content = section["content"]
                    for vs in _vision_sections:
                        if vs["section"] == section["section"]:
                            content = vs.get("extracted_content", content)
                            break
                    results.append({
                        "section": section["section"],
                        "pages": section["pages"],
                        "processes": section.get("processes", []),
                        "content": content[:3000],  # Limit to avoid huge context
                    })

    # If no index hits, do full-text search across sections
    if not results:
        for section in _sections:
            if section["section"] in matched_sections:
                continue
            if process_filter and process_filter not in section.get("processes", []):
                continue
            if query_lower in section.get("content", "").lower():
                matched_sections.add(section["section"])
                content = section["content"]
                for vs in _vision_sections:
                    if vs["section"] == section["section"]:
                        content = vs.get("extracted_content", content)
                        break
                results.append({
                    "section": section["section"],
                    "pages": section["pages"],
                    "processes": section.get("processes", []),
                    "content": content[:3000],
                })

    return results[:5]  # Max 5 results


def get_manual_page(page_number: int) -> dict:
    """Get content and image path for a specific manual page."""
    if page_number < 1 or page_number > 48:
        return {"error": f"Page number must be between 1 and 48, got {page_number}"}

    page_image = f"page-{page_number:02d}.png"
    image_path = KNOWLEDGE_DIR / "pages" / page_image

    # Find section for this page
    section_name = "Unknown"
    content = ""
    for section in _sections:
        if page_number in section["pages"]:
            section_name = section["section"]
            content = section["content"]
            # Check for vision-extracted content
            for vs in _vision_sections:
                if vs["section"] == section_name:
                    content = vs.get("extracted_content", content)
                    break
            break

    return {
        "page_number": page_number,
        "section": section_name,
        "content": content[:4000],
        "image_path": f"/api/pages/{page_image}" if image_path.exists() else None,
    }


def get_duty_cycle(process: str, voltage: str, amperage: int | None = None) -> dict:
    """Look up duty cycle for a specific process/voltage/amperage."""
    duty_data = _tables.get("duty_cycles", {})

    # Normalize inputs
    process_map = {
        "mig": "MIG", "flux-core": "MIG", "flux": "MIG",  # MIG and Flux-Core share table
        "tig": "TIG",
        "stick": "Stick",
    }
    process_key = process_map.get(process.lower(), process)

    voltage_map = {"120v": "120VAC", "240v": "240VAC", "120": "120VAC", "240": "240VAC"}
    voltage_key = voltage_map.get(voltage.lower().replace("vac", "v"), voltage)

    process_data = duty_data.get(process_key, {})
    voltage_data = process_data.get(voltage_key, {})

    if not voltage_data:
        return {
            "error": f"No duty cycle data found for {process} at {voltage}",
            "available_processes": list(duty_data.keys()),
            "source_page": 29,
        }

    result = {
        "process": process_key,
        "voltage": voltage_key,
        "rated": voltage_data.get("rated", "N/A"),
        "source_page": 29,
        "all_ratings": {},
    }

    # Include all amperage ratings for this process/voltage
    for key, val in voltage_data.items():
        if key == "rated":
            continue
        if isinstance(val, dict) and "duty_cycle_percent" in val:
            result["all_ratings"][key] = val

    # If specific amperage requested, find closest match or interpolate
    if amperage is not None:
        exact_key = f"{amperage}A"
        if exact_key in voltage_data:
            match = voltage_data[exact_key]
            result["requested_amperage"] = amperage
            result["duty_cycle_percent"] = match["duty_cycle_percent"]
            result["weld_minutes"] = match["weld_minutes"]
            result["cool_minutes"] = match["cool_minutes"]
        else:
            result["requested_amperage"] = amperage
            result["note"] = f"Exact duty cycle for {amperage}A not in table. Refer to rated values."

    # Also include specs data
    specs = _tables.get("specifications", {}).get(process_key, {})
    if specs:
        vkey = "120v" if "120" in voltage_key else "240v"
        result["welding_current_range"] = specs.get(f"welding_current_range_{vkey}", "N/A")
        result["max_current"] = specs.get(f"welding_current_range_{vkey}", "N/A").split("-")[-1] if specs.get(f"welding_current_range_{vkey}") else "N/A"

    return result


def get_troubleshooting(symptom: str) -> list[dict]:
    """Look up troubleshooting entries for a symptom."""
    troubleshooting = _tables.get("troubleshooting", {})
    entries = troubleshooting.get("entries", [])
    symptom_lower = symptom.lower()

    results = []
    for entry in entries:
        # Check problem name, causes, and solutions for matches
        searchable = (
            entry["problem"].lower()
            + " ".join(entry.get("possible_causes", [])).lower()
            + " ".join(entry.get("solutions", [])).lower()
        )
        if symptom_lower in searchable or any(word in searchable for word in symptom_lower.split()):
            results.append({
                "problem": entry["problem"],
                "possible_causes": entry.get("possible_causes", []),
                "solutions": entry.get("solutions", []),
                "source_pages": troubleshooting.get("source_pages", [42, 43, 44]),
            })

    return results


def get_polarity(process: str) -> dict:
    """Get polarity setup for a specific welding process."""
    polarity_data = _tables.get("polarity", {})
    process_map = {
        "mig": "MIG", "flux-core": "Flux-Core", "flux": "Flux-Core",
        "tig": "TIG", "stick": "Stick",
    }
    process_key = process_map.get(process.lower(), process)
    data = polarity_data.get(process_key, {})

    if not data:
        return {"error": f"No polarity data for {process}", "source_pages": [14, 15, 16]}

    return {
        "process": process_key,
        **data,
        "source_pages": polarity_data.get("source_pages", [14, 15, 16]),
    }


def get_specifications(process: str | None = None) -> dict:
    """Get specifications for a process or all processes."""
    specs = _tables.get("specifications", {})
    if process:
        process_map = {"mig": "MIG", "tig": "TIG", "stick": "Stick"}
        process_key = process_map.get(process.lower(), process)
        return specs.get(process_key, {"error": f"No specs for {process}"})
    return specs


def get_selection_chart() -> dict:
    """Get the welding process selection chart data."""
    return _tables.get("selection_chart", {})


def get_all_tables() -> dict:
    """Get all structured table data."""
    return _tables
