import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

from backend import EthnographicAnalyzer
from organizer import load_index, scan_notes

load_dotenv()

INDEX_FILENAME = "notes_index.json"
DEFAULT_ROOT = ".."

st.set_page_config(page_title="Archaeological Field Notes Organizer", layout="wide")

st.title("Archaeological Field Notes Organizer")
st.write("Select a year and then choose an archaeological category to display matching notes.")
st.info("Documentation is available in ARCHAEOLOGIST_LIBRARY_DOCUMENTATION.md and below.")

with st.sidebar:
    st.header("Library Settings")
    root_path = st.text_input("Field notes root folder", DEFAULT_ROOT)
    if st.button("Rescan library"):
        st.session_state.rescan = True

rescan = st.session_state.get("rescan", False)

index = load_index(INDEX_FILENAME)
if rescan or not index.get("notes"):
    st.info("Scanning your folder library now...")
    index = scan_notes(root_path, INDEX_FILENAME)
    st.session_state.rescan = False

if not index.get("notes"):
    st.warning("No notes were found in the folder structure. Please make sure the year folders are available.")
    st.stop()

if index.get("skipped_unreadable_txt"):
    st.info(f"Skipped {index['skipped_unreadable_txt']} unreadable .txt file(s) during scan.")

st.markdown(f"**Library root:** {index.get('root', root_path)}")
st.markdown(f"**Total notes indexed:** {index.get('note_count', 0)}")

notes = index["notes"]
all_years = sorted({note["year"] for note in notes if note["year"] != "Unknown"})

analyzer = EthnographicAnalyzer()
category_labels = {info["label"]: key for key, info in analyzer.get_all_categories().items()}

with st.sidebar:
    st.header("Filter Notes")
    selected_year = st.selectbox("Year", ["All"] + all_years, index=0)

    year_filtered_notes = [note for note in notes if note["year"] == selected_year] if selected_year != "All" else notes
    available_categories = sorted(
        {analyzer.get_category_label(analyzer.get_category_for_tag(tag))
         for note in year_filtered_notes
         for tag in note.get("tags", [])
         if analyzer.get_category_for_tag(tag)}
    )
    selected_category_label = st.selectbox("Category", ["All"] + available_categories, index=0)

    st.markdown("---")
    st.markdown("**Tip:** Choose the year first, then choose the archaeological category.")
    st.markdown("**Documentation:** ARCHAEOLOGIST_LIBRARY_DOCUMENTATION.md")
    st.markdown("**Tags shown below for the selected year/category.**")

year_filter = None if selected_year == "All" else selected_year
category_filter = None if selected_category_label == "All" else category_labels.get(selected_category_label)

filtered = []
for note in notes:
    if year_filter and note["year"] != year_filter:
        continue
    if category_filter:
            note_categories = {
                analyzer.get_category_for_tag(tag)
                for tag in note.get("tags", [])
                if analyzer.get_category_for_tag(tag)
            }

if not filtered:
    st.info("No matching notes found for that year and category.")
else:
    for note in filtered:
        tags = ", ".join(note.get("tags", [])) if note.get("tags") else "(no tags yet)"
        note_categories = sorted(
            {analyzer.get_category_label(analyzer.get_category_for_tag(tag))
             for tag in note.get("tags", [])
             if analyzer.get_category_for_tag(tag)}
        )
        category_display = ", ".join(note_categories) if note_categories else "Uncategorized"

        st.subheader(note["title"])
        st.write(f"**Year:** {note['year']}  \n**Source:** {note['source']}  \n**Categories:** {category_display}")
        st.write(f"**Tags:** {tags}")
        st.write(note.get("excerpt", ""))
        st.write(f"`{note['path']}`")
        st.markdown("---")

with st.expander("Available tags for this selection"):
    selected_tags = sorted({
        tag
        for note in filtered
        for tag in note.get("tags", [])
    })
    if selected_tags:
        st.write(", ".join(selected_tags))
    else:
        st.write("No tags available for this selection.")

with st.expander("Documentation"):
    doc_path = Path("ARCHAEOLOGIST_LIBRARY_DOCUMENTATION.md")
    if doc_path.exists():
        st.markdown(doc_path.read_text())
    else:
        st.write("Documentation file not found in the folder.")
