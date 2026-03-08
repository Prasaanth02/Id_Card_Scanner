import re
import logging

logger = logging.getLogger(__name__)

def extract_fields(ocr_results, raw_text_full):
    """
    Intelligently extracts fields from OCR text using regex and heuristics.
    Works for plain ID cards with no strict formatting.
    """
    extracted = {
        "name": None,
        "roll_number": None,
        "validity": None,
        "department": None,
        "institution": None,
        "_confidence_scores": {
            "name": 0.0,
            "roll_number": 0.0,
            "validity": 0.0,
            "department": 0.0,
            "institution": 0.0,
        }
    }
    
    # Pre-process lines
    lines = raw_text_full.split("\n")
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    
    # 1. Extract Roll Number / ID Number
    # Heuristic: alphanumeric strings 4–15 chars that contain at least one digit.
    # Matches patterns like 21CS045, RA2211003011632, 2023001, etc.
    roll_pattern = re.compile(r'\b[A-Za-z0-9]{4,15}\b')
    roll_label_pattern = re.compile(r'(roll|reg|id|register|admission|enrol)\s*[.:# -]*\s*(\S+)', re.IGNORECASE)

    # First try: look for labelled roll numbers ("Roll No: 21CS045")
    for line in cleaned_lines:
        m = roll_label_pattern.search(line)
        if m:
            candidate = m.group(2).strip().rstrip('.,;')
            if roll_pattern.fullmatch(candidate) and any(c.isdigit() for c in candidate):
                extracted["roll_number"] = candidate.upper()
                extracted["_confidence_scores"]["roll_number"] = 0.95
                logger.info("Roll number (labelled): %s", candidate)
                break

    # Second try: look for standalone alphanumeric tokens with digits
    if not extracted["roll_number"]:
        for line in cleaned_lines:
            for word in line.split():
                clean = word.strip('.,;:()[]')
                if roll_pattern.fullmatch(clean) and any(c.isdigit() for c in clean):
                    # Reject pure years like 2024, 2025
                    if re.fullmatch(r'\d{4}', clean) and 1900 <= int(clean) <= 2100:
                        continue
                    extracted["roll_number"] = clean.upper()
                    extracted["_confidence_scores"]["roll_number"] = 0.85
                    logger.info("Roll number (heuristic): %s", clean)
                    break
            if extracted["roll_number"]:
                break

    # 2. Extract Validity / Expiry Date of the ID Card
    # Matches DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD, MM-YYYY, etc.
    date_pattern = re.compile(r'\b(\d{2}[-/\.]\d{2}[-/\.]\d{4}|\d{4}[-/\.]\d{2}[-/\.]\d{2}|\d{2}[-/\.]\d{4})\b')
    validity_keywords = re.compile(r'(valid|validity|expir|expires|expiry|upto|thru|through)', re.IGNORECASE)

    # First try: find a date on a line that mentions validity/expiry
    for line in cleaned_lines:
        if validity_keywords.search(line):
            match = date_pattern.search(line)
            if match:
                extracted["validity"] = match.group(0)
                extracted["_confidence_scores"]["validity"] = 0.95
                logger.info("Validity (keyword match): %s", match.group(0))
                break

    # Second try: use the last date found (validity dates are often at the bottom)
    if not extracted["validity"]:
        all_dates = []
        for line in cleaned_lines:
            for m in date_pattern.finditer(line):
                all_dates.append(m.group(0))
        if all_dates:
            extracted["validity"] = all_dates[-1]
            extracted["_confidence_scores"]["validity"] = 0.70
            logger.info("Validity (last date fallback): %s", all_dates[-1])

    # 3. Extract Department
    # Heuristic: Proximity to keywords "Department", "Dept", "Engineering", "Science", "Technology"
    dept_keywords = ["computer", "science", "engineering", "technology", "mechanical", "civil", "electrical", "electronics", "department", "dept"]
    for line in cleaned_lines:
        lower_line = line.lower()
        if any(kw in lower_line for kw in dept_keywords) and len(line) > 5:
            # Ensure it's not the institution line (which might also have "engineering")
            if "college" not in lower_line and "university" not in lower_line and "institute" not in lower_line:
                extracted["department"] = line
                extracted["_confidence_scores"]["department"] = 0.85
                break

    # 4. Extract Institution Name
    invalid_words = ["bus", "valid", "principal", "boarding"]
    inst_keywords = ["college", "university", "institute", "academy"]

    for line in cleaned_lines:
        lower_line = line.lower()

        # Skip unwanted words
        if any(word in lower_line for word in invalid_words):
            continue

        # Detect abbreviation institutions like SLCS, IIT, MIT
        if re.match(r'^[A-Z]{3,6}$', line):
            extracted["institution"] = line
            extracted["_confidence_scores"]["institution"] = 0.90
            break

        # Detect normal institution names
        if any(kw in lower_line for kw in inst_keywords) and len(line) > 8:
            extracted["institution"] = line
            extracted["_confidence_scores"]["institution"] = 0.85
            break

    # 5. Extract Name
    # Heuristic: Uppercase words or Title Case, usually near the top, not containing keywords
    # Exclude known labels or generic terms
    exclude_for_name = set(dept_keywords + inst_keywords + ["name", "dob", "date", "birth", "blood", "group", "id", "card", "student", "staff", "principal", "director", "signature"])
    
    potential_names = []
    for line in cleaned_lines:
        lower_line = line.lower()
        # Skip lines that look like they contain known fields
        if any(ex in lower_line for ex in exclude_for_name):
            continue
        # Skip lines with numbers (unlikely to be a raw standalone name)
        if any(char.isdigit() for char in line):
            continue
            
        # If line is mostly uppercase or title case and reasonable length
        if (line.isupper() or line.istitle()) and 5 <= len(line) <= 30:
            potential_names.append(line)
            
    if potential_names:
        # Usually the first valid looking plain text is the name
        extracted["name"] = potential_names[0]
        extracted["_confidence_scores"]["name"] = 0.70

    return extracted
