import re
from typing import List, Dict


def _clean_line(line: str) -> str:
    """Trim whitespace from a line."""
    return line.strip()


def _build_heading_regex(heading: str) -> re.Pattern:
    """
    Return a regex that matches a whole line containing *heading* (case‑insensitive).
    The heading may optionally end with a colon.
    """
    return re.compile(rf"^\s*{re.escape(heading)}\s*:?.*$", re.IGNORECASE | re.MULTILINE)


def extract_name(text: str) -> str:
    """Extract patient name."""
    # Match lines like "Patient Name: John Doe" or "Name : Jane" but avoid "Medication Name"
    match = re.search(r"^\s*(?:Patient\s+Name|Full\s+Name|Name)\s*[:\-\–]\s*(.+)", text, re.IGNORECASE | re.MULTILINE)
    if match:
        name = _clean_line(match.group(1))
        # Filter out common false positives
        if name.upper() == "AGE/GENDER" or "FREQUENCY" in name.upper() or "MEDICATION" in name.upper():
            return "Not Found"
        return name
    return "Not Found"


def extract_age(text: str) -> str:
    """Extract patient age (numeric)."""
    match = re.search(r"\bAge\s*[:\-\–]?\s*(\d{1,3})", text, re.IGNORECASE)
    return match.group(1) if match else "Not Found"


def extract_gender(text: str) -> str:
    """Extract gender (Male/Female)."""
    match = re.search(r"Gender\s*[:\-\–]?\s*(Male|Female|M|F)\b", text, re.IGNORECASE)
    if not match:
        return "Not Documented - Requires Clinician Review"
    g = match.group(1).upper()
    return "Male" if g.startswith("M") else "Female"


def extract_date(field: str, text: str) -> str:
    """Extract a date after a given heading."""
    heading_regex = _build_heading_regex(field)
    m = heading_regex.search(text)
    if not m:
        return "Not Documented - Requires Clinician Review"
    after = text[m.end():]
    for line in after.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.search(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", line):
            return line
    return "Not Documented - Requires Clinician Review"


def extract_diagnosis(text: str) -> List[str]:
    """Extract diagnoses listed under 'Principal Diagnosis' or 'DIAGNOSIS'."""
    start_regex = re.compile(r"^\s*(?:Principal\s+)?Diagnosis\s*:?.*$", re.IGNORECASE | re.MULTILINE)
    end_regex = re.compile(r"^\s*(HISTORY|PAST HISTORY|COURSE|MEDICATIONS|DISCHARGE|FOLLOW)", re.IGNORECASE | re.MULTILINE)
    m = start_regex.search(text)
    if not m:
        return []
    segment = text[m.end():]
    end_match = end_regex.search(segment)
    if end_match:
        segment = segment[: end_match.start()]
    diagnoses: List[str] = []
    for line in segment.splitlines():
        line = line.strip()
        if not line:
            continue
        # Numbered or bulleted list
        if re.match(r"^[\d\-\*]+[\)\.]?\s+", line):
            diagnoses.append(line.split(maxsplit=1)[1].strip())
        elif line.isupper() and len(line.split()) > 1:
            diagnoses.append(line.title())
    return diagnoses


def extract_hospital_course(text: str) -> str:
    """Extract the hospital course section. Accept headings: 'COURSE IN THE HOSPITAL' or 'Hospital Course'."""
    start_regex = _build_heading_regex("COURSE IN THE HOSPITAL")
    fallback_regex = _build_heading_regex("Hospital Course")
    m = start_regex.search(text) or fallback_regex.search(text)
    if not m:
        return "Not Documented - Requires Clinician Review"
    segment = text[m.end():]
    end_regex = re.compile(r"^\s*(DISCHARGE CONDITION|CONDITION AT DISCHARGE|FOLLOW|ADVICE ON DISCHARGE|MEDICATIONS)", re.IGNORECASE | re.MULTILINE)
    end_match = end_regex.search(segment)
    if end_match:
        segment = segment[: end_match.start()]
    return " ".join([_clean_line(l) for l in segment.splitlines() if _clean_line(l)])


def extract_medications(text: str) -> List[Dict[str, str]]:
    """Extract medication table. Expected format: name frequency duration (e.g., 'RACIPER 1-0-0 7 DAYS')."""
    start_regex = re.compile(r"^\s*(Discharge Medications|ADVICE ON DISCHARGE|Medications?)\s*:?.*$", re.IGNORECASE | re.MULTILINE)
    end_regex = re.compile(r"^\s*(FOLLOW|DISCHARGE CONDITION|CONDITION AT DISCHARGE)", re.IGNORECASE | re.MULTILINE)
    m = start_regex.search(text)
    if not m:
        return []
    segment = text[m.end():]
    end_match = end_regex.search(segment)
    if end_match:
        segment = segment[: end_match.start()]
    meds: List[Dict[str, str]] = []
    for line in segment.splitlines():
        line = line.strip()
        # Filter out table headers or junk OCR noise
        if not line or "Medication Name" in line or "Duration" in line or len(line) < 5:
            continue
        # Clean up stray characters from OCR at the start of lines
        line = re.sub(r"^[\s=\-\|sZa]+", "", line)
        parts = line.split()
        if len(parts) >= 3:
            # Reconstruct the name, frequency, duration more robustly
            # Often frequency is like 1-0-0
            freq_idx = -1
            for i, p in enumerate(parts):
                if re.match(r"^\d+-\d+-\d+$", p):
                    freq_idx = i
                    break
            
            if freq_idx > 0:
                name = " ".join(parts[:freq_idx]).replace(".", "").strip()
                frequency = parts[freq_idx]
                duration = " ".join(parts[freq_idx+1:]).strip()
            else:
                name = parts[0].replace(".", "")
                frequency = parts[1]
                duration = " ".join(parts[2:])
            
            meds.append({"name": name, "frequency": frequency, "duration": duration})
    return meds


def extract_follow_up(text: str) -> List[str]:
    """Extract follow‑up instructions."""
    start_regex = _build_heading_regex("Follow‑up Instructions")
    if not start_regex.search(text):
        start_regex = _build_heading_regex("Follow up Instructions")
    end_regex = re.compile(r"^\s*(DISCHARGE CONDITION|CONDITION AT DISCHARGE)", re.IGNORECASE | re.MULTILINE)
    m = start_regex.search(text)
    if not m:
        return []
    segment = text[m.end():]
    end_match = end_regex.search(segment)
    if end_match:
        segment = segment[: end_match.start()]
    bullet_items: List[str] = []
    for line in segment.splitlines():
        line = line.strip()
        if not line:
            continue
        bullet_items.append(line)
    return bullet_items


def parse_discharge_summary(raw_text: str) -> Dict[str, object]:
    """Parse raw OCR / PDF text into a structured dict."""
    data = {
        "patient_name": extract_name(raw_text),
        "age": extract_age(raw_text),
        "gender": extract_gender(raw_text),
        "admission_date": extract_date("Admission Date", raw_text),
        "discharge_date": extract_date("Discharge Date", raw_text),
        "diagnosis": extract_diagnosis(raw_text),
        "hospital_course": extract_hospital_course(raw_text),
        "medications": extract_medications(raw_text),
        "follow_up": extract_follow_up(raw_text),
    }
    return data
