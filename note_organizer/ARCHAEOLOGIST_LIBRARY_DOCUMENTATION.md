# Archaeologist Field Notes Library Documentation

## Purpose
This project is a **library-style organizer** for archaeological field notes across multiple years. It is built to read your existing folder structure of year folders and subfolders, categorize notes by archaeological topics, and present them in a simple year → category → file workflow.

## What it does
- Scans the folder structure under `..` relative to `note_organizer/`
- Extracts text from `.txt`, `.docx`, and `.doc` notes
- Detects if `.txt` files are corrupted and skips unreadable text files safely
- Builds a searchable index (`notes_index.json`) automatically when needed
- Supports filtering by:
  - Year
  - Archaeological category
- Displays matching note files with title, year, source, categories, tags, excerpt, and file path

## Why this is useful for an archaeologist
The tool is designed as a **research library** from the entire field archive:
- Years become the first filter
- Archaeological categories become the second filter
- Results are the notes related to that year/category combination
- No manual upload is required once the folder library exists

## Current UI behavior
When the app starts, it will:
1. Try to load `notes_index.json`
2. If the index is missing, automatically scan the folder tree under `..`
3. Populate the year dropdown from discovered notes
4. Populate the category dropdown from notes in the selected year
5. Show only matching notes after both selections

## Architectural files
- `app.py` — Streamlit user interface
- `organizer.py` — scanning and text extraction logic
- `backend.py` — category mapping and note filtering logic
- `enhanced_tagger.py` — improved tag extraction for archaeology-related content
- `notes_index.json` — generated index of scanned notes
- `references_catalog.json` — optional catalog of generated reference codes (if created previously)

## Archaeological categories included
The organizer now recognizes these categories:
- Archaeology & Excavation
- Material Culture & Artifacts
- Settlement & Architecture
- Site & Landscape
- Economics & Market
- Agriculture
- Herding & Pastoralism
- Social & Kinship
- Cultural Practices
- Religion & Spirituality
- Household & Domestic
- Migration & Settlement
- Burial & Death
- Ethnicity & Identity

## How the folder structure is used
The app uses your year folders and nested files as the source library.
Example structure:

```
1995/
  1995.07.04_Pembo Kayran.txt
  1995.07.14_Burials.txt
  ...
1998/
  1998.07.07_land use.txt
  1998/corrupted/AS2 copy.txt
  ...
```

No additional upload step is required. The folder structure itself is the library.

## How to run
From the `note_organizer/` folder:

```bash
streamlit run app.py
```

If the index does not exist, the app will build it automatically.

## What has been changed so far
- Added **archaeology-first UI flow**: year selection first, then category selection
- Added **off-white, minimalist style** for easier reading
- Added **auto-scan fallback** when `notes_index.json` is missing
- Added **archaeology-specific tag patterns** for excavation, artifact, site, stratigraphy, and related content
- Added safe **corrupted `.txt` detection** so binary files do not break the scan

## Notes for future improvement
- Add a dedicated **site/excavation area** filter from filenames or content
- Improve `.doc` extraction for older Word notes
- Add **reference code display** for archaeologist indexing and citation
- Add an export of selected results to a CSV or spreadsheet

## Important note
The tool is intended as a research library built from your existing folders. If you want to inspect the current index manually, open `notes_index.json` after the first scan.
