"""
Enhanced tagging module for ethnographic field notes
Improves extraction from .docx files and uses filename patterns
"""

import re
from pathlib import Path


# Enhanced tag patterns with more keywords
ENHANCED_TAG_PATTERNS = {
    "ethnicity": [
        r"ethnic", r"ethnicity", r"kurd", r"turk", r"alevi", r"y[öo]rük", 
        r"roma", r"circass", r"armen", r"arab", r"tatar", r"laz", r"greek"
    ],
    "herding": [
        r"herd", r"shepherd", r"sheep", r"cattle", r"goat", r"grazing", 
        r"flock", r"pastur", r"livestock", r"animal", r"dairy", r"nomad"
    ],
    "agriculture": [
        r"farm", r"farming", r"crop", r"wheat", r"barley", r"soil", r"tractor", 
        r"plow", r"planting", r"harvest", r"vegetable", r"garden", r"soil",
        r"field", r"irrigation", r"seed", r"agr"
    ],
    "household": [
        r"cook", r"kitchen", r"dairy", r"cheese", r"butter", r"milk", 
        r"home", r"household", r"family", r"domestic", r"meal", r"food"
    ],
    "migration": [
        r"migrat", r"settle", r"move", r"village", r"relocat", r"immigrant",
        r"travel", r"nomadic", r"seasonal", r"movement"
    ],
    "social": [
        r"married", r"wife", r"husband", r"son", r"daughter", r"visit", 
        r"wife", r"men", r"women", r"cousin", r"relative", r"brother", 
        r"sister", r"family", r"kinship", r"social"
    ],
    "burial": [
        r"burial", r"grave", r"funeral", r"cemeter", r"buried", r"death", 
        r"died", r"tomb", r"mourning"
    ],
    "religion": [
        r"mosque", r"church", r"prayer", r"religion", r"islam", r"muslim", 
        r"christian", r"alevi", r"holy", r"sacred", r"faith", r"spiritual",
        r"ritual", r"ceremony"
    ],
    "economy": [
        r"tax", r"price", r"market", r"income", r"money", r"cost", r"sell", 
        r"buy", r"trade", r"commerce", r"economic", r"business", r"commerce"
    ],
    "cultural": [
        r"tradition", r"custom", r"celebration", r"festival", r"ritual", 
        r"ceremony", r"dance", r"music", r"song", r"art", r"craft", r"cultural"
    ],
}

# Filename-based tag inference
FILENAME_PATTERNS = {
    "herding": r"herd",
    "agriculture": r"farm|agr|crop",
    "burial": r"burial|cemetery|grave|death",
    "social": r"visit|talk|conversation|convo",
    "economy": r"tax|market|price",
    "household": r"kitchen|cook|dairy|cheese",
    "migration": r"migrat|settle|move",
    "archaeology": r"excavation|dig|trench|site|survey|stratigraphy|context|layer",
    "artifacts": r"artifact|pottery|ceramic|lithic|tool|vessel|shard",
    "architecture": r"building|wall|structure|ruin|house|foundation|mudbrick|settlement",
    "landscape": r"site|hill|valley|mound|terrace|plain|topography",
}


def extract_tags_from_filename(filename: str) -> set[str]:
    """Extract tags from filename patterns"""
    tags = set()
    filename_lower = filename.lower()
    
    for tag, pattern in FILENAME_PATTERNS.items():
        if re.search(pattern, filename_lower):
            tags.add(tag)
    
    return tags


def extract_tags_from_path(filepath: Path) -> set[str]:
    """Extract tags from folder and path segments"""
    tags = set()
    path_segments = [segment.lower() for segment in filepath.parts if segment]
    for segment in path_segments:
        for tag, pattern in FILENAME_PATTERNS.items():
            if re.search(pattern, segment):
                tags.add(tag)
    return tags


def extract_enhanced_tags(text: str) -> set[str]:
    """Extract tags using enhanced keyword matching"""
    tags = set()
    text_lower = text.lower()
    
    # Extract up to first 5000 chars for efficiency
    text_sample = text_lower[:5000]
    
    for tag_category, patterns in ENHANCED_TAG_PATTERNS.items():
        for pattern in patterns:
            # Use word boundary matching where appropriate
            if len(pattern) > 3:
                search_pattern = r"\b" + pattern + r"\b"
            else:
                search_pattern = pattern
            
            if re.search(search_pattern, text_sample, re.IGNORECASE):
                tags.add(tag_category)
                break
    
    return tags


def get_tags_for_note(filename: str, text: str, filepath: Path | str | None = None) -> set[str]:
    """
    Combine filename, folder path, and text-based tagging.
    Returns comprehensive set of tags.
    """
    tags = set()
    tags.update(extract_tags_from_filename(filename))

    if filepath is not None:
        tags.update(extract_tags_from_path(Path(filepath)))

    if text and len(text.strip()) > 50:
        text_tags = extract_enhanced_tags(text)
        tags.update(text_tags)
    else:
        if not tags:
            filename_tags = extract_tags_from_filename(filename)
            tags.update(filename_tags)

    return tags


def analyze_file_content(filepath: str, text: str) -> dict:
    """
    Comprehensive analysis of a note file
    Returns dict with tags, content quality, extracted summary
    """
    filename = Path(filepath).name
    
    # Get tags
    tags = get_tags_for_note(filename, text)
    
    # Assess content quality
    text = text.strip()
    content_quality = "empty" if not text else (
        "minimal" if len(text) < 100 else
        "small" if len(text) < 500 else
        "medium" if len(text) < 2000 else
        "substantial"
    )
    
    # Extract first meaningful sentence
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', text) if len(s.strip()) > 10]
    summary = sentences[0] if sentences else ""
    if len(summary) > 150:
        summary = summary[:150] + "..."
    
    return {
        "tags": sorted(tags),
        "content_quality": content_quality,
        "content_length": len(text),
        "summary": summary,
    }


if __name__ == "__main__":
    # Test
    test_filename = "1995.07.04_Herding notes.txt"
    test_text = "Talked with shepherds about grazing practices and seasonal migration patterns in the highlands."
    
    result = analyze_file_content(test_filename, test_text)
    print(f"Filename: {test_filename}")
    print(f"Tags: {result['tags']}")
    print(f"Quality: {result['content_quality']}")
    print(f"Summary: {result['summary']}")
