import re

def extract_fields(ocr_results, raw_text_full):
    """
    Intelligently extracts fields from OCR text using regex and heuristics.
    Works for plain ID cards with no strict formatting.
    """
    extracted = {
        "name": None,
        "roll_number": None,
        "date_of_birth": None,
        "department": None,
        "institution": None,
        "_confidence_scores": {
            "name": 0.0,
            "roll_number": 0.0,
            "date_of_birth": 0.0,
            "department": 0.0,
            "institution": 0.0,
        }
    }
    
    # Pre-process lines
    lines = raw_text_full.split("\n")
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    
    # 1. Extract Roll Number / ID Number
    # Heuristic: Looks for patterns mixing uppercase letters and numbers (e.g., 21CS045)
    # Often 5 to 15 characters long.
    roll_pattern = re.compile(r'\b[A-Z0-9]{5,15}\b')
    for line in cleaned_lines:
        words = line.split()
        for word in words:
            # Check if it has both numbers and letters
            if any(char.isdigit() for char in word) and any(char.isalpha() for char in word):
                if roll_pattern.fullmatch(word):
                    extracted["roll_number"] = word
                    extracted["_confidence_scores"]["roll_number"] = 0.90
                    break
        if extracted["roll_number"]: break

    # 2. Extract Date of Birth
    # Matches DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD, etc.
    dob_pattern = re.compile(r'\b(\d{2}[-/\.]\d{2}[-/\.]\d{4}|\d{4}[-/\.]\d{2}[-/\.]\d{2})\b')
    for line in cleaned_lines:
        match = dob_pattern.search(line)
        if match:
            extracted["date_of_birth"] = match.group(0)
            extracted["_confidence_scores"]["date_of_birth"] = 0.95
            break

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
    # Heuristic: Contains "College", "University", "Institute", "Academy", "School"
    inst_keywords = ["college", "university", "institute", "academy", "school"]
    for line in cleaned_lines:
        lower_line = line.lower()
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
