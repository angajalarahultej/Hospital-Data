# Simple Clinical Discharge Summary Agent

import argparse
import os
import re
import sys
from typing import List, Dict, Tuple
import io
from PIL import Image
import fitz
import pytesseract

# PDF text extraction using pdfminer.six (install via pip)

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF file using pdfminer.six, falling back to OCR if needed."""
    try:
        from pdfminer.high_level import extract_text
    except ImportError:
        sys.exit("pdfminer.six is required. Install it via 'pip install pdfminer.six' and re-run.")
    text = extract_text(pdf_path)
    if text.strip():
        return text
    # Fallback to OCR for image‑based PDFs
    print("PDF appears to be image‑based – falling back to OCR…")
    return ocr_extract(pdf_path)


def parse_section(text: str, heading: str) -> str:
    """Very naive section parser.
    Looks for a line starting with the heading (case‑insensitive) and captures
    subsequent lines until another heading (all caps line) or end of text.
    """
    pattern = re.compile(rf"^{heading}:?\s*$", re.IGNORECASE | re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return ""
    start = matches[0].end()
    # Find next all‑caps line as a simple delimiter
    delimiter = re.compile(r"^[A-Z][A-Z\s]+$", re.MULTILINE)
    rest = text[start:]
    delim_match = delimiter.search(rest)
    end = delim_match.start() if delim_match else len(rest)
    return rest[:end].strip()


def extract_fields(texts: List[str]) -> Dict[str, str]:
    """Extract required fields from a list of document texts.
    Returns a dict with keys as field names.
    """
    data: Dict[str, str] = {}
    fields = [
        "Patient Name",
        "Age",
        "Gender",
        "Admission Date",
        "Discharge Date",
        "Diagnosis",
        "Secondary Diagnosis",
        "Hospital Course",
        "Procedures",
        "Allergies",
        "Medications",
        "Follow‑up Instructions",
        "Pending Results",
        "Discharge Condition",
    ]
    for txt in texts:
        for field in fields:
            if field not in data or not data[field]:
                content = parse_section(txt, field)
                if content:
                    data[field] = content
    return data


def detect_missing(data: Dict[str, str]) -> List[str]:
    missing = []
    for key, val in data.items():
        if not val:
            missing.append(key)
    return missing


def detect_conflicts(data_lists: List[Dict[str, str]]) -> List[Tuple[str, str, str]]:
    """Detect simple conflicts across multiple docs.
    Returns list of (field, value1, value2) where values differ.
    """
    conflicts = []
    if not data_lists:
        return conflicts
    base = data_lists[0]
    for other in data_lists[1:]:
        for key in base.keys():
            v1 = base.get(key, "")
            v2 = other.get(key, "")
            if v1 and v2 and v1 != v2:
                conflicts.append((key, v1, v2))
    return conflicts


def parse_medications(text: str) -> Dict[str, str]:
    """Very simple medication parser – expects lines like 'Drug: dose'."""
    meds: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            drug, dose = map(str.strip, line.split(":", 1))
            meds[drug] = dose
    return meds


def compare_medications(adm_txt: str, dis_txt: str) -> Tuple[List[str], List[str], List[Tuple[str, str, str]]]:
    adm = parse_medications(adm_txt)
    dis = parse_medications(dis_txt)
    added = [f"{d}: {dose}" for d, dose in dis.items() if d not in adm]
    removed = [f"{d}: {dose}" for d, dose in adm.items() if d not in dis]
    changed: List[Tuple[str, str, str]] = []
    for d in adm:
        if d in dis and adm[d] != dis[d]:
            changed.append((d, adm[d], dis[d]))
    return added, removed, changed


def ocr_extract(pdf_path: str) -> str:
    """Render each PDF page to an image and run Tesseract OCR.
    Requires `pymupdf`, `pillow`, and `pytesseract` to be installed.
    """
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        pix = page.get_pixmap()
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        page_text = pytesseract.image_to_string(img)
        texts.append(page_text)
    doc.close()
    return "\n".join(texts)

def generate_summary(data: Dict[str, str]) -> str:
    sections = [
        "Patient Demographics",
        "Admission Date",
        "Discharge Date",
        "Principal Diagnosis",
        "Secondary Diagnoses",
        "Hospital Course",
        "Procedures",
        "Allergies",
        "Discharge Medications",
        "Medication Changes",
        "Follow‑up Instructions",
        "Pending Results",
        "Discharge Condition",
    ]
    out = []
    out.append("=== Discharge Summary Draft ===\n")
    mapping = {
        "Patient Demographics": lambda d: f"Name: {d.get('Patient Name') or 'Not Documented - Requires Clinician Review'}\nAge: {d.get('Age') or 'Not Documented - Requires Clinician Review'}\nGender: {d.get('Gender') or 'Not Documented - Requires Clinician Review'}",
      
        "Admission Date": lambda d: d.get('Admission Date') or 'Not Documented - Requires Clinician Review',
        "Discharge Date": lambda d: d.get('Discharge Date') or 'Not Documented - Requires Clinician Review',
        "Principal Diagnosis": lambda d: d.get('Diagnosis') or 'Not Documented - Requires Clinician Review',
        "Secondary Diagnoses": lambda d: d.get('Secondary Diagnosis') or 'Not Documented - Requires Clinician Review',
        "Hospital Course": lambda d: d.get('Hospital Course') or 'Not Documented - Requires Clinician Review',
        "Procedures": lambda d: d.get('Procedures') or 'Not Documented - Requires Clinician Review',
        "Allergies": lambda d: d.get('Allergies') or 'Not Documented - Requires Clinician Review',
        "Discharge Medications": lambda d: d.get('Medications') or 'Not Documented - Requires Clinician Review',
        "Medication Changes": lambda d: "(See Medication Reconciliation Report)",
        "Follow‑up Instructions": lambda d: d.get('Follow‑up Instructions') or 'Not Documented - Requires Clinician Review',
        "Pending Results": lambda d: d.get('Pending Results') or 'None',
        "Discharge Condition": lambda d: d.get('Discharge Condition') or 'Not Documented - Requires Clinician Review',
    }
    for sec in sections:
        out.append(f"--- {sec} ---")
        out.append(mapping[sec](data))
        out.append("")
    out.append("Clinician Review Required")
    return "\n".join(out)


def write_report(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Simple Clinical Discharge Summary Agent")
    parser.add_argument("pdfs", nargs="+", help="List of PDF files (Admission, Progress, Lab, Medication, Discharge)")
    parser.add_argument("--outdir", default="output", help="Directory for generated reports")
    parser.add_argument("--ocr", action="store_true", help="Force OCR extraction even if PDFminer finds text")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    texts = []
    for pdf in args.pdfs:
        if args.ocr:
            txt = ocr_extract(pdf)
        else:
            txt = extract_text_from_pdf(pdf)
        texts.append(txt)

    data = extract_fields(texts)

    trace_steps = []
    trace_steps.append("Step 1: Read PDFs")
    trace_steps.append(f"Read {len(args.pdfs)} PDFs")
    trace_steps.append("Step 2: Extract Demographics and core fields")
    for k in ["Patient Name", "Age", "Gender", "Admission Date", "Discharge Date", "Diagnosis", "Secondary Diagnosis"]:
        trace_steps.append(f"{k}: {'Found' if data.get(k) else 'Missing'}")
    trace_steps.append("Step 3: Detect Missing Data")
    missing = detect_missing(data)
    trace_steps.append(f"Missing fields: {', '.join(missing) if missing else 'None'}")
    trace_steps.append("Step 4: Detect Conflicts")
    conflicts = detect_conflicts([extract_fields([t]) for t in texts])
    conflict_str = ", ".join([c[0] for c in conflicts]) if conflicts else "None"
    trace_steps.append(f"Conflicts: {conflict_str}")
    trace_steps.append("Step 5: Medication Reconciliation")
    adm_meds_txt = parse_section(texts[0], "Medications")
    dis_meds_txt = parse_section(texts[-1], "Medications")
    added, removed, changed = compare_medications(adm_meds_txt, dis_meds_txt)
    trace_steps.append(f"Added: {', '.join(added) if added else 'None'}")
    trace_steps.append(f"Removed: {', '.join(removed) if removed else 'None'}")
    trace_steps.append(f"Changed: {', '.join([f'{d} ({old}->{new})' for d, old, new in changed]) if changed else 'None'}")
    trace_steps.append("Step 6: Generate Summary")

    summary = generate_summary(data)
    write_report(os.path.join(args.outdir, "discharge_summary.txt"), summary)
    write_report(os.path.join(args.outdir, "trace_log.txt"), "\n".join(trace_steps))
    conflict_report = "".join([f"{field}: \n- {v1} \n- {v2} \n- Conflict Detected - Requires Clinician Review\n\n" for field, v1, v2 in conflicts]) or "No conflicts detected."
    write_report(os.path.join(args.outdir, "conflict_report.txt"), conflict_report)
    med_report_lines = []
    if added:
        med_report_lines.append("Added Medications:\n" + "\n".join(added))
    if removed:
        med_report_lines.append("Removed Medications:\n" + "\n".join(removed))
    if changed:
        ch_lines = [f"{drug}: {old} -> {new}" for drug, old, new in changed]
        med_report_lines.append("Changed Medications:\n" + "\n".join(ch_lines))
    if not med_report_lines:
        med_report_lines.append("No medication changes detected.")
    write_report(os.path.join(args.outdir, "medication_reconciliation.txt"), "\n\n".join(med_report_lines))

    print("Reports generated in", args.outdir)

if __name__ == "__main__":
    main()
