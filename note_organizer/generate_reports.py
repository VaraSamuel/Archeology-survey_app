"""
Generate organized reports matching the handwritten reference system
Creates printable catalogs for ethnographic note organization
"""

import json
from pathlib import Path
from collections import defaultdict


def generate_filing_system_report(references_json_path: str = "references_catalog.json") -> str:
    """
    Generate a report that matches the handwritten note format:
    - Organized by year
    - Shows categorization
    - Displays file reference codes (F1, F2, etc.)
    """
    
    with open(references_json_path) as f:
        catalog = json.load(f)
    
    report = []
    report.append("╔" + "═" * 78 + "╗")
    report.append("║" + " " * 78 + "║")
    report.append("║" + "ETHNOGRAPHIC FIELD NOTES - FILING REFERENCE SYSTEM".center(78) + "║")
    report.append("║" + "(1995 → 2024) Individual File Index with Categorization".center(78) + "║")
    report.append("║" + " " * 78 + "║")
    report.append("╚" + "═" * 78 + "╝")
    report.append("")
    
    catalog_data = catalog.get("catalog", {})
    
    # Summary statistics
    total_refs = catalog["metadata"]["total_references"]
    total_years = len(catalog["metadata"]["years_covered"])
    total_categories = len(catalog["metadata"]["categories"])
    
    report.append(f"SUMMARY")
    report.append(f"  Total Files: {total_refs}")
    report.append(f"  Years Covered: {total_years} ({min(catalog['metadata']['years_covered'])} - {max(catalog['metadata']['years_covered'])})")
    report.append(f"  Main Categories: {total_categories}")
    report.append("")
    
    # By year detailed breakdown
    report.append("=" * 80)
    report.append("DETAILED FILE LISTING BY YEAR")
    report.append("=" * 80)
    
    for year in sorted(catalog_data.keys(), key=lambda x: (x == "Unknown", x)):
        year_data = catalog_data[year]
        
        # Skip if no data
        if not year_data:
            continue
        
        report.append("")
        report.append(f"├─ {year}")
        
        categories_in_year = sorted(year_data.keys())
        for idx, category in enumerate(categories_in_year):
            is_last_cat = (idx == len(categories_in_year) - 1)
            cat_prefix = "└─ " if is_last_cat else "├─ "
            
            files_in_cat = year_data[category]
            cat_label = _get_category_label(category)
            
            report.append(f"{cat_prefix}{cat_label}")
            
            # Show files with reference codes
            for file_idx, file_item in enumerate(files_in_cat):
                is_last_file = (file_idx == len(files_in_cat) - 1)
                
                if is_last_cat:
                    file_prefix = "    " + ("└─" if is_last_file else "├─")
                else:
                    file_prefix = "│   " + ("└─" if is_last_file else "├─")
                
                ref_code = file_item["code"]
                title = file_item["title"]
                
                # Format: [REF] Title
                report.append(f"{file_prefix} [{ref_code}] {title}")
                
                # Show tags if present
                if file_item.get("tags"):
                    tag_str = ", ".join(file_item["tags"])
                    if is_last_cat:
                        tags_prefix = "    " + ("   " if is_last_file else "│  ")
                    else:
                        tags_prefix = "│   " + ("   " if is_last_file else "│  ")
                    report.append(f"{tags_prefix} Tags: {tag_str}")
    
    return "\n".join(report)


def generate_quick_reference_table(references_json_path: str = "references_catalog.json") -> str:
    """Generate a quick lookup table by reference code"""
    
    with open(references_json_path) as f:
        catalog = json.load(f)
    
    report = []
    report.append("QUICK REFERENCE LOOKUP TABLE")
    report.append("=" * 120)
    report.append(f"{'CODE':<8} {'YEAR':<8} {'FILE':<70} {'CATEGORY':<20}")
    report.append("-" * 120)
    
    ref_map = catalog.get("reference_map", {})
    
    # Sort by code
    sorted_refs = sorted(
        ref_map.items(),
        key=lambda x: (_code_sort_key(x[1]["code"]))
    )
    
    for path, info in sorted_refs[:100]:  # Show first 100
        code = info["code"]
        year = info["year"]
        title = info["title"][:70]
        category = info["category"]
        
        report.append(f"{code:<8} {year:<8} {title:<70} {category:<20}")
    
    if len(sorted_refs) > 100:
        report.append(f"... and {len(sorted_refs) - 100} more entries")
    
    report.append("=" * 120)
    return "\n".join(report)


def generate_statistics_report(references_json_path: str = "references_catalog.json") -> str:
    """Generate statistics on the note collection"""
    
    with open(references_json_path) as f:
        catalog = json.load(f)
    
    report = []
    report.append("\nCOLLECTION STATISTICS")
    report.append("=" * 60)
    
    # Count by category
    category_counts = defaultdict(int)
    year_counts = defaultdict(int)
    tag_counts = defaultdict(int)
    
    catalog_data = catalog.get("catalog", {})
    
    for year, year_data in catalog_data.items():
        year_counts[year] = sum(len(files) for files in year_data.values())
        
        for category, files in year_data.items():
            category_counts[category] += len(files)
            
            for file_item in files:
                for tag in file_item.get("tags", []):
                    tag_counts[tag] += 1
    
    report.append("\nNotes by Category:")
    for cat in sorted(category_counts.keys(), key=lambda x: -category_counts[x])[:15]:
        count = category_counts[cat]
        pct = 100 * count / catalog["metadata"]["total_references"]
        label = _get_category_label(cat)
        report.append(f"  {label:<30} {count:>4} ({pct:>5.1f}%)")
    
    report.append("\nNotes by Decade:")
    for year in sorted(year_counts.keys()):
        if year != "Unknown":
            count = year_counts[year]
            pct = 100 * count / catalog["metadata"]["total_references"]
            report.append(f"  {year}: {count:>4} ({pct:>5.1f}%)")
    
    report.append("\nTop Tags:")
    for tag in sorted(tag_counts.keys(), key=lambda x: -tag_counts[x])[:10]:
        count = tag_counts[tag]
        pct = 100 * count / catalog["metadata"]["total_references"]
        report.append(f"  {tag:<20} {count:>4} ({pct:>5.1f}%)")
    
    return "\n".join(report)


def _get_category_label(category: str) -> str:
    """Get display label for category"""
    labels = {
        "economics": "📊 Economics & Market",
        "agriculture": "🌾 Agriculture",
        "herding": "🐑 Herding & Pastoralism",
        "social": "👥 Social & Kinship",
        "cultural": "🎭 Cultural Practices",
        "religion": "🕌 Religion & Spirituality",
        "household": "🏠 Household & Domestic",
        "migration": "🚶 Migration & Settlement",
        "burial": "🪦 Burial & Death",
        "ethnicity": "🌍 Ethnicity & Identity",
        "general": "📋 General / Field Notes",
    }
    return labels.get(category, category)


def _code_sort_key(code: str) -> tuple:
    """Sort codes properly (EC1, EC2, ..., AG1, AG2, ...)"""
    # Extract prefix and number
    match = __import__('re').match(r'([A-Z]+)(\d+)', code)
    if match:
        prefix, num = match.groups()
        return (prefix, int(num))
    return (code, 0)


if __name__ == "__main__":
    # Generate all reports
    print(generate_filing_system_report())
    print("\n\n")
    print(generate_statistics_report())
    
    # Save to file
    with open("FILING_SYSTEM_1995.txt", "w") as f:
        f.write(generate_filing_system_report())
    
    print("\n✓ Report saved to FILING_SYSTEM_1995.txt")
