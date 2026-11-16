import zipfile
from io import BytesIO

import pytest
from docx import Document
from pptx import Presentation

from rag.ingest import extractors
from rag.ingest.extractors import (
    ExtractionError,
    extract_csv,
    extract_docx,
    extract_pptx,
    extract_upload_text,
)


def _docx_bytes() -> bytes:
    doc = Document()
    doc.add_paragraph("Quarterly plan for the search team.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Owner"
    table.cell(0, 1).text = "Goal"
    table.cell(1, 0).text = "Ada"
    table.cell(1, 1).text = "Ship phase two"
    doc.add_paragraph("Closing remarks.")
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _pptx_bytes() -> bytes:
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Roadmap"
    slide.placeholders[1].text = "Ship background jobs"
    slide.notes_slide.notes_text_frame.text = "Mention the quota"
    buffer = BytesIO()
    deck.save(buffer)
    return buffer.getvalue()


def test_docx_keeps_document_order_and_tables() -> None:
    text = extract_docx(_docx_bytes())
    assert text.index("Quarterly plan") < text.index("Ada | Ship phase two")
    assert text.index("Ada | Ship phase two") < text.index("Closing remarks")


def test_pptx_includes_slides_and_notes() -> None:
    text = extract_pptx(_pptx_bytes())
    assert "Slide 1" in text
    assert "Roadmap" in text
    assert "Ship background jobs" in text
    assert "Notes: Mention the quota" in text


def test_csv_rows_become_labelled_lines() -> None:
    text = extract_csv(b"name,role\nAda,Engineer\nGrace,Admiral\n")
    assert text.splitlines() == [
        "Row 1 - name: Ada; role: Engineer",
        "Row 2 - name: Grace; role: Admiral",
    ]


def test_csv_falls_back_to_windows_encoding() -> None:
    assert "José" in extract_csv(b"name\nJos\xe9\n")


def test_invalid_office_files_are_rejected() -> None:
    with pytest.raises(ExtractionError, match="Invalid Word file"):
        extract_docx(b"not a zip")
    with pytest.raises(ExtractionError, match="Invalid PowerPoint file"):
        extract_pptx(b"not a zip")


def test_archive_that_expands_too_far_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extractors, "MAX_UNZIPPED_BYTES", 100)
    with pytest.raises(ExtractionError, match="too large"):
        extract_docx(_docx_bytes())


def test_zip_without_office_parts_is_rejected() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "hi")
    with pytest.raises(ExtractionError):
        extract_docx(buffer.getvalue())


def test_extension_picks_the_reader_case_insensitively() -> None:
    assert extract_upload_text("NOTES.MD", "héllo wörld".encode()) == "héllo wörld"


def test_binary_garbage_is_rejected() -> None:
    with pytest.raises(ExtractionError):
        extract_upload_text("data.bin", b"\xff\xfe\x00\x81")


def test_text_over_the_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extractors, "MAX_EXTRACTED_CHARS", 10)
    with pytest.raises(ExtractionError) as excinfo:
        extract_upload_text("big.txt", b"x" * 50)
    assert excinfo.value.status_code == 413
