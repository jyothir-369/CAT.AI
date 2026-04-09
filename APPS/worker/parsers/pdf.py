"""
PDF parser — tries pdfminer.six first, falls back to PyMuPDF (fitz).
"""
from typing import Optional


def parse_pdf(raw_bytes: bytes) -> str:
    """
    Extract text from PDF bytes.
    Returns plain text string.
    """
    text = _parse_with_pdfminer(raw_bytes)
    if not text or len(text.strip()) < 50:
        text = _parse_with_pymupdf(raw_bytes)
    return text or ""


def _parse_with_pdfminer(raw_bytes: bytes) -> Optional[str]:
    """pdfminer.six — best text extraction for text-based PDFs."""
    try:
        from io import BytesIO
        from pdfminer.high_level import extract_text as pdfminer_extract

        text = pdfminer_extract(BytesIO(raw_bytes))
        return text
    except ImportError:
        print("[Parser/PDF] pdfminer not installed — skipping")
        return None
    except Exception as exc:
        print(f"[Parser/PDF] pdfminer failed: {exc}")
        return None


def _parse_with_pymupdf(raw_bytes: bytes) -> Optional[str]:
    """PyMuPDF (fitz) — fallback, handles more PDF types including scanned."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        print("[Parser/PDF] PyMuPDF not installed — skipping")
        return None
    except Exception as exc:
        print(f"[Parser/PDF] PyMuPDF failed: {exc}")
        return None