"""
Backend for Ethnographic Field Notes Organizer
Handles data analysis, categorization, and year-based analysis
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from organizer import load_index, scan_notes
from collections import defaultdict

load_dotenv()


class EthnographicAnalyzer:
    """Advanced analyzer for ethnographic field notes"""
    
    # Ethnographic categories
    CATEGORIES = {
        "economics": {
            "label": "📊 Economics & Market",
            "patterns": ["tax", "price", "market", "income", "money", "cost", "sell", "buy", "trade", "commerce"]
        },
        "agriculture": {
            "label": "🌾 Agriculture",
            "patterns": ["farm", "farming", "crop", "wheat", "barley", "soil", "tractor", "plow", "planting", "harvest"]
        },
        "herding": {
            "label": "🐑 Herding & Pastoralism",
            "patterns": ["herd", "sheep", "cattle", "goat", "grazing", "shepherd", "flock", "pastur"]
        },
        "social": {
            "label": "👥 Social & Kinship",
            "patterns": ["married", "wife", "husband", "son", "daughter", "visit", "men", "women", "cousin", "family", "brother", "sister"]
        },
        "cultural": {
            "label": "🎭 Cultural Practices",
            "patterns": ["tradition", "custom", "celebration", "festival", "ritual", "ceremony", "dance", "music", "song"]
        },
        "religion": {
            "label": "🕌 Religion & Spirituality",
            "patterns": ["mosque", "church", "prayer", "religion", "islam", "muslim", "christian", "alevi", "holy", "sacred"]
        },
        "household": {
            "label": "🏠 Household & Domestic",
            "patterns": ["cook", "kitchen", "dairy", "cheese", "butter", "milk", "home", "household", "cooking"]
        },
        "migration": {
            "label": "🚶 Migration & Settlement",
            "patterns": ["migrat", "settle", "move", "village", "relocat", "immigrant", "travel"]
        },
        "archaeology": {
            "label": "🪨 Archaeology & Excavation",
            "patterns": ["excavation", "excavate", "trench", "stratigraphy", "context", "layer", "dig", "survey", "site", "artifact", "pottery", "lithic", "ceramic", "bone", "burial", "tomb", "architecture"]
        },
        "artifacts": {
            "label": "🏺 Material Culture & Artifacts",
            "patterns": ["artifact", "artifacts", "pottery", "ceramic", "lithic", "tool", "vessel", "ornament", "bead", "metal", "shard", "bone"]
        },
        "architecture": {
            "label": "🏛️ Settlement & Architecture",
            "patterns": ["building", "wall", "house", "structure", "ruin", "room", "foundation", "mudbrick", "stone", "architecture", "settlement"]
        },
        "landscape": {
            "label": "🗺️ Site & Landscape",
            "patterns": ["landscape", "topography", "hill", "valley", "mound", "survey", "plain", "plateau", "terrace", "site"]
        },
        "burial": {
            "label": "🪦 Burial & Death",
            "patterns": ["burial", "grave", "funeral", "cemeter", "buried", "death", "died"]
        },
        "ethnicity": {
            "label": "🌍 Ethnicity & Identity",
            "patterns": ["ethnic", "ethnicity", "kurd", "turk", "alevi", "y[öo]rük", "roma", "circass", "armen", "arab"]
        }
    }
    
    def __init__(self):
        self.categories_by_tag = self._build_category_index()
    
    def _build_category_index(self) -> dict:
        """Build index mapping tags to categories"""
        index = defaultdict(list)
        for category, info in self.CATEGORIES.items():
            index[category].append(category)
            for tag in info.get("patterns", []):
                index[tag.lower()].append(category)
        return index
    
    def get_category_for_tag(self, tag: str) -> str:
        """Get category for a given tag"""
        tag_lower = tag.lower()
        categories = self.categories_by_tag.get(tag_lower, [])
        if categories:
            return categories[0]

        # Fallback substring match for tags that are not exact pattern keys
        for existing_tag, candidate_categories in self.categories_by_tag.items():
            if existing_tag in tag_lower or tag_lower in existing_tag:
                return candidate_categories[0]

        return None

    def get_all_categories(self) -> dict:
        """Return the category definitions"""
        return self.CATEGORIES

    def get_category_label(self, category: str) -> str:
        """Get display label for a category"""
        if not category:
            return "Unknown"
        return self.CATEGORIES.get(category, {}).get("label", category)

    def analyze_by_year(self, index: dict) -> dict:
        """Analyze notes grouped and categorized by year"""
        analysis = {}
        
        for note in index.get("notes", []):
            year = note["year"]
            if year not in analysis:
                analysis[year] = {
                    "count": 0,
                    "categories": defaultdict(int),
                    "tags": defaultdict(int),
                    "notes": []
                }
            
            analysis[year]["count"] += 1
            analysis[year]["notes"].append(note)
            
            # Count categories and tags
            for tag in note.get("tags", []):
                category = self.get_category_for_tag(tag)
                if category:
                    analysis[year]["categories"][category] += 1
                analysis[year]["tags"][tag] += 1
        
        return analysis
    
    def get_notes_by_year_and_category(self, index: dict, year: str, category: str) -> list:
        """Get all notes for a specific year and category"""
        filtered = []
        for note in index.get("notes", []):
            if note["year"] != year:
                continue
            
            # Check if any tag in the note belongs to this category
            for tag in note.get("tags", []):
                if self.get_category_for_tag(tag) == category:
                    filtered.append(note)
                    break
        
        return filtered
    
    def get_timeline_data(self, index: dict) -> dict:
        """Get data for timeline visualization"""
        analysis = self.analyze_by_year(index)
        timeline = {}
        
        for year in sorted(analysis.keys()):
            if year == "Unknown":
                continue
            timeline[year] = {
                "total_notes": analysis[year]["count"],
                "categories": dict(analysis[year]["categories"]),
                "top_tags": sorted(
                    analysis[year]["tags"].items(),
                    key=lambda x: (-x[1], x[0])
                )[:5]
            }
        
        return timeline
    
    def get_category_statistics(self, index: dict) -> dict:
        """Get statistics for each ethnographic category"""
        stats = {}
        
        for category, info in self.CATEGORIES.items():
            notes_with_category = []
            years_touched = set()
            
            for note in index.get("notes", []):
                for tag in note.get("tags", []):
                    if self.get_category_for_tag(tag) == category:
                        notes_with_category.append(note)
                        years_touched.add(note["year"])
                        break
            
            stats[category] = {
                "label": info["label"],
                "note_count": len(notes_with_category),
                "years_touched": sorted([y for y in years_touched if y != "Unknown"]),
                "year_span": f"{min(years_touched)} - {max(years_touched)}" if years_touched else "N/A"
            }
        
        return stats


class NoteService:
    """Service for managing field notes"""
    
    DEFAULT_ROOT = ".."
    INDEX_FILENAME = "notes_index.json"
    
    def __init__(self, root_path: str = None, index_filename: str = None):
        self.root_path = root_path or self.DEFAULT_ROOT
        self.index_filename = index_filename or self.INDEX_FILENAME
        self.analyzer = EthnographicAnalyzer()
    
    def scan_notes_directory(self, use_openai: bool = False) -> dict:
        """Scan the notes directory and create an index"""
        openai_key = os.getenv("OPENAI_API_KEY") if use_openai else None
        index = scan_notes(
            self.root_path, 
            self.index_filename, 
            openai_key=openai_key, 
            use_openai=use_openai
        )
        return index
    
    def load_notes_index(self) -> dict:
        """Load the existing notes index from file"""
        return load_index(self.index_filename)
    
    def get_all_years(self, index: dict) -> list:
        """Extract and sort all unique years from notes"""
        years = {note["year"] for note in index.get("notes", []) if note["year"] != "Unknown"}
        return sorted(years)
    
    def get_all_tags(self, index: dict) -> list:
        """Extract and sort all unique tags from notes"""
        tags = {tag for note in index.get("notes", []) for tag in note.get("tags", [])}
        return sorted(tags)
    
    def filter_notes(self, index: dict, years: list = None, categories: list = None, tags: list = None) -> list:
        """
        Filter notes by year, categories and/or tags
        """
        year_filter = None
        if years and "All" not in years:
            year_filter = set(years)
        
        filtered = []
        tag_set = set(tags) if tags else None
        category_set = set(categories) if categories else None
        
        for note in index.get("notes", []):
            # Apply year filter
            if year_filter and note["year"] not in year_filter:
                continue
            
            # Apply tag filter (all selected tags must be in note's tags)
            if tag_set and not tag_set.issubset(set(note.get("tags", []))):
                continue
            
            # Apply category filter
            if category_set:
                note_categories = set()
                for tag in note.get("tags", []):
                    cat = self.analyzer.get_category_for_tag(tag)
                    if cat:
                        note_categories.add(cat)
                if not category_set.intersection(note_categories):
                    continue
            
            filtered.append(note)
        
        return filtered
    
    def get_category_label(self, category: str) -> str:
        """Get display label for category"""
        return self.analyzer.CATEGORIES.get(category, {}).get("label", category)
    
    def get_all_categories(self) -> dict:
        """Get all available categories"""
        return self.analyzer.CATEGORIES
