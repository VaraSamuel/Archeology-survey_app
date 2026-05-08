# Ethnographic Field Notes Organizer - Architecture

## Overview

A sophisticated Streamlit-based application for organizing and analyzing ethnographic field notes by year and ethnographic categories (Economics, Social, Cultural, Religion, etc.).

## Project Structure

```
note_organizer/
├── organizer.py        # Core library (file parsing, tagging)
├── backend.py          # Business logic & ethnographic analysis
├── frontend.py         # Streamlit UI with 4 tabs
└── README.md          # Usage guide
```

## Components

### 1. **organizer.py** (Core Library)
- Reads `.txt`, `.docx`, `.doc` files
- Extracts text and normalizes formatting
- Infers year from file path/name
- Generates keyword tags using regex patterns
- Optional NLP tagging (spaCy)
- Optional AI tagging (OpenAI)

### 2. **backend.py** (Business Logic)

#### Classes:

**EthnographicAnalyzer**
- Manages 10 ethnographic categories:
  - 📊 Economics & Market
  - 🌾 Agriculture
  - 🐑 Herding & Pastoralism
  - 👥 Social & Kinship
  - 🎭 Cultural Practices
  - 🕌 Religion & Spirituality
  - 🏠 Household & Domestic
  - 🚶 Migration & Settlement
  - 🪦 Burial & Death
  - 🌍 Ethnicity & Identity

- Key methods:
  - `get_category_for_tag()` - Maps tags to categories
  - `analyze_by_year()` - Groups notes by year with category counts
  - `get_notes_by_year_and_category()` - Filters by year + category
  - `get_timeline_data()` - Data for visualizations
  - `get_category_statistics()` - Stats per category

**NoteService**
- Service layer for frontend usage
- Key methods:
  - `scan_notes_directory()` - Scan and index all notes
  - `load_notes_index()` - Load existing index
  - `filter_notes()` - Filter by years/categories/tags
  - `get_all_years()`, `get_all_tags()` - Extract metadata
  - `get_category_label()` - Get display names

### 3. **frontend.py** (Streamlit UI)

#### 4 Main Tabs:

**Tab 1: 📊 By Year**
- Browse notes organized chronologically
- Year-level statistics and category breakdown
- Expandable sections for each note
- Tags organized by ethnographic category

**Tab 2: 🏷️ By Category**
- Browse by ethnographic dimension
- Statistics: total notes, years covered, time span
- Notes grouped by year within each category
- Filter by specific categories

**Tab 3: 📈 Timeline Analysis**
- Overall research statistics
- Bar chart: notes per year
- Line chart: category evolution over time
- Year-by-year breakdowns

**Tab 4: 📋 All Notes**
- Advanced filtering by year + category + tag
- Display filtered results with metadata
- Tags organized by category

## Data Flow

```
Field Notes
    ↓
organizer.py (scan_notes)
    ├─ Extract text
    ├─ Extract year metadata
    ├─ Generate tags (keyword + NLP + AI)
    └─ Output: notes_index.json
    ↓
backend.py (NoteService)
    ├─ Load index
    ├─ EthnographicAnalyzer: map tags → categories
    ├─ Filter & analyze
    └─ Return structured data
    ↓
frontend.py (Streamlit)
    └─ Display in 4 organized tabs
```

## Installation & Setup

```bash
cd /Users/samuelvara/Downloads/Field_Notes_Ethnography/note_organizer

# Install dependencies
pip install -r requirements.txt
python3 -m spacy download en_core_web_sm

# Optional: Add OPENAI_API_KEY to .env
echo "OPENAI_API_KEY=your_key_here" >> .env
```

## Running the Application

### Main Command (Recommended)
```bash
streamlit run /Users/samuelvara/Downloads/Field_Notes_Ethnography/note_organizer/frontend.py
```

### Quick Test Backend
```bash
cd /Users/samuelvara/Downloads/Field_Notes_Ethnography/note_organizer
python3 -c "from backend import NoteService; s = NoteService(); print(s.load_notes_index())"
```

### From Any Directory
```bash
# Run frontend
streamlit run /Users/samuelvara/Downloads/Field_Notes_Ethnography/note_organizer/frontend.py

# Or set alias for convenience
alias ethnography="cd /Users/samuelvara/Downloads/Field_Notes_Ethnography/note_organizer && streamlit run frontend.py"
ethnography
```

