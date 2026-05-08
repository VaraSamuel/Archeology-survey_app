# 🏺 Archaeological Field Notes Organizer

A FastAPI web application for organizing, categorizing, and browsing archaeological ethnographic field notes. Features year/category filtering, full-text search, and batch downloads.

## Features

- 📅 **Browse by Year**: Filter notes across 30+ years of research
- 🏷️ **Organize by Category**: 14+ archaeological categories (herding, agriculture, burial, artifacts, etc.)
- 🔍 **Full-Text Search**: Search across titles, content, and tags
- 📥 **Download**: Export notes as ZIP files by year or category
- 🎨 **Clean UI**: Modern, responsive interface optimized for archaeologists
- 📊 **Statistics**: View distribution and coverage of notes

## Technology Stack

- **Backend**: FastAPI + Python
- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript
- **Data**: Local file system with JSON index
- **Deployment**: Railway ready

## Project Structure

```
.
├── note_organizer/
│   ├── web_app.py              # FastAPI web app (main entry)
│   ├── backend.py              # Core logic & category definitions
│   ├── organizer.py            # File scanning & indexing
│   ├── enhanced_tagger.py      # Tag extraction from notes
│   ├── notes_index.json        # Generated index of all notes
│   └── requirements.txt        # Python dependencies
├── 1995/, 1996/, ..., 2024/    # Year-organized field notes
├── Undated_Notes/              # Notes without year info
├── Procfile                    # Railway deployment config
├── runtime.txt                 # Python version
└── railway.toml                # Railway configuration
```

## Installation & Local Usage

### 1. Clone Repository
```bash
git clone https://github.com/VaraSamuel/Archeology-survey_app.git
cd Archeology-survey_app
```

### 2. Install Dependencies
```bash
pip install -r note_organizer/requirements.txt
```

### 3. Run Locally
```bash
cd note_organizer
python web_app.py
```

App will be available at `http://localhost:8000`

## Deployment to Railway

### Step 1: Connect Repository to Railway

1. Go to https://railway.app
2. Click **+ New Project**
3. Select **Deploy from GitHub**
4. Authorize and select this repository: `VaraSamuel/Archeology-survey_app`

### Step 2: Configure Environment (if needed)

In Railway dashboard:
- Go to **Variables** tab
- Add environment variables (if using OpenAI):
  ```
  OPENAI_API_KEY=your_key_here
  ```
- These are optional; app works fine without them

### Step 3: Deploy

Railway automatically detects the `Procfile` and deploys.

**Deployment will:**
1. Install Python 3.10
2. Install dependencies from `requirements.txt`
3. Start FastAPI server on Railway's auto-assigned port
4. Make app available on `https://your-app-name.railway.app`

### Step 4: Monitor Deployment

- Check **Deployments** tab for status
- View logs in **Logs** tab
- If build fails, check logs for missing dependencies

## Environment Variables (Optional)

Create `.env` file in root (won't be uploaded to Git):

```
OPENAI_API_KEY=sk-...
```

## API Endpoints

- `GET /` - Main HTML interface
- `GET /api/years` - List all available years
- `GET /api/categories` - List all category definitions
- `GET /api/stats` - Library statistics
- `GET /api/notes?year=1995&category=herding&search=query` - Filter notes
- `GET /api/download/year/{year}` - Download year as ZIP
- `GET /api/download/category/{category}` - Download category as ZIP

## Categories

The app includes 14 archaeology-focused categories:

- 📊 Economics & Market
- 🌾 Agriculture
- 🐑 Herding & Pastoralism
- 👥 Social & Kinship
- 🎭 Cultural Practices
- 🕌 Religion & Spirituality
- 🏠 Household & Domestic
- 🚶 Migration & Settlement
- 🪨 Archaeology & Excavation
- 🏺 Material Culture & Artifacts
- 🏛️ Settlement & Architecture
- 🗺️ Site & Landscape
- 🪦 Burial & Death
- 🌍 Ethnicity & Identity

## How Tags Work

Tags are extracted from:
1. **File content** (primary source) - keyword patterns in text
2. **Filename** (secondary) - patterns in note filenames
3. **Folder path** (fallback) - patterns in year/collection names

Tags are automatically mapped to categories using pattern matching in `backend.py`.

## Security

The app does NOT upload:
- `.env` files (API keys)
- `notes_index.json` (if sensitive)
- API keys or credentials

See `.gitignore` for excluded files.

## Troubleshooting

### "Error: API error: 500"
- Check Railway logs for stack trace
- Ensure `notes_index.json` exists in `note_organizer/`
- Try rescanning notes via API

### Slow initial load
- First scan indexes all 700+ notes
- Subsequent loads are cached
- Use `/api/rescan` to manually refresh

### Missing years in dropdown
- Check that notes are in year-named folders (e.g., `/1995/`)
- Run rescan via API or dashboard

## Contributing

To add new categories:
1. Edit `backend.py` → `EthnographicAnalyzer.CATEGORIES`
2. Add patterns for tag matching
3. Rescan notes with `/api/rescan`

## License

Project for archaeological research documentation.

## Contact

For issues or questions, check the project repository.
