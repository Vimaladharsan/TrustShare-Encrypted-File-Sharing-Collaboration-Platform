"""Which files are allowed, and checking that a file's content really matches its extension.

A file's extension is just part of its name – anyone can rename virus.exe to report.pdf.
So the first bytes ("magic bytes") and, for Office files, the inside of the ZIP are checked too.
"""

import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileType:
    mime_type: str
    category: str  # used for filters and icons in the dashboard


# Allow-list: anything not listed here is rejected.
ALLOWED_TYPES: dict[str, FileType] = {
    "pdf": FileType("application/pdf", "document"),
    "docx": FileType(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"
    ),
    "xlsx": FileType(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "spreadsheet"
    ),
    "csv": FileType("text/csv", "spreadsheet"),
    "pptx": FileType(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "presentation",
    ),
    "png": FileType("image/png", "image"),
    "jpg": FileType("image/jpeg", "image"),
    "jpeg": FileType("image/jpeg", "image"),
    "txt": FileType("text/plain", "text"),
}

ALLOWED_EXTENSIONS_TEXT = "PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG"

# Signatures at the very start of each format.
MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "docx": (b"PK\x03\x04",),  # Office files are ZIP archives
    "xlsx": (b"PK\x03\x04",),
    "pptx": (b"PK\x03\x04",),
}

# A real Word/Excel/PowerPoint file contains this part inside its ZIP.
OFFICE_MAIN_PART = {
    "docx": "word/document.xml",
    "xlsx": "xl/workbook.xml",
    "pptx": "ppt/presentation.xml",
}


def clean_filename(raw: str | None) -> str:
    """Safe display name. It is only ever shown to people – never used as a path on disk."""
    name = (raw or "").replace("\\", "/").split("/")[-1]  # drop any folder parts like ../../
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")  # control chars
    name = re.sub(r"\s+", " ", name).strip(" .")
    if len(name) > 255:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 250 - len(ext)] + dot + ext) if dot else name[:255]
    return name


def extension_of(name: str) -> str:
    return name.rpartition(".")[2].lower() if "." in name else ""


def content_matches(extension: str, head: bytes) -> bool:
    """Check the first bytes of the file against the expected signature."""
    if extension in MAGIC_BYTES:
        return head.startswith(MAGIC_BYTES[extension])
    # TXT / CSV have no signature: require readable text (no NUL bytes, valid UTF-8).
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:
        # The first chunk may end in the middle of a multi-byte character; that's fine.
        return exc.start >= len(head) - 3
    return True


def office_structure_ok(extension: str, path: Path) -> bool:
    """For DOCX/XLSX/PPTX, open the ZIP and look for the format's main part."""
    part = OFFICE_MAIN_PART.get(extension)
    if part is None:
        return True
    try:
        with zipfile.ZipFile(path) as archive:
            return part in archive.namelist()
    except zipfile.BadZipFile:
        return False
