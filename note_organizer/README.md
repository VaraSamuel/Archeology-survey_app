# Field Notes Organizer

A small Python/Streamlit app to scan your ethnographic field notes, extract text from `.txt` and `.docx` files, infer year metadata, and generate topic tags.

## Install

```bash
cd /Users/samuelvara/Downloads/Field_Notes_Ethnography/note_organizer
python3 -m pip install -r requirements.txt
python3 -m spacy download en_core_web_sm
```

## Run

```bash
streamlit run app.py
```

## Usage

1. Enter the folder containing your field notes (e.g. `..` or the dataset root).
2. Click `Scan notes`.
3. Use the sidebar to filter by year and topic.
4. Click any tag to filter the note list.

## Notes

- The app reads `.txt` and `.docx` files.
- `.doc` support depends on `antiword` being installed on your machine.
- Optionally, set `OPENAI_API_KEY` in the app or environment to use OpenAI for richer tag extraction.
