"""
Document extraction service — converts raw bytes from any supported format
into clean UTF-8 plain text.

Supported formats:
  .txt  — direct UTF-8 decode
  .pdf  — pdfplumber (native text layer)
  .png / .jpg / .jpeg / .tiff — pytesseract OCR
"""
import io
import os
from pathlib import Path

# ── Tesseract path resolution ─────────────────────────────────────────
# Explicitly set the Tesseract executable path for Windows so that uvicorn
# doesn't need a full process restart after installation.
import pytesseract as _tess

_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\T995279\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]
for _candidate in _TESSERACT_CANDIDATES:
    if Path(_candidate).exists():
        _tess.pytesseract.tesseract_cmd = _candidate
        break


def extract_text(filename: str, file_bytes: bytes) -> str:
    """
    Extract plain text from raw file bytes.

    Args:
        filename:   Original filename (used only to determine format).
        file_bytes: Raw bytes of the file content.

    Returns:
        Extracted text as a UTF-8 string, stripped of excess whitespace.

    Raises:
        ValueError: If the file extension is not supported.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        return _extract_txt(file_bytes)
    elif ext == ".pdf":
        return _extract_pdf(file_bytes)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        return _extract_image(file_bytes)
    else:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            "Supported types: .txt, .pdf, .png, .jpg, .jpeg, .tiff"
        )


def _extract_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace").strip()


def _extract_pdf(file_bytes: bytes) -> str:
    import pdfplumber  # lazy import — only required if PDF is encountered

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())

    return "\n\n".join(text_parts)


def _extract_image(file_bytes: bytes) -> str:
    from PIL import Image

    image = Image.open(io.BytesIO(file_bytes))

    # --psm 6 = assume a single uniform block of text (good for scanned faxes/forms)
    custom_config = r"--oem 3 --psm 6"
    raw = _tess.image_to_string(image, config=custom_config)
    return raw.strip()
