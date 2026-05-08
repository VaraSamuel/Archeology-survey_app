"""
File reference system and catalog generator for ethnographic field notes
Maps notes to reference codes (F1, F2, E3, etc.) organized by category and year
"""

import json
from pathlib import Path
from collections import defaultdict
from backend import EthnographicAnalyzer


class ReferenceSystem:
    """Creates and manages file references for organized notes"""
    
    def __init__(self, index: dict):
        self.index = index
        self.analyzer = EthnographicAnalyzer()
        self.references = defaultdict(list)
        self.reference_map = {}
        
    def generate_references(self) -> dict:
        """
        Generate reference codes for all notes
        Format: {category_prefix}{number}
        Example: F1, F2, F3 for Field Notes, E1, E2 for Economics, etc.
        """
        
        category_prefixes = {
            "economics": "EC",
            "agriculture": "AG",
            "herding": "HD",
            "social": "SO",
            "cultural": "CL",
            "religion": "RL",
            "household": "HH",
            "migration": "MG",
            "burial": "BR",
            "ethnicity": "ET"
        }
        
        counter = defaultdict(int)
        
        # Sort notes by year, then title
        sorted_notes = sorted(
            self.index["notes"],
            key=lambda x: (x["year"], x["title"])
        )
        
        # Generate references
        for note in sorted_notes:
            primary_category = self._get_primary_category(note)
            prefix = category_prefixes.get(primary_category, "FN")
            
            counter[primary_category] += 1
            ref_code = f"{prefix}{counter[primary_category]}"
            
            self.reference_map[note["path"]] = {
                "code": ref_code,
                "category": primary_category,
                "title": note["title"],
                "year": note["year"],
                "tags": note["tags"]
            }
            
            self.references[primary_category].append({
                "code": ref_code,
                "title": note["title"],
                "year": note["year"],
                "tags": note["tags"],
                "path": note["path"]
            })
        
        return self.reference_map
    
    def _get_primary_category(self, note: dict) -> str:
        """Determine primary category for a note based on its tags"""
        if not note["tags"]:
            return "general"
        
        # Count category occurrences
        category_scores = defaultdict(int)
        for tag in note["tags"]:
            category = self.analyzer.get_category_for_tag(tag)
            if category:
                category_scores[category] += 1
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        return "general"
    
    def get_catalog_by_year_and_category(self) -> dict:
        """
        Generate catalog organized by year and category
        Structure: {year: {category: [references]}}
        """
        catalog = defaultdict(lambda: defaultdict(list))
        
        for path, ref_info in self.reference_map.items():
            year = ref_info["year"]
            category = ref_info["category"]
            
            catalog[year][category].append({
                "code": ref_info["code"],
                "title": ref_info["title"],
                "tags": ref_info["tags"]
            })
        
        # Sort by year and category
        sorted_catalog = {}
        for year in sorted(catalog.keys(), key=lambda x: (x != "Unknown", x)):
            sorted_catalog[year] = {}
            for category in sorted(catalog[year].keys()):
                sorted_catalog[year][category] = sorted(
                    catalog[year][category],
                    key=lambda x: x["code"]
                )
        
        return sorted_catalog
    
    def generate_report(self, year: str = None) -> str:
        """Generate human-readable report of references and organization"""
        report = []
        report.append("=" * 80)
        report.append("ETHNOGRAPHIC FIELD NOTES - FILE REFERENCE CATALOG")
        report.append("=" * 80)
        report.append("")
        
        catalog = self.get_catalog_by_year_and_category()
        
        if year:
            years = [year]
        else:
            years = sorted(catalog.keys(), key=lambda x: (x == "Unknown", x))
        
        for y in years:
            if y not in catalog:
                continue
                
            report.append(f"\n{'=' * 80}")
            report.append(f"YEAR: {y}")
            report.append(f"{'=' * 80}\n")
            
            for category in sorted(catalog[y].keys()):
                category_label = self.analyzer.CATEGORIES.get(
                    category, 
                    {}
                ).get("label", category)
                
                report.append(f"\n{category_label}")
                report.append("-" * 40)
                
                for item in catalog[y][category]:
                    report.append(f"  [{item['code']}] {item['title']}")
                    if item['tags']:
                        tags_str = ", ".join(item['tags'][:3])
                        report.append(f"        Tags: {tags_str}")
        
        return "\n".join(report)
    
    def save_references_json(self, output_path: str):
        """Save reference system as JSON"""
        catalog = self.get_catalog_by_year_and_category()
        
        output = {
            "metadata": {
                "total_references": len(self.reference_map),
                "years_covered": list(set(r["year"] for r in self.reference_map.values())),
                "categories": list(self.references.keys())
            },
            "catalog": catalog,
            "reference_map": {
                path: {
                    "code": info["code"],
                    "category": info["category"],
                    "title": info["title"],
                    "year": info["year"]
                }
                for path, info in self.reference_map.items()
            }
        }
        
        Path(output_path).write_text(json.dumps(output, indent=2, ensure_ascii=False))
    
    def get_notes_by_reference_code(self, code: str) -> dict:
        """Look up note details by reference code"""
        for path, ref_info in self.reference_map.items():
            if ref_info["code"] == code:
                return {
                    "code": code,
                    "title": ref_info["title"],
                    "year": ref_info["year"],
                    "category": ref_info["category"],
                    "tags": ref_info["tags"],
                    "path": path
                }
        return None


def main():
    """Demo usage"""
    from backend import NoteService
    
    service = NoteService()
    index = service.load_notes_index()
    
    ref_system = ReferenceSystem(index)
    ref_system.generate_references()
    
    # Generate reports for 1995
    print(ref_system.generate_report(year="1995"))
    
    # Save full catalog
    ref_system.save_references_json("references_catalog.json")
    
    print("\n\nCatalog saved to references_catalog.json")
    print(f"Total references created: {len(ref_system.reference_map)}")


if __name__ == "__main__":
    main()
