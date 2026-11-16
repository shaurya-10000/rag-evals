"""Turn uploaded files into plain text that can be chunked and embedded."""

import csv
import zipfile
from contextlib import suppress
from io import BytesIO, StringIO
from typing import Any

from docx import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from pptx import Presentation
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError

from rag.api.vision import VisionError, describe_image

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Same ceiling as editing a document, so anything ingested can also be edited later.
MAX_EXTRACTED_CHARS = 500_000
MAX_UNZIPPED_BYTES = 100 * 1024 * 1024
MAX_ZIP_ENTRIES = 5_000

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
UPLOAD_EXTENSIONS = (
    ".pdf",
    ".docx",
    ".pptx",
    ".csv",
    ".txt",
    ".md",
    ".markdown",
    *IMAGE_EXTENSIONS,
)


class ExtractionError(Exception):
    """A document could not be read. The message is safe to show to the user."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def limit_text(text: str) -> str:
    if len(text.strip()) > MAX_EXTRACTED_CHARS:
        raise ExtractionError(
            f"This document has too much text (limit {MAX_EXTRACTED_CHARS:,} characters). "
            "Split it into smaller files.",
            status_code=413,
        )
    return text


def decode_text(contents: bytes, *, allow_cp1252: bool = False) -> str:
    encodings = ("utf-8-sig", "cp1252") if allow_cp1252 else ("utf-8-sig",)
    for encoding in encodings:
        try:
            return contents.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("File must be UTF-8 text, PDF, or Image")


def _check_zip(contents: bytes, label: str) -> None:
    """Refuse archives that would expand into something huge (zip bombs)."""
    try:
        with zipfile.ZipFile(BytesIO(contents)) as archive:
            entries = archive.infolist()
    except zipfile.BadZipFile as e:
        raise ExtractionError(f"Invalid {label} file") from e
    if len(entries) > MAX_ZIP_ENTRIES or sum(i.file_size for i in entries) > MAX_UNZIPPED_BYTES:
        raise ExtractionError(f"This {label} file is too large to process.", status_code=413)


def extract_pdf(contents: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(contents))
        pages = (page.extract_text() for page in reader.pages)
        text = "\n".join(page for page in pages if page)
    except FileNotDecryptedError as e:
        raise ExtractionError("This PDF is password protected.") from e
    except Exception as e:
        raise ExtractionError("Invalid PDF file") from e
    return limit_text(text)


def _table_lines(table: Any) -> list[str]:
    lines: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            text = " ".join(str(cell.text).split())
            # Merged cells repeat the same text; keep it once.
            if text and (not cells or cells[-1] != text):
                cells.append(text)
        if cells:
            lines.append(" | ".join(cells))
    return lines


def extract_docx(contents: bytes) -> str:
    _check_zip(contents, "Word")
    lines: list[str] = []
    try:
        doc: Any = DocxDocument(BytesIO(contents))
        # Walk the body in order so tables stay next to the text around them.
        for child in doc.element.body.iterchildren():
            kind = str(child.tag).rsplit("}", 1)[-1]
            if kind == "p":
                text = str(Paragraph(child, doc).text).strip()
                if text:
                    lines.append(text)
            elif kind == "tbl":
                lines.extend(_table_lines(Table(child, doc)))
    except Exception as e:
        raise ExtractionError("Invalid Word file") from e
    return limit_text("\n".join(lines))


def _shape_lines(shape: Any) -> list[str]:
    lines: list[str] = []
    if getattr(shape, "has_text_frame", False):
        text = str(shape.text_frame.text).strip()
        if text:
            lines.append(text)
    if getattr(shape, "has_table", False):
        lines.extend(_table_lines(shape.table))
    for child in getattr(shape, "shapes", []):  # grouped shapes
        lines.extend(_shape_lines(child))
    return lines


def extract_pptx(contents: bytes) -> str:
    _check_zip(contents, "PowerPoint")
    sections: list[str] = []
    try:
        deck: Any = Presentation(BytesIO(contents))
        for number, slide in enumerate(deck.slides, start=1):
            lines: list[str] = []
            for shape in slide.shapes:
                lines.extend(_shape_lines(shape))
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
                notes = str(slide.notes_slide.notes_text_frame.text).strip()
                if notes:
                    lines.append(f"Notes: {notes}")
            if lines:
                sections.append(f"Slide {number}\n" + "\n".join(lines))
    except Exception as e:
        raise ExtractionError("Invalid PowerPoint file") from e
    return limit_text("\n\n".join(sections))


def _column_name(header: list[str], index: int) -> str:
    return header[index] if index < len(header) and header[index] else f"column {index + 1}"


def extract_csv(contents: bytes) -> str:
    """Each row becomes 'Row N - column: value; ...' so it embeds and cites well."""
    text = decode_text(contents, allow_cp1252=True)
    dialect: Any = csv.excel
    with suppress(csv.Error):
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    try:
        rows = [r for r in csv.reader(StringIO(text), dialect) if any(c.strip() for c in r)]
    except csv.Error as e:
        raise ExtractionError("Invalid CSV file") from e
    if not rows:
        return ""

    header = [h.strip() for h in rows[0]]
    lines: list[str] = []
    for number, row in enumerate(rows[1:], start=1):
        pairs = [
            f"{_column_name(header, i)}: {value.strip()}"
            for i, value in enumerate(row)
            if value.strip()
        ]
        if pairs:
            lines.append(f"Row {number} - " + "; ".join(pairs))
    return limit_text("\n".join(lines or [" | ".join(h for h in header if h)]))


def _describe(filename: str, contents: bytes) -> str:
    try:
        return describe_image(filename, contents)
    except VisionError as e:
        raise ExtractionError(str(e), status_code=500) from e


def extract_upload_text(filename: str, contents: bytes) -> str:
    """Extract text from an uploaded file, choosing the reader by extension."""
    name = filename.lower()
    if name.endswith(".pdf"):
        return extract_pdf(contents)
    if name.endswith(".docx"):
        return extract_docx(contents)
    if name.endswith(".pptx"):
        return extract_pptx(contents)
    if name.endswith(".csv"):
        return extract_csv(contents)
    if name.endswith(IMAGE_EXTENSIONS):
        return _describe(name, contents)
    return limit_text(decode_text(contents))
