import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from enhanced_tagger import get_tags_for_note

try:
    import docx
except ImportError:
    docx = None

try:
    import spacy
    SPACY_MODEL = "en_core_web_sm"
    try:
        nlp = spacy.load(SPACY_MODEL)
    except Exception:
        nlp = spacy.blank("en")
except ImportError:
    nlp = None

try:
    import openai
except ImportError:
    openai = None

SUPPORTED_EXTENSIONS = [".txt", ".docx", ".doc"]

TAG_PATTERNS = {
    "ethnicity": [r"ethnic", r"ethnicity", r"kurd", r"turk", r"alevi", r"y[öo]rük", r"roma", r"circass", r"armen", r"arab"],
    "herding": [r"herd", r"sheep", r"cattle", r"goat", r"grazing", r"shepherd", r"flock", r"pastur"],
    "agriculture": [r"farm", r"farming", r"crop", r"wheat", r"barley", r"soil", r"tractor", r"plow", r"planting", r"harvest"],
    "household": [r"cook", r"kitchen", r"dairy", r"cheese", r"butter", r"milk", r"home", r"household", r"family"],
    "migration": [r"migrat", r"settle", r"move", r"village", r"relocat", r"immigrant"],
    "social": [r"married", r"wife", r"husband", r"son", r"daughter", r"visit", r"wife", r"men", r"women", r"cousin"],
    "burial": [r"burial", r"grave", r"funeral", r"cemeter", r"buried"],
    "religion": [r"mosque", r"church", r"prayer", r"religion", r"islam", r"muslim", r"christian", r"alevi"],
    "economy": [r"tax", r"price", r"market", r"income", r"money", r"cost", r"sell", r"buy"],
    "archaeology": [r"excavation", r"excavate", r"trench", r"stratigraphy", r"context", r"layer", r"dig", r"survey", r"site", r"artifact", r"pottery", r"lithic", r"ceramic", r"bone", r"architecture"],
    "artifacts": [r"artifact", r"artifacts", r"pottery", r"ceramic", r"lithic", r"tool", r"vessel", r"ornament", r"bead", r"metal", r"shard", r"bone"],
    "architecture": [r"building", r"wall", r"house", r"structure", r"ruin", r"room", r"foundation", r"mudbrick", r"stone", r"architecture", r"settlement"],
    "landscape": [r"landscape", r"topography", r"hill", r"valley", r"mound", r"survey", r"plain", r"plateau", r"terrace", r"site"],
}


def is_text_bytes(data: bytes, max_nontext_ratio: float = 0.30) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return False

    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = sum(1 for b in data if b not in text_chars)
    return (nontext / len(data)) <= max_nontext_ratio


def read_text_file(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except Exception:
        return None

    if not is_text_bytes(raw):
        return None

    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def read_docx(path: Path) -> str:
    if docx is None:
        return ""
    document = docx.Document(path)
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def read_doc(path: Path) -> str:
    if shutil.which("antiword") is None:
        return ""
    try:
        proc = subprocess.run(["antiword", str(path)], capture_output=True, text=True, check=True)
        return proc.stdout
    except subprocess.CalledProcessError:
        return ""


def infer_year(path: Path) -> str:
    path_parts = [part for part in path.parts if re.fullmatch(r"19\d{2}|20\d{2}", part)]
    if path_parts:
        return path_parts[0]
    match = re.search(r"(19\d{2}|20\d{2})", path.name)
    return match.group(0) if match else "Unknown"


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def extract_keyword_tags(text: str) -> set[str]:
    tags = set()
    lowered = text.lower()
    for tag, patterns in TAG_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lowered):
                tags.add(tag)
                break
    return tags


def extract_spacy_tags(text: str, max_tags: int = 8) -> set[str]:
    if nlp is None:
        return set()
    doc = nlp(text[:10000])
    candidates = {}
    for chunk in doc.noun_chunks:
        token = chunk.text.strip().lower()
        if len(token) < 3 or len(token) > 30:
            continue
        if token.isnumeric():
            continue
        candidates[token] = candidates.get(token, 0) + 1
    sorted_tags = sorted(candidates.items(), key=lambda item: (-item[1], len(item[0])))
    return {tag for tag, _ in sorted_tags[:max_tags]}


def make_excerpt(text: str, max_chars: int = 240) -> str:
    excerpt = text.strip().replace("\n", " ")
    if len(excerpt) <= max_chars:
        return excerpt
    return excerpt[:max_chars].rsplit(" ", 1)[0] + "..."


def extract_openai_tags(text: str, api_key: str, max_tags: int = 8) -> list[str]:
    if openai is None or not api_key:
        return []
    openai.api_key = api_key
    prompt = (
        "Read the following note and return a comma-separated list of 5-10 short topic tags. "
        "Use lowercase words or short phrases. Do not include explanations.\n\n"
        f"Note:\n{text[:3000]}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=120,
        )
        raw = response.choices[0].message.content.strip()
        tags = [tag.strip().lower() for tag in re.split(r"[,;\n]+", raw) if tag.strip()]
        return tags[:max_tags]
    except Exception:
        return []


def scan_notes(root: str, index_path: str | Path = "notes_index.json", openai_key: str | None = None, use_openai: bool = False) -> dict:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Root path not found: {root}")
    files = []
    for path in root_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            if path.name.startswith("~$"):
                continue
            files.append(path)

    notes = []
    skipped = 0
    for path in sorted(files):
        if path.suffix.lower() == ".txt":
            text = read_text_file(path)
            if text is None:
                skipped += 1
                continue
        elif path.suffix.lower() == ".docx":
            text = read_docx(path)
        elif path.suffix.lower() == ".doc":
            text = read_doc(path)
        else:
            text = ""

        text = normalize_text(text)
        
        # Use enhanced tagging with filename and path patterns
        tags = get_tags_for_note(path.name, text, path)
        
        # Also try keyword-based tags as fallback
        keyword_tags = extract_keyword_tags(text)
        tags.update(keyword_tags)
        
        # Add spacy tags if available
        tags.update(extract_spacy_tags(text))
        
        if use_openai and openai_key:
            tags.update(extract_openai_tags(text, openai_key))

        note = {
            "title": path.name,
            "path": str(path),
            "year": infer_year(path),
            "tags": sorted(tags),
            "excerpt": make_excerpt(text),
            "source": path.suffix.lower().lstrip('.'),
        }
        notes.append(note)

    index = {
        "root": str(root_path),
        "note_count": len(notes),
        "notes": notes,
    }
    if skipped:
        index["skipped_unreadable_txt"] = skipped
    index_file = Path(index_path)
    index_file.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    return index


def load_index(index_path: str | Path = "notes_index.json") -> dict:
    path = Path(index_path)
    if not path.exists():
        return {"root": "", "note_count": 0, "notes": []}
    return json.loads(path.read_text(encoding="utf-8"))
