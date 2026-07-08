"""Small shared helpers: saving generated markdown, trimming chat history, extracting resume text."""
import io
import os
from datetime import datetime
from langchain_core.messages import trim_messages

OUTPUT_FOLDER = "EquiSkill_output"


def save_markdown(content: str, label: str) -> str:
    """Saves generated content to a timestamped .md file and returns its path."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{label}_{timestamp}.md"
    path = os.path.join(OUTPUT_FOLDER, filename)
    cleaned = str(content).replace("```markdown", "").strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(cleaned)
    return path


def trim_conversation(messages, max_messages: int = 10):
    """Keeps only the most recent messages so the prompt doesn't grow unbounded."""
    return trim_messages(
        messages,
        max_tokens=max_messages,
        strategy="last",
        token_counter=len,
        start_on="human",
        include_system=True,
        allow_partial=False,
    )


def extract_resume_text(uploaded_file) -> str:
    """
    Extract plain text from an uploaded resume file (PDF, DOCX, or TXT).
    Works with Streamlit's UploadedFile objects.
    """
    filename = uploaded_file.name.lower()
    raw_bytes = uploaded_file.read()

    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as e:
            return f"(Could not parse PDF: {e})"

    elif filename.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(raw_bytes))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as e:
            return f"(Could not parse DOCX: {e})"

    else:
        # Plain text fallback
        try:
            return raw_bytes.decode("utf-8", errors="replace").strip()
        except Exception as e:
            return f"(Could not read file: {e})"
