import json
import os
import re

SQL_FILE = "app/data/data.sql"
OUTPUT_DIR = "app/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "seed_questions.json")


def parse_value(val):
    val = val.strip()
    if val.upper() == "NULL":
        return None
    if val.upper() == "TRUE":
        return True
    if val.upper() == "FALSE":
        return False
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1]
    return val


def convert():
    if not os.path.exists(SQL_FILE):
        print(f"❌ File not found: {SQL_FILE}")
        return

    questions = []

    # Regex to capture values inside VALUES (...)
    # This is a simple regex assumption that values don't contain ), inside quotes properly handled by simple split if no commas in text.
    # But text might contain commas. e.g. "Hello, world".
    # Better to use a slightly more robust splitter or regex.

    with open(SQL_FILE) as f:
        for line in f:
            if not line.startswith("INSERT INTO question_bank"):
                continue

            # Extract content in parenthesis after VALUES
            match = re.search(r"VALUES \((.*)\);", line)
            if not match:
                continue

            # Split by comma, but ignore commas inside single quotes
            # A simple way for this specific SQL file which seems to have clean strings
            raw_values = match.group(1)

            # Robust splitting
            values = []
            current_val = []
            in_quote = False
            for char in raw_values:
                if char == "'" and (not current_val or current_val[-1] != "\\"):
                    in_quote = not in_quote
                if char == "," and not in_quote:
                    values.append("".join(current_val).strip())
                    current_val = []
                else:
                    current_val.append(char)
            values.append("".join(current_val).strip())

            # Helper to safely get index
            def get_val(idx, values=values):
                if idx >= len(values):
                    return None
                return parse_value(values[idx])

            # Order in SQL: id, text, template, slot_key, genres, test_phases, purpose_category, purpose_subcategory, active, created_at, updated_at

            q = {
                "id": get_val(0),
                "text": get_val(1),
                "template": get_val(2),
                "slotKey": get_val(3),
                "genres": get_val(4),
                "testPhases": get_val(5),
                "purposeCategory": get_val(6),
                "purposeSubcategory": get_val(7),
                "active": get_val(8),
            }
            questions.append(q)

    # Ensure output dir exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

    print(f"✅ Converted {len(questions)} questions to {OUTPUT_FILE}")


if __name__ == "__main__":
    convert()
