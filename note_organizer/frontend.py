"""
Frontend UI for Ethnographic Field Notes Organizer
Built with Streamlit
Organized by year and ethnographic categories: Economics, Social, Cultural, etc.
"""

import io
import zipfile
import os
import streamlit as st
from backend import NoteService

# Page configuration
st.set_page_config(
    page_title="Ethnographic Field Notes Organizer",
    layout="wide",
    initial_sidebar_state="expanded"
)


def build_category_zip(notes: list[dict]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            path = Path(note["path"])
            if path.exists() and path.is_file():
                archive_name = Path(note["year"] if note["year"] != "Unknown" else "Unknown") / path.name
                try:
                    zf.write(path, arcname=str(archive_name))
                except Exception:
                    try:
                        zf.writestr(str(archive_name), path.read_bytes())
                    except Exception:
                        continue
    buffer.seek(0)
    return buffer.getvalue()

# CSS for better styling
st.markdown("""
    <style>
        .category-header {
            font-size: 18px;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .year-header {
            font-size: 24px;
            font-weight: bold;
            color: #1f77b4;
            margin-bottom: 20px;
            border-bottom: 2px solid #1f77b4;
            padding-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🌍 Ethnographic Field Notes Organizer")
st.markdown("*Organizing research by year and ethnographic categories*")

# Initialize backend service
service = NoteService()

# SIDEBAR: Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    root_path = st.text_input("Field notes root folder", value=service.DEFAULT_ROOT)
    service.root_path = root_path
    
    use_openai = st.checkbox("Use OpenAI for enriched categorization", value=False)
    
    if use_openai:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            openai_api_key = st.text_input("OpenAI API key", type="password")
        else:
            st.success("✓ Using API key from .env")
    
    st.divider()
    
    # Scan button
    if st.button("🔍 Scan Notes", use_container_width=True):
        try:
            with st.spinner("Scanning notes..."):
                index = service.scan_notes_directory(use_openai=use_openai)
            st.success(f"✓ Scanned {index['note_count']} notes from {index['root']}")
        except Exception as exc:
            st.error(f"❌ Scan failed: {exc}")
            index = service.load_notes_index()
    else:
        index = service.load_notes_index()

# Check if data exists
if not index.get("notes"):
    st.warning("⚠️ No indexed notes yet. Click 'Scan Notes' after choosing the root folder.")
    st.stop()

# Main tabs for different views
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 By Year",
    "🏷️ By Category",
    "📈 Timeline Analysis",
    "📋 All Notes"
])

# ============= TAB 1: BY YEAR =============
with tab1:
    st.header("Notes Organized by Year")
    
    with st.sidebar:
        st.subheader("📅 Year Filters")
        all_years = service.get_all_years(index)
        selected_years = st.multiselect("Select years", ["All"] + all_years, default=["All"])
    
    if "All" in selected_years or not selected_years:
        display_years = all_years
    else:
        display_years = [y for y in all_years if y in selected_years]
    
    # Display by year
    for year in sorted(display_years, reverse=True):
        year_notes = [n for n in index["notes"] if n["year"] == year]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f'<div class="year-header">{year}</div>', unsafe_allow_html=True)
        with col2:
            st.metric("Notes", len(year_notes))
        
        # Show category breakdown for this year
        categories_count = {}
        for note in year_notes:
            for tag in note.get("tags", []):
                cat = service.analyzer.get_category_for_tag(tag)
                if cat:
                    categories_count[cat] = categories_count.get(cat, 0) + 1
        
        if categories_count:
            cols = st.columns(len(categories_count))
            for idx, (cat, count) in enumerate(sorted(categories_count.items())):
                with cols[idx]:
                    st.metric(service.get_category_label(cat).split()[0], count)
        
        # Display notes for this year with expandable sections
        for note in sorted(year_notes, key=lambda x: x["title"]):
            with st.expander(f"📄 {note['title']}", expanded=False):
                st.markdown(f"**Source:** {note['source']}")
                st.markdown(f"**Path:** {note['path']}")
                
                if note.get("tags"):
                    # Organize tags by category and skip uncategorized tags
                    tags_by_category = {}
                    for tag in note["tags"]:
                        cat = service.analyzer.get_category_for_tag(tag)
                        if not cat:
                            continue
                        if cat not in tags_by_category:
                            tags_by_category[cat] = []
                        tags_by_category[cat].append(tag)
                    
                    for cat in sorted(tags_by_category.keys()):
                        tags = tags_by_category[cat]
                        st.markdown(f"**{service.get_category_label(cat)}:** {', '.join(tags)}")
                
                st.markdown("---")
                st.write(note["excerpt"])

# ============= TAB 2: BY CATEGORY =============
with tab2:
    st.header("Ethnographic Categories")
    
    categories = service.get_all_categories()
    
    with st.sidebar:
        st.subheader("🏷️ Category Filters")
        selected_categories = st.multiselect(
            "Select categories",
            list(categories.keys()),
            default=list(categories.keys())
        )
    
    # Display statistics for each category
    stats = service.analyzer.get_category_statistics(index)
    
    for cat_key in selected_categories:
        cat_info = categories[cat_key]
        cat_stats = stats[cat_key]
        
        if cat_stats["note_count"] == 0:
            continue
        
        with st.expander(f'{cat_info["label"]} ({cat_stats["note_count"]} notes)', expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Notes", cat_stats["note_count"])
            with col2:
                st.metric("Years Covered", len(cat_stats["years_touched"]))
            with col3:
                st.metric("Time Span", cat_stats["year_span"])
            
            st.markdown(f"**Years:** {', '.join(cat_stats['years_touched'][:10])}")
            
            # Show notes in this category
            cat_notes = service.filter_notes(index, categories=[cat_key])
            
            st.markdown(f"**{len(cat_notes)} notes in this category**")
            
            if cat_notes:
                zip_bytes = build_category_zip(cat_notes)
                st.download_button(
                    label=f"Download {cat_info['label']} notes as ZIP",
                    data=zip_bytes,
                    file_name=f"{cat_key}_notes.zip",
                    mime="application/zip"
                )
            
            # Group by year
            by_year = {}
            for note in cat_notes:
                year = note["year"]
                if year not in by_year:
                    by_year[year] = []
                by_year[year].append(note)
            
            for year in sorted(by_year.keys(), reverse=True):
                with st.expander(f"{year} ({len(by_year[year])} notes)"):
                    for note in by_year[year]:
                        st.markdown(f"**{note['title']}**")
                        st.markdown(f"_{note['excerpt']}_")
                        st.markdown("---")

# ============= TAB 3: TIMELINE ANALYSIS =============
with tab3:
    st.header("Timeline Analysis")
    
    timeline_data = service.analyzer.get_timeline_data(index)
    
    if timeline_data:
        # Overall statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Notes", len(index["notes"]))
        with col2:
            st.metric("Years Covered", len(timeline_data))
        with col3:
            st.metric("Year Span", f"{min(timeline_data.keys())} - {max(timeline_data.keys())}")
        with col4:
            st.metric("Avg Notes/Year", f"{len(index['notes']) / len(timeline_data):.1f}")
        
        st.divider()
        
        # Notes per year
        years_sorted = sorted(timeline_data.keys())
        note_counts = [timeline_data[y]["total_notes"] for y in years_sorted]
        
        st.subheader("📊 Notes Per Year")
        st.bar_chart({
            "Year": years_sorted,
            "Notes": note_counts
        })
        
        # Category evolution over time
        st.subheader("🎯 Category Evolution Over Time")
        
        # Prepare data for each category
        category_data = {}
        for cat in service.get_all_categories().keys():
            category_data[cat] = []
            for year in years_sorted:
                count = timeline_data[year]["categories"].get(cat, 0)
                category_data[cat].append(count)
        
        # Show selected categories
        selected_cats = st.multiselect(
            "Select categories to visualize",
            list(service.get_all_categories().keys()),
            default=["economics", "social", "agriculture", "herding"]
        )
        
        if selected_cats:
            chart_data = {"Year": years_sorted}
            for cat in selected_cats:
                chart_data[service.get_category_label(cat)] = category_data[cat]
            
            st.line_chart({k: v for k, v in chart_data.items() if k != "Year"})
        
        # Year-by-year breakdown
        st.subheader("📈 Year-by-Year Breakdown")
        for year in sorted(years_sorted, reverse=True):
            with st.expander(f"{year} - {timeline_data[year]['total_notes']} notes"):
                year_categories = timeline_data[year]["categories"]
                if year_categories:
                    cols = st.columns(min(len(year_categories), 4))
                    for idx, (cat, count) in enumerate(sorted(year_categories.items())):
                        with cols[idx % len(cols)]:
                            st.metric(
                                service.get_category_label(cat).split()[0],
                                count
                            )
                else:
                    st.write("No category counts available for this year.")

# ============= TAB 4: ALL NOTES =============
with tab4:
    st.header("All Notes - Advanced Filter")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        all_years = service.get_all_years(index)
        selected_years = st.multiselect("Years", ["All"] + all_years, default=["All"], key="all_years")
    
    with col2:
        categories = list(service.get_all_categories().keys())
        selected_categories = st.multiselect("Categories", categories, key="all_cats")
    
    with col3:
        all_tags = service.get_all_tags(index)
        selected_tags = st.multiselect("Tags", all_tags, key="all_tags")
    
    # Apply all filters
    filtered = service.filter_notes(
        index,
        years=selected_years if selected_years and "All" not in selected_years else None,
        categories=selected_categories if selected_categories else None,
        tags=selected_tags if selected_tags else None
    )
    
    st.markdown(f"### Results: {len(filtered)} / {len(index['notes'])} notes")
    
    if filtered:
        for note in sorted(filtered, key=lambda x: (x["year"], x["title"]), reverse=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{note['title']}** — {note['year']}")
            with col2:
                st.caption(note['source'])
            
            if note.get("tags"):
                tags_by_category = {}
                for tag in note["tags"]:
                    cat = service.analyzer.get_category_for_tag(tag)
                    if cat not in tags_by_category:
                        tags_by_category[cat] = []
                    tags_by_category[cat].append(tag)
                
                tag_cols = st.columns(min(3, len(tags_by_category)))
                for idx, (cat, tags) in enumerate(sorted(tags_by_category.items())):
                    with tag_cols[idx % len(tag_cols)]:
                        st.caption(f"**{service.get_category_label(cat).split()[0]}:** {', '.join(tags)}")
            
            st.markdown(note["excerpt"])
            st.markdown("---")
    else:
        st.info("No notes match the selected filters.")