## Browser Access

Once running, open: **http://localhost:8501**

## Database Structure

### notes_index.json
```json
{
  "root": "/path/to/field/notes",
  "note_count": 150,
  "notes": [
    {
      "title": "1995.07.04_Pembo Kayran.txt",
      "path": "/path/to/1995.07.04_Pembo Kayran.txt",
      "year": "1995",
      "tags": ["social", "kinship", "migration"],
      "excerpt": "First 240 chars of content...",
      "source": "txt"
    },
    ...
  ]
}
```

## Ethnographic Categories - Tag Mapping

Each note's tags are automatically mapped to categories:

| Category | Sample Tags | Patterns |
|----------|------------|----------|
| **Economics** | market, price, cost, income | tax, trade, commerce |
| **Agriculture** | farm, crop, harvest, soil | wheat, barley, plow |
| **Herding** | herd, sheep, pasture, grazing | cattle, shepherd, flock |
| **Social** | wife, husband, cousin, family | married, son, daughter |
| **Cultural** | tradition, ritual, ceremony | celebration, festival, dance |
| **Religion** | mosque, prayer, islam, muslim | church, alevi, sacred |
| **Household** | kitchen, dairy, cheese, butter | cook, milk, home |
| **Migration** | migrate, settle, village | relocate, immigrant, travel |
| **Burial** | funeral, cemetery, grave | burial, death, buried |
| **Ethnicity** | kurds, turks, alevi, roma | circassian, armenian, arab |

## Workflow Example

1. **Scan Notes**
   - Click "🔍 Scan Notes" in sidebar
   - Choose root folder (e.g., `..` for parent directory)
   - Optional: Enable OpenAI for richer categorization
   - System indexes all `.txt` and `.docx` files

2. **Browse by Year**
   - Tab 1: See notes organized 1995 → 2024
   - Expand any year to see category breakdown
   - Click note titles to view full details

3. **Analyze by Category**
   - Tab 2: Select "📊 Economics" to see all economic data
   - View which years have economic content
   - See trends in household, herding, agriculture

4. **Timeline Analysis**
   - Tab 3: Visualize research evolution
   - See when focus shifted between categories
   - Identify data collection patterns

5. **Advanced Filtering**
   - Tab 4: Combine year + category + tag filters
   - Export specific research subsets

## Performance Notes

- **First scan**: ~10-30 seconds (scanning all files)
- **Subsequent loads**: ~1-2 seconds (cached index)
- **Large datasets**: 500+ notes handled efficiently
- **Visualizations**: Real-time with Streamlit caching

## Customization

### Add New Categories
Edit `backend.py` - `CATEGORIES` dict in `EthnographicAnalyzer`:
```python
"new_category": {
    "label": "🔴 Display Name",
    "patterns": ["keyword1", "keyword2", ...]
}
```

### Modify Tag Detection
Edit `organizer.py` - `TAG_PATTERNS` dict:
```python
TAG_PATTERNS = {
    "category": ["pattern1", "pattern2", ...],
    ...
}
```

### Change UI Layout
Edit `frontend.py` - modify Streamlit components in each tab

## Dependencies

- **streamlit** - Web UI framework
- **python-docx** - .docx parsing
- **python-dotenv** - Environment variables
- **spacy** - NLP tagging (optional)
- **openai** - AI categorization (optional)

See `requirements.txt` for exact versions.

## Troubleshooting

**No notes appear after scan:**
- Check root folder path is correct
- Verify files end in `.txt` or `.docx`
- Check `notes_index.json` exists in project root

**Categories not showing:**
- Ensure tags match patterns in `TAG_PATTERNS`
- Try enabling OpenAI for better detection
- Check `backend.py` category definitions

**Slow performance:**
- For 500+ files, first scan takes time
- Subsequent loads are cached
- Consider filtering by year range

## Future Enhancements

- [ ] Export to PDF reports
- [ ] Custom category creation via UI
- [ ] Full-text search
- [ ] Network analysis (connections between notes)
- [ ] Multi-language support
- [ ] Collaboration features
