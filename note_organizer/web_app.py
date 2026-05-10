"""
FastAPI web application for Archaeological / Ethnographic Field Notes Organizer

Features:
- Browse notes by year, category, and search
- View full note text in browser
- Preview .txt and .docx files inline
- Download individual files
- Download all notes for a year as ZIP
- Download all notes for a category as ZIP
- Safer file serving using generated note IDs instead of raw paths in the browser
"""

import html
import io
import json
import mimetypes
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse, FileResponse
import uvicorn

from backend import EthnographicAnalyzer, NoteService
from organizer import load_index, scan_notes, scan_notes_from_drive

try:
    import docx
except ImportError:
    docx = None


# ------------------------------------------------------------
# App setup
# ------------------------------------------------------------

app = FastAPI(title="Archaeological Field Notes Organizer")

service = NoteService()
analyzer = EthnographicAnalyzer()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
INDEX_PATH = BASE_DIR / "notes_index.json"

DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "1Euk4YpPVaYgWFjHuI3g9IJ4vKT-e2mbL")

try:
    from drive_client import DriveClient
    drive_client = DriveClient()
    print("Google Drive client initialized")
except Exception as _drive_exc:
    print(f"Google Drive not available: {_drive_exc}")
    drive_client = None

index_data: Dict[str, Any] = {}
note_id_map: Dict[str, Dict[str, Any]] = {}


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def load_or_scan_index() -> Dict[str, Any]:
    """Load cached index if available, otherwise scan from Google Drive."""
    try:
        if INDEX_PATH.exists():
            data = load_index(str(INDEX_PATH))
            # Only use cached index if it came from Drive (has drive_id on notes)
            if data and data.get("notes") and data.get("source") == "google_drive":
                return data
    except Exception as exc:
        print(f"Could not load cached index: {exc}")

    if drive_client:
        print(f"Scanning notes from Google Drive folder {DRIVE_FOLDER_ID}...")
        try:
            data = scan_notes_from_drive(DRIVE_FOLDER_ID, drive_client, str(INDEX_PATH))
            return data
        except Exception as exc:
            print(f"Drive scan failed: {exc}")

    print("Falling back to local filesystem scan...")
    try:
        data = scan_notes(str(PROJECT_ROOT), str(INDEX_PATH))
        print(f"Indexed {data.get('note_count', 0)} notes")
        return data
    except Exception as exc:
        print(f"Local scan failed: {exc}")
        return {"root": str(PROJECT_ROOT), "note_count": 0, "notes": []}


def rebuild_note_id_map() -> None:
    """Assign stable browser-safe IDs to notes."""
    global note_id_map

    note_id_map = {}

    for i, note in enumerate(index_data.get("notes", []), start=1):
        note_id = f"note-{i}"
        note["id"] = note_id
        note_id_map[note_id] = note


def get_note_or_404(note_id: str) -> Dict[str, Any]:
    note = note_id_map.get(note_id)

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    return note


def get_note_path_or_404(note_id: str) -> Path:
    note = get_note_or_404(note_id)
    raw_path = note.get("path")

    if not raw_path:
        raise HTTPException(status_code=404, detail="File path missing for this note")

    file_path = Path(raw_path).expanduser().resolve()

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    return file_path


