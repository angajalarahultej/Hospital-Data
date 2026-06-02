import os
import json
from pathlib import Path

# Import extractor and parser from top‑level modules
from extractor import extract_text  # noqa: E402
from pdf_parser import parse_discharge_summary  # noqa: E402



INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"

def ensure_directories():
    """Create input and output folders if they do not exist."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def process_pdf(pdf_path: Path):
    """Run the full extraction → parsing pipeline for a single PDF.

    Returns a tuple ``(data_dict, summary_text)`` where ``data_dict`` is the
    structured JSON representation and ``summary_text`` is a human‑readable
    multi‑line string.
    """
    # 1️⃣ Extract raw text (PDF text + OCR fallback)
    raw_text = extract_text(str(pdf_path))

    # 2️⃣ Parse the raw text into a structured dict
    data = parse_discharge_summary(raw_text)

    # 3️⃣ Build a simple plain‑text summary for the terminal / summary.txt
    lines = []
    lines.append(f"Patient Name : {data.get('patient_name', 'N/A')}")
    lines.append(f"Age          : {data.get('age', 'N/A')}")
    lines.append(f"Gender       : {data.get('gender', 'N/A')}")
    lines.append(f"Admission    : {data.get('admission_date', 'N/A')}")
    lines.append(f"Discharge    : {data.get('discharge_date', 'N/A')}")
    lines.append("\nDiagnosis:")
    for d in data.get('diagnosis', []):
        lines.append(f"  - {d}")
    lines.append("\nHospital Course:\n" + data.get('hospital_course', 'N/A'))
    lines.append("\nMedications:")
    for m in data.get('medications', []):
        lines.append(f"  - {m.get('name')} – {m.get('frequency')} – {m.get('duration')}")
    lines.append("\nFollow‑up Instructions:")
    for fu in data.get('follow_up', []):
        lines.append(f"  - {fu}")
    summary_text = "\n".join(lines)
    return data, summary_text

def write_outputs(pdf_name: str, data: dict, summary: str):
    """Write ``output.json`` and ``summary.txt`` into the output directory.
    The files are named after the source PDF (without extension) to avoid
    collisions when multiple PDFs are processed.
    """
    base_name = Path(pdf_name).stem
    json_path = OUTPUT_DIR / f"{base_name}_output.json"
    txt_path = OUTPUT_DIR / f"{base_name}_summary.txt"

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as tf:
        tf.write(summary)

    print(f"✅ Generated: {json_path.name} & {txt_path.name}\n")

def main():
    ensure_directories()
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"📂 No PDF files found in '{INPUT_DIR}'. Place PDFs there and re‑run.")
        return

    for pdf_path in pdf_files:
        print(f"\n🚀 Processing: {pdf_path.name}")
        try:
            data, summary = process_pdf(pdf_path)
            # Print a concise summary to the terminal
            print("--- Extracted Summary ---")
            print(summary)
            # Persist results
            write_outputs(pdf_path.name, data, summary)
        except Exception as e:
            print(f"❌ Failed to process {pdf_path.name}: {e}")

if __name__ == "__main__":
    main()
