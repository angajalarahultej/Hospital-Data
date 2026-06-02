import fitz
import io
import shutil
import os

# Optional OCR imports – they may be missing if Tesseract is not installed.
try:
    from PIL import Image
    import pytesseract
    # Locate tesseract binary (Homebrew may install under /opt/homebrew/bin on Apple Silicon)
    _tesseract_path = shutil.which("tesseract")
    if not _tesseract_path:
        possible = "/opt/homebrew/bin/tesseract"
        if os.path.exists(possible):
            _tesseract_path = possible
    if not _tesseract_path:
        raise RuntimeError("Tesseract OCR executable not found. Install via Homebrew: 'brew install tesseract'")
    pytesseract.pytesseract.tesseract_cmd = _tesseract_path
except Exception:
    Image = None
    pytesseract = None


def _extract_with_fitz(pdf_path: str) -> str:
    """Extract text using PyMuPDF (fitz)."""
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        txt = page.get_text()
        if txt:
            texts.append(txt)
    doc.close()
    return "\n".join(texts)


def _extract_with_ocr(pdf_path: str) -> str:
    """Fallback OCR extraction using pytesseract.
    Renders each page at ~300 dpi for better OCR accuracy.
    """
    if Image is None or pytesseract is None:
        return ""

    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        try:
            # Use a moderate scaling factor (~2.5) to keep DPI around 300 while being faster.
            matrix = fitz.Matrix(2.5, 2.5)
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            txt = pytesseract.image_to_string(img)
            if txt:
                texts.append(txt)
        except Exception as e:
            print(f"OCR extraction error on page {page.number}: {e}")
    doc.close()
    return "\n".join(texts)


def extract_text(pdf_path: str) -> str:
    """Extract raw text (PDF text + OCR fallback)."""
    raw = _extract_with_fitz(pdf_path).strip()
    if raw:
        return raw
    # OCR fallback
    return _extract_with_ocr(pdf_path).strip()