def safe_read_text_file(path: Path) -> str:
    """Read text files with fallback encodings."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "mac_roman"]

    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding, errors="replace")
        except Exception:
            continue

    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_docx_text(path: Path) -> str:
    """Extract readable text from .docx files."""
    if docx is None:
        return (
            "python-docx is not installed, so this .docx file cannot be previewed.\n\n"
            "Install it with:\n"
            "pip install python-docx"
        )

    try:
        document = docx.Document(str(path))
        paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]

        # Include table text too, because many field-note docs may be table-like.
        table_lines = []
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    table_lines.append(" | ".join(cells))

        parts = []
        if paragraphs:
            parts.append("\n\n".join(paragraphs))
        if table_lines:
            parts.append("\n\nTABLE CONTENT\n" + "\n".join(table_lines))

        return "\n\n".join(parts).strip() or "(No readable text found in this .docx file.)"

    except Exception as exc:
        return f"Could not preview this .docx file.\n\nError: {exc}"


def extract_doc_text_mac(path: Path) -> str:
    """
    Extract readable text from legacy .doc files using macOS textutil.

    This works on macOS because textutil is built in. If textutil cannot read a
    specific legacy Word file, the app falls back to a clear download message.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.txt"

            result = subprocess.run(
                [
                    "textutil",
                    "-convert",
                    "txt",
                    str(path),
                    "-output",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return (
                    "Could not preview this legacy .doc file with macOS textutil.\n\n"
                    f"textutil error:\n{result.stderr.strip()}\n\n"
                    "Use the Download button to open the original file."
                )

            if output_path.exists():
                text = output_path.read_text(encoding="utf-8", errors="replace").strip()
                return text or "(No readable text found in this .doc file.)"

            return "(No readable text found in this .doc file.)"

    except Exception as exc:
        return (
            "Could not preview this legacy .doc file.\n\n"
            f"Error: {exc}\n\n"
            "Use the Download button to open the original file."
        )


_DRIVE_MIME_TO_EXT = {
    "text/plain": ".txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/vnd.google-apps.document": ".docx",
}


def fetch_drive_bytes(note: Dict[str, Any]) -> tuple:
    """Download a note from Drive. Returns (bytes, effective_mime, filename)."""
    if not drive_client:
        raise HTTPException(status_code=503, detail="Google Drive not configured")
    drive_id = note.get("drive_id")
    if not drive_id:
        raise HTTPException(status_code=404, detail="No Drive ID for this note")
    mime = note.get("drive_mime_type", "application/octet-stream")
    data = drive_client.download_bytes(drive_id, mime)
    name = note.get("title", "file")
    if mime == "application/vnd.google-apps.document" and not name.lower().endswith(".docx"):
        name = name + ".docx"
        eff_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        eff_mime = mime
    return data, eff_mime, name


def preview_note_from_drive(note: Dict[str, Any]) -> Dict[str, Any]:
    """Extract preview text for a Drive-backed note."""
    note_id = note["id"]
    mime = note.get("drive_mime_type", "")
    suffix = _DRIVE_MIME_TO_EXT.get(mime, Path(note.get("title", "")).suffix.lower())
    name = note.get("title", "file")

    try:
        raw, _, filename = fetch_drive_bytes(note)
    except HTTPException as exc:
        return {
            "id": note_id, "title": name, "year": note.get("year", "Unknown"),
            "source": note.get("source", "unknown"), "tags": note.get("tags", []),
            "excerpt": note.get("excerpt", ""), "path": note.get("path", ""),
            "filename": name, "extension": suffix, "preview_type": "error",
            "can_inline_preview": False, "content": f"Could not download from Drive: {exc.detail}",
        }

    if suffix == ".txt":
        content = None
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                content = raw.decode(enc)
                break
            except Exception:
                continue
        content = content or raw.decode("utf-8", errors="replace")
        preview_type, can_inline_preview = "text", True

    elif suffix == ".docx":
        if docx is not None:
            try:
                doc = docx.Document(io.BytesIO(raw))
                paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
                table_lines = []
                for table in doc.tables:
                    for row in table.rows:
                        cells = [c.text.strip() for c in row.cells if c.text.strip()]
                        if cells:
                            table_lines.append(" | ".join(cells))
                parts = []
                if paragraphs:
                    parts.append("\n\n".join(paragraphs))
                if table_lines:
                    parts.append("\n\nTABLE CONTENT\n" + "\n".join(table_lines))
                content = "\n\n".join(parts).strip() or "(No readable text found.)"
            except Exception as exc:
                content = f"Could not read .docx file: {exc}"
        else:
            content = "python-docx is not installed; cannot preview .docx files."
        preview_type, can_inline_preview = "docx-text", True

    else:
        content = (
            f"Preview is not available for {suffix or 'this file type'}.\n\n"
            "Use the Download button to open the original file."
        )
        preview_type, can_inline_preview = "unsupported", False

    return {
        "id": note_id,
        "title": name,
        "year": note.get("year", "Unknown"),
        "source": note.get("source", suffix.lstrip(".") or "unknown"),
        "tags": note.get("tags", []),
        "excerpt": note.get("excerpt", ""),
        "path": note.get("path", ""),
        "filename": filename if suffix == ".docx" and mime == "application/vnd.google-apps.document" else name,
        "extension": suffix,
        "preview_type": preview_type,
        "can_inline_preview": can_inline_preview,
        "content": content,
    }


def preview_note_text(note_id: str) -> Dict[str, Any]:
    """Return preview text and metadata for a note."""
    note = get_note_or_404(note_id)

    if note.get("drive_id"):
        return preview_note_from_drive(note)

    path = get_note_path_or_404(note_id)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        content = safe_read_text_file(path)
        preview_type = "text"
        can_inline_preview = True

    elif suffix == ".docx":
        content = extract_docx_text(path)
        preview_type = "docx-text"
        can_inline_preview = True

    elif suffix == ".doc":
        content = extract_doc_text_mac(path)
        preview_type = "legacy-doc-text"
        can_inline_preview = True

    else:
        content = (
            f"Preview is not available for {suffix or 'this file type'}.\n\n"
            "Use the Download button to open the original file."
        )
        preview_type = "unsupported"
        can_inline_preview = False

    return {
        "id": note_id,
        "title": note.get("title", path.name),
        "year": note.get("year", "Unknown"),
        "source": note.get("source", suffix.replace(".", "") or "unknown"),
        "tags": note.get("tags", []),
        "excerpt": note.get("excerpt", ""),
        "path": str(path),
        "filename": path.name,
        "extension": suffix,
        "preview_type": preview_type,
        "can_inline_preview": can_inline_preview,
        "content": content,
    }


def category_for_note(note: Dict[str, Any]) -> List[str]:
    cats = []

    for tag in note.get("tags", []):
        cat = analyzer.get_category_for_tag(tag)
        if cat and cat not in cats:
            cats.append(cat)

    return cats


def filter_notes(
    year: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    filtered = []

    search_lower = search.lower().strip() if search else ""

    for note in index_data.get("notes", []):
        if year and year != "All" and note.get("year") != year:
            continue

        if category and category != "All":
            note_categories = category_for_note(note)
            if category not in note_categories:
                continue

        if search_lower:
            title = note.get("title", "").lower()
            excerpt = note.get("excerpt", "").lower()
            tags = " ".join(note.get("tags", [])).lower()
            note_year = str(note.get("year", "")).lower()

            if (
                search_lower not in title
                and search_lower not in excerpt
                and search_lower not in tags
                and search_lower not in note_year
            ):
                continue

        output_note = dict(note)
        output_note["categories"] = category_for_note(note)
        filtered.append(output_note)

    return filtered


def make_zip_response(notes: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            year = note.get("year", "Unknown")
            drive_id = note.get("drive_id")

            if drive_id and drive_client:
                mime = note.get("drive_mime_type", "application/octet-stream")
                name = note.get("title", "file")
                if mime == "application/vnd.google-apps.document" and not name.lower().endswith(".docx"):
                    name = name + ".docx"
                try:
                    data = drive_client.download_bytes(drive_id, mime)
                    zf.writestr(f"{year}/{name}", data)
                except Exception as exc:
                    print(f"ZIP: could not download {name}: {exc}")
                continue

            raw_path = note.get("path")
            if not raw_path:
                continue
            path = Path(raw_path).expanduser().resolve()
            if not path.exists() or not path.is_file():
                continue
            try:
                zf.write(path, arcname=f"{year}/{path.name}")
            except Exception:
                continue

    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def make_safe_filename(name: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in name)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "download"


# ------------------------------------------------------------
# Initialize data
# ------------------------------------------------------------

index_data = load_or_scan_index()
rebuild_note_id_map()

print(f"✓ Loaded {len(index_data.get('notes', []))} notes from index")


# ------------------------------------------------------------
# API routes
# ------------------------------------------------------------

@app.get("/api/index")
async def get_index():
    """Get the full notes index."""
    return index_data


@app.get("/api/years")
async def get_years():
    """Get all available years."""
    years = sorted({
        note.get("year")
        for note in index_data.get("notes", [])
        if note.get("year") and note.get("year") != "Unknown"
    })

    return {"years": years}


@app.get("/api/categories")
async def get_categories():
    """Get all categories with labels and patterns."""
    cats = {}

    for cat_key, cat_info in analyzer.CATEGORIES.items():
        cats[cat_key] = {
            "label": cat_info["label"],
            "patterns": cat_info["patterns"]
        }

    return cats


@app.get("/api/notes")
async def get_filtered_notes(
    year: str = Query(None),
    category: str = Query(None),
    search: str = Query(None)
):
    """Get filtered notes."""
    notes = filter_notes(year=year, category=category, search=search)
    return {"notes": notes, "count": len(notes)}


@app.get("/api/stats")
async def get_stats():
    """Get library statistics."""
    notes = index_data.get("notes", [])
    years = {
        note.get("year")
        for note in notes
        if note.get("year") and note.get("year") != "Unknown"
    }

    category_counts = {}
    year_counts = {}

    for note in notes:
        year = note.get("year", "Unknown")
        year_counts[year] = year_counts.get(year, 0) + 1

        for cat in category_for_note(note):
            category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "total_notes": len(notes),
        "years_covered": len(years),
        "year_range": f"{min(years) if years else 'N/A'} - {max(years) if years else 'N/A'}",
        "categories": category_counts,
        "years": year_counts,
        "root": index_data.get("root", str(PROJECT_ROOT)),
    }


@app.get("/api/note/{note_id}")
async def get_note_preview(note_id: str):
    """Get full preview text and metadata for a note."""
    return preview_note_text(note_id)


@app.get("/api/note/{note_id}/text", response_class=PlainTextResponse)
async def get_note_text(note_id: str):
    """Get note preview as plain text."""
    preview = preview_note_text(note_id)
    return preview["content"]


@app.get("/api/note/{note_id}/view", response_class=HTMLResponse)
async def view_note_page(note_id: str):
    """Open a readable note page in a new tab."""
    preview = preview_note_text(note_id)
    title = html.escape(preview["title"])
    content = html.escape(preview["content"])
    tags = " ".join(
        f'<span class="tag">{html.escape(str(tag))}</span>'
        for tag in preview.get("tags", [])
    )

    download_url = f"/api/note/{note_id}/download"
    raw_url = f"/api/note/{note_id}/raw"

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            margin: 0;
            background: #f5f2ea;
            color: #2f261f;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
        }}
        .wrap {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 28px;
        }}
        .topbar {{
            background: #fff;
            border: 1px solid #e5dccb;
            border-radius: 16px;
            padding: 22px;
            margin-bottom: 20px;
            box-shadow: 0 8px 24px rgba(80, 54, 28, 0.08);
        }}
        h1 {{
            margin: 0 0 8px;
            color: #7b3f15;
            font-size: 28px;
            line-height: 1.25;
        }}
        .meta {{
            color: #6d6257;
            margin-bottom: 14px;
        }}
        .tag {{
            display: inline-block;
            background: #efe3d3;
            color: #3d3026;
            padding: 5px 9px;
            border-radius: 999px;
            font-size: 12px;
            margin: 4px 5px 0 0;
        }}
        .actions {{
            margin-top: 16px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        a.button {{
            display: inline-block;
            text-decoration: none;
            background: #8b4513;
            color: white;
            padding: 10px 14px;
            border-radius: 10px;
            font-weight: 700;
        }}
        a.button.secondary {{
            background: #5d6470;
        }}
        pre {{
            white-space: pre-wrap;
            word-break: break-word;
            background: #fff;
            border: 1px solid #e5dccb;
            border-radius: 16px;
            padding: 24px;
            line-height: 1.6;
            font-size: 15px;
            box-shadow: 0 8px 24px rgba(80, 54, 28, 0.08);
        }}
    </style>
</head>
<body>
    <div class="wrap">
        <div class="topbar">
            <h1>{title}</h1>
            <div class="meta">
                Year: {html.escape(str(preview["year"]))} |
                Source: {html.escape(str(preview["source"]))} |
                File: {html.escape(str(preview["filename"]))}
            </div>
            <div>{tags}</div>
            <div class="actions">
                <a class="button" href="{download_url}">Download Original</a>
                <a class="button secondary" href="{raw_url}" target="_blank">Open Raw File</a>
                <a class="button secondary" href="/">Back to Library</a>
            </div>
        </div>

        <pre>{content}</pre>
    </div>
</body>
</html>
"""


@app.get("/api/note/{note_id}/raw")
async def open_raw_note(note_id: str):
    """Open the original file directly in the browser."""
    note = get_note_or_404(note_id)

    if note.get("drive_id"):
        data, eff_mime, name = fetch_drive_bytes(note)
        return StreamingResponse(
            iter([data]),
            media_type=eff_mime,
            headers={"Content-Disposition": f'inline; filename="{name}"'},
        )

    path = get_note_path_or_404(note_id)
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(
        path=str(path),
        media_type=media_type or "application/octet-stream",
        filename=path.name,
    )


@app.get("/api/note/{note_id}/download")
async def download_note(note_id: str):
    """Download original note file."""
    note = get_note_or_404(note_id)

    if note.get("drive_id"):
        data, _, name = fetch_drive_bytes(note)
        return StreamingResponse(
            iter([data]),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    path = get_note_path_or_404(note_id)
    return FileResponse(
        path=str(path),
        media_type="application/octet-stream",
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@app.get("/api/download/category/{category}")
async def download_category(category: str):
    """Download all notes in a category as ZIP."""
    notes = filter_notes(category=category)

    if not notes:
        raise HTTPException(status_code=404, detail="No notes in category")

    cat_label = analyzer.CATEGORIES.get(category, {}).get("label", category)
    safe_name = make_safe_filename(cat_label)

    return make_zip_response(notes, f"{safe_name}_notes.zip")


@app.get("/api/download/year/{year}")
async def download_year(year: str):
    """Download all notes from a year as ZIP."""
    notes = filter_notes(year=year)

    if not notes:
        raise HTTPException(status_code=404, detail="No notes for year")

    safe_year = make_safe_filename(year)

    return make_zip_response(notes, f"{safe_year}_notes.zip")


@app.post("/api/rescan")
async def rescan():
    """Rescan notes from Google Drive (or local filesystem) and rebuild the index."""
    global index_data

    if drive_client:
        index_data = scan_notes_from_drive(DRIVE_FOLDER_ID, drive_client, str(INDEX_PATH))
    else:
        index_data = scan_notes(str(PROJECT_ROOT), str(INDEX_PATH))

    rebuild_note_id_map()

    return {
        "status": "ok",
        "note_count": index_data.get("note_count", 0)
    }


# ------------------------------------------------------------
# HTML frontend
# ------------------------------------------------------------

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archaeological Field Notes Organizer</title>

    <style>
        :root {
            --bg: #f5f2ea;
            --paper: #ffffff;
            --paper-soft: #fbf8f2;
            --text: #2f261f;
            --muted: #6f665d;
            --brand: #8b4513;
            --brand-dark: #65310f;
            --brand-soft: #efe3d3;
            --green: #247a45;
            --blue: #315f8f;
            --red: #9f3434;
            --border: #e6dccb;
            --shadow: 0 8px 24px rgba(80, 54, 28, 0.08);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: radial-gradient(circle at top left, #fff7ea 0, var(--bg) 38%, #eee7dc 100%);
            color: var(--text);
            min-height: 100vh;
        }

        .container {
            max-width: 1500px;
            margin: 0 auto;
            padding: 24px;
        }

        header {
            background:
                linear-gradient(135deg, rgba(139,69,19,0.96), rgba(160,82,45,0.94)),
                radial-gradient(circle at top right, rgba(255,255,255,0.3), transparent 40%);
            color: white;
            padding: 34px 28px;
            border-radius: 22px;
            margin-bottom: 26px;
            box-shadow: var(--shadow);
        }

        header h1 {
            font-size: clamp(30px, 4vw, 48px);
            margin-bottom: 8px;
            letter-spacing: -0.04em;
        }

        header p {
            font-size: 16px;
            opacity: 0.92;
            max-width: 850px;
            line-height: 1.5;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 22px;
        }

        .stat-card {
            background: rgba(255,255,255,0.88);
            backdrop-filter: blur(8px);
            padding: 18px;
            border-radius: 18px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
        }

        .stat-card .value {
            font-size: 30px;
            font-weight: 850;
            color: var(--brand);
            line-height: 1.1;
        }

        .stat-card .label {
            font-size: 13px;
            color: var(--muted);
            margin-top: 6px;
            font-weight: 650;
        }

        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 18px;
            flex-wrap: wrap;
        }

        .tab-btn {
            border: 1px solid var(--border);
            background: var(--paper);
            color: var(--muted);
            padding: 10px 14px;
            border-radius: 999px;
            cursor: pointer;
            font-weight: 800;
            box-shadow: 0 4px 14px rgba(80, 54, 28, 0.05);
        }

        .tab-btn.active {
            background: var(--brand);
            color: white;
            border-color: var(--brand);
        }

        .filters {
            background: rgba(255,255,255,0.88);
            backdrop-filter: blur(8px);
            padding: 18px;
            border-radius: 18px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
        }

        .filter-row {
            display: grid;
            grid-template-columns: 170px 260px minmax(260px, 1fr) auto auto;
            gap: 14px;
            align-items: end;
        }

        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 7px;
        }

        .filter-group label {
            font-weight: 800;
            color: var(--text);
            font-size: 13px;
        }

        select,
        input {
            width: 100%;
            padding: 11px 12px;
            border: 1px solid var(--border);
            border-radius: 12px;
            font-size: 15px;
            background: white;
            color: var(--text);
        }

        select:focus,
        input:focus {
            outline: none;
            border-color: var(--brand);
            box-shadow: 0 0 0 4px rgba(139, 69, 19, 0.12);
        }

        button,
        .button-link {
            background: var(--brand);
            color: white;
            padding: 11px 14px;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 850;
            transition: transform 0.15s ease, background-color 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 7px;
            white-space: nowrap;
        }

        button:hover,
        .button-link:hover {
            background: var(--brand-dark);
            transform: translateY(-1px);
        }

        button.secondary,
        .button-link.secondary {
            background: #68635e;
        }

        button.green,
        .button-link.green {
            background: var(--green);
        }

        button.blue,
        .button-link.blue {
            background: var(--blue);
        }

        button.red {
            background: var(--red);
        }

        .results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            gap: 12px;
            flex-wrap: wrap;
        }

        .results-header h2 {
            font-size: 22px;
            letter-spacing: -0.02em;
        }

        .notes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(370px, 1fr));
            gap: 18px;
        }

        .note-card {
            background: rgba(255,255,255,0.92);
            padding: 18px;
            border-radius: 18px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            transition: transform 0.16s ease, box-shadow 0.16s ease;
            min-height: 290px;
            display: flex;
            flex-direction: column;
        }

        .note-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 34px rgba(80, 54, 28, 0.12);
        }

        .note-card h3 {
            margin-bottom: 10px;
            color: var(--brand);
            word-break: break-word;
            font-size: 18px;
            line-height: 1.25;
        }

        .note-meta {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            font-size: 13px;
            color: var(--muted);
            margin-bottom: 10px;
            font-weight: 650;
        }

        .pill {
            background: var(--paper-soft);
            border: 1px solid var(--border);
            padding: 4px 8px;
            border-radius: 999px;
        }

        .tags {
            margin: 8px 0 10px;
        }

        .tag {
            display: inline-block;
            background-color: var(--brand-soft);
            color: #3d3026;
            padding: 4px 8px;
            border-radius: 999px;
            font-size: 12px;
            margin-right: 5px;
            margin-bottom: 5px;
            font-weight: 700;
        }

        .category-tag {
            background: #dcc19d;
            color: #2e2118;
        }

        .excerpt {
            font-size: 14px;
            color: #52483f;
            line-height: 1.55;
            margin: 6px 0 14px;
            flex: 1;
            max-height: 130px;
            overflow: hidden;
            position: relative;
        }

        .card-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: auto;
        }

        .small-btn {
            padding: 8px 10px;
            font-size: 13px;
            border-radius: 10px;
        }

        .empty {
            background: white;
            padding: 46px;
            border-radius: 18px;
            text-align: center;
            color: var(--muted);
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            grid-column: 1 / -1;
        }

        .categories-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 18px;
        }

        .category-card {
            background: rgba(255,255,255,0.92);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 18px;
            box-shadow: var(--shadow);
        }

        .category-card h3 {
            color: var(--brand);
            margin-bottom: 10px;
        }

        .category-patterns {
            color: var(--muted);
            line-height: 1.45;
            font-size: 14px;
            margin-bottom: 14px;
        }

        .viewer-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(31, 24, 18, 0.56);
            display: none;
            align-items: center;
            justify-content: center;
            padding: 22px;
            z-index: 1000;
        }

        .viewer {
            width: min(1180px, 96vw);
            height: min(850px, 92vh);
            background: #fff;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 24px 80px rgba(0,0,0,0.28);
            display: flex;
            flex-direction: column;
        }

        .viewer-header {
            padding: 16px 18px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
            background: var(--paper-soft);
        }

        .viewer-title h2 {
            font-size: 20px;
            color: var(--brand);
            margin-bottom: 5px;
            line-height: 1.25;
        }

        .viewer-meta {
            font-size: 13px;
            color: var(--muted);
            font-weight: 650;
        }

        .viewer-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: flex-end;
        }

        .viewer-body {
            overflow: auto;
            padding: 18px;
            flex: 1;
        }

        .viewer-content {
            white-space: pre-wrap;
            word-break: break-word;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
            background: #fff;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px;
            line-height: 1.6;
            font-size: 14px;
            min-height: 100%;
        }

        .path-line {
            font-size: 12px;
            color: #83786c;
            margin-top: 8px;
            word-break: break-all;
        }

        .toast {
            position: fixed;
            right: 18px;
            bottom: 18px;
            padding: 12px 14px;
            background: #2f261f;
            color: white;
            border-radius: 12px;
            display: none;
            z-index: 2000;
            box-shadow: var(--shadow);
            max-width: 420px;
        }

        @media (max-width: 960px) {
            .filter-row {
                grid-template-columns: 1fr;
            }

            .notes-grid {
                grid-template-columns: 1fr;
            }

            .viewer {
                width: 98vw;
                height: 94vh;
            }

            .viewer-header {
                flex-direction: column;
            }
        }
    </style>
</head>

<body>
    <div class="container">
        <header>
            <h1>🏺 Archaeological Field Notes Organizer</h1>
            <p>
                Browse the full field-note archive by year, ethnographic category, and keywords.
                Click any note to view extracted text, open the original file, or download it.
            </p>
        </header>

        <div class="stats" id="stats"></div>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab(event, 'browse')">Browse Notes</button>
            <button class="tab-btn" onclick="switchTab(event, 'categories')">Categories</button>
        </div>

        <div id="browse-tab">
            <div class="filters">
                <div class="filter-row">
                    <div class="filter-group">
                        <label for="year-filter">Year</label>
                        <select id="year-filter" onchange="filterNotes()">
                            <option value="">All Years</option>
                        </select>
                    </div>

                    <div class="filter-group">
                        <label for="category-filter">Category</label>
                        <select id="category-filter" onchange="filterNotes()">
                            <option value="">All Categories</option>
                        </select>
                    </div>

                    <div class="filter-group">
                        <label for="search-input">Search title, text excerpt, tag, year</label>
                        <input type="text" id="search-input" placeholder="Example: farming, burial, household, 1995..." onkeyup="debouncedFilterNotes()">
                    </div>

                    <button onclick="clearFilters()">Clear</button>
                    <button class="secondary" onclick="rescanLibrary()">Rescan</button>
                </div>
            </div>

            <div class="results-header">
                <h2 id="results-count">Loading...</h2>
                <div id="bulk-actions"></div>
            </div>

            <div id="notes-container" class="notes-grid"></div>
        </div>

        <div id="categories-tab" style="display: none;">
            <div id="categories-container" class="categories-grid"></div>
        </div>
    </div>

    <div class="viewer-backdrop" id="viewer-backdrop" onclick="closeViewerFromBackdrop(event)">
        <div class="viewer">
            <div class="viewer-header">
                <div class="viewer-title">
                    <h2 id="viewer-title">Loading...</h2>
                    <div class="viewer-meta" id="viewer-meta"></div>
                    <div class="path-line" id="viewer-path"></div>
                </div>

                <div class="viewer-actions">
                    <a class="button-link green small-btn" id="viewer-download" href="#" target="_blank">Download</a>
                    <a class="button-link blue small-btn" id="viewer-full-page" href="#" target="_blank">Open Page</a>
                    <a class="button-link secondary small-btn" id="viewer-raw" href="#" target="_blank">Raw File</a>
                    <button class="red small-btn" onclick="closeViewer()">Close</button>
                </div>
            </div>

            <div class="viewer-body">
                <div class="viewer-content" id="viewer-content">Loading...</div>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        let categoriesCache = {};
        let filterTimer = null;

        async function init() {
            try {
                await loadStats();
                await loadYears();
                await loadCategories();
                await filterNotes();
            } catch (err) {
                console.error('Init error:', err);
                showToast('Error loading app: ' + err.message);
                document.getElementById('results-count').textContent = 'Error loading data';
            }
        }

        async function apiGet(url) {
            const response = await fetch(url);

            if (!response.ok) {
                const text = await response.text();
                throw new Error(`${response.status}: ${text}`);
            }

            return await response.json();
        }

        async function loadStats() {
            const data = await apiGet('/api/stats');

            const statsHtml = `
                <div class="stat-card">
                    <div class="value">${data.total_notes}</div>
                    <div class="label">Total Notes</div>
                </div>
                <div class="stat-card">
                    <div class="value">${data.years_covered}</div>
                    <div class="label">Years Covered</div>
                </div>
                <div class="stat-card">
                    <div class="value">${escapeHtml(data.year_range)}</div>
                    <div class="label">Time Span</div>
                </div>
                <div class="stat-card">
                    <div class="value">${Object.keys(data.categories || {}).length}</div>
                    <div class="label">Categories Detected</div>
                </div>
            `;

            document.getElementById('stats').innerHTML = statsHtml;
        }

        async function loadYears() {
            const data = await apiGet('/api/years');

            const yearSelect = document.getElementById('year-filter');
            yearSelect.innerHTML = '<option value="">All Years</option>';

            data.years.forEach(year => {
                const option = document.createElement('option');
                option.value = year;
                option.textContent = year;
                yearSelect.appendChild(option);
            });
        }

        async function loadCategories() {
            const categories = await apiGet('/api/categories');
            categoriesCache = categories;

            const categorySelect = document.getElementById('category-filter');
            categorySelect.innerHTML = '<option value="">All Categories</option>';

            Object.entries(categories).forEach(([key, cat]) => {
                const option = document.createElement('option');
                option.value = key;
                option.textContent = cat.label;
                categorySelect.appendChild(option);
            });

            renderCategories(categories);
        }

        function renderCategories(categories) {
            const container = document.getElementById('categories-container');
            let html = '';

            Object.entries(categories).forEach(([key, cat]) => {
                html += `
                    <div class="category-card">
                        <h3>${escapeHtml(cat.label)}</h3>
                        <div class="category-patterns">
                            <strong>Keyword patterns:</strong>
                            ${escapeHtml((cat.patterns || []).slice(0, 12).join(', '))}
                            ${(cat.patterns || []).length > 12 ? '...' : ''}
                        </div>
                        <div class="card-actions">
                            <button class="small-btn" onclick="selectCategory('${key}')">View Notes</button>
                            <a class="button-link green small-btn" href="/api/download/category/${encodeURIComponent(key)}">Download ZIP</a>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html;
        }

        function debouncedFilterNotes() {
            clearTimeout(filterTimer);
            filterTimer = setTimeout(filterNotes, 250);
        }

        async function filterNotes() {
            const year = document.getElementById('year-filter').value;
            const category = document.getElementById('category-filter').value;
            const search = document.getElementById('search-input').value;

            const params = new URLSearchParams();

            if (year) params.append('year', year);
            if (category) params.append('category', category);
            if (search) params.append('search', search);

            const url = `/api/notes?${params.toString()}`;
            const data = await apiGet(url);

            renderNotes(data.notes || [], data.count || 0);
            renderBulkActions(year, category);
        }

        function renderBulkActions(year, category) {
            const container = document.getElementById('bulk-actions');
            let html = '';

            if (year) {
                html += `<a class="button-link green small-btn" href="/api/download/year/${encodeURIComponent(year)}">Download ${escapeHtml(year)} ZIP</a>`;
            }

            if (category) {
                const label = categoriesCache[category]?.label || category;
                html += `<a class="button-link green small-btn" href="/api/download/category/${encodeURIComponent(category)}">Download ${escapeHtml(label)} ZIP</a>`;
            }

            container.innerHTML = html;
        }

        function renderNotes(notes, count) {
            const container = document.getElementById('notes-container');
            document.getElementById('results-count').textContent = `Results: ${count} notes`;

            if (!notes || notes.length === 0) {
                container.innerHTML = '<div class="empty">No notes found matching your filters.</div>';
                return;
            }

            let html = '';

            notes.forEach(note => {
                const tags = note.tags || [];
                const categories = note.categories || [];
                const noteId = note.id;

                const tagsHtml = tags
                    .slice(0, 12)
                    .map(tag => `<span class="tag">${escapeHtml(tag)}</span>`)
                    .join('');

                const categoriesHtml = categories
                    .map(cat => {
                        const label = categoriesCache[cat]?.label || cat;
                        return `<span class="tag category-tag">${escapeHtml(label)}</span>`;
                    })
                    .join('');

                const extraTagCount = tags.length > 12
                    ? `<span class="tag">+${tags.length - 12} more</span>`
                    : '';

                html += `
                    <div class="note-card">
                        <h3>${escapeHtml(note.title || 'Untitled')}</h3>

                        <div class="note-meta">
                            <span class="pill">📅 ${escapeHtml(note.year || 'Unknown')}</span>
                            <span class="pill">📄 ${escapeHtml(note.source || 'Unknown')}</span>
                            <span class="pill">ID: ${escapeHtml(noteId || '')}</span>
                        </div>

                        <div class="tags">
                            ${categoriesHtml}
                            ${tagsHtml}
                            ${extraTagCount}
                        </div>

                        <div class="excerpt">
                            ${escapeHtml(note.excerpt || '(No excerpt available. Click View Text to try extracting the full note.)')}
                        </div>

                        <div class="card-actions">
                            <button class="small-btn" onclick="openViewer('${noteId}')">View Text</button>
                            <a class="button-link blue small-btn" href="/api/note/${encodeURIComponent(noteId)}/view" target="_blank">Open Page</a>
                            <a class="button-link green small-btn" href="/api/note/${encodeURIComponent(noteId)}/download">Download</a>
                            <a class="button-link secondary small-btn" href="/api/note/${encodeURIComponent(noteId)}/raw" target="_blank">Raw</a>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html;
        }

        async function openViewer(noteId) {
            const backdrop = document.getElementById('viewer-backdrop');
            const title = document.getElementById('viewer-title');
            const meta = document.getElementById('viewer-meta');
            const pathLine = document.getElementById('viewer-path');
            const content = document.getElementById('viewer-content');

            backdrop.style.display = 'flex';
            title.textContent = 'Loading...';
            meta.textContent = '';
            pathLine.textContent = '';
            content.textContent = 'Loading note text...';

            try {
                const note = await apiGet(`/api/note/${encodeURIComponent(noteId)}`);

                title.textContent = note.title || 'Untitled';
                meta.textContent = `Year: ${note.year || 'Unknown'} | Source: ${note.source || 'Unknown'} | File: ${note.filename || ''} | Preview: ${note.preview_type}`;
                pathLine.textContent = note.path || '';
                content.textContent = note.content || '(No preview text available.)';

                document.getElementById('viewer-download').href = `/api/note/${encodeURIComponent(noteId)}/download`;
                document.getElementById('viewer-full-page').href = `/api/note/${encodeURIComponent(noteId)}/view`;
                document.getElementById('viewer-raw').href = `/api/note/${encodeURIComponent(noteId)}/raw`;
            } catch (error) {
                title.textContent = 'Could not load note';
                content.textContent = error.message;
            }
        }

        function closeViewer() {
            document.getElementById('viewer-backdrop').style.display = 'none';
        }

        function closeViewerFromBackdrop(event) {
            if (event.target.id === 'viewer-backdrop') {
                closeViewer();
            }
        }

        function switchTab(event, tab) {
            document.getElementById('browse-tab').style.display = tab === 'browse' ? 'block' : 'none';
            document.getElementById('categories-tab').style.display = tab === 'categories' ? 'block' : 'none';

            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
        }

        function selectCategory(category) {
            document.getElementById('category-filter').value = category;
            document.getElementById('browse-tab').style.display = 'block';
            document.getElementById('categories-tab').style.display = 'none';

            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelector('.tab-btn').classList.add('active');

            filterNotes();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function clearFilters() {
            document.getElementById('year-filter').value = '';
            document.getElementById('category-filter').value = '';
            document.getElementById('search-input').value = '';
            filterNotes();
        }

        async function rescanLibrary() {
            const ok = confirm('Rescan the field notes library? This can take a moment.');
            if (!ok) return;

            showToast('Rescanning library...');

            try {
                const response = await fetch('/api/rescan', { method: 'POST' });

                if (!response.ok) {
                    throw new Error(await response.text());
                }

                const data = await response.json();

                showToast(`Rescan complete. Indexed ${data.note_count} notes.`);
                await loadStats();
                await loadYears();
                await loadCategories();
                await filterNotes();
            } catch (error) {
                showToast('Rescan failed: ' + error.message);
            }
        }

        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.style.display = 'block';

            setTimeout(() => {
                toast.style.display = 'none';
            }, 4200);
        }

        function escapeHtml(text) {
            text = String(text ?? '');

            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };

            return text.replace(/[&<>"']/g, m => map[m]);
        }

        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeViewer();
            }
        });

        window.onload = init;
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main HTML page."""
    return HTML_TEMPLATE


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting Archaeological Field Notes Organizer on port {port}...")
    print(f"Open http://localhost:{port} in your browser")
    uvicorn.run(app, host="0.0.0.0", port=port)
