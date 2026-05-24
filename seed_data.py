"""
SchoolBrain.ai — Seed Data Script
Run: python seed_data.py
Inserts 20 students × 10 exam events into data/schools/demo/events.jsonl
"""

import json, random, sys
from pathlib import Path
from datetime import datetime, timedelta

# ── Fake student data ─────────────────────────────────────────────────────────
STUDENTS = [
    # Weak students (avg 30-45)
    {"id": "s001", "name": "Rahul Sharma",     "class": "8A"},
    {"id": "s002", "name": "Priya Patel",      "class": "8A"},
    {"id": "s003", "name": "Amit Verma",       "class": "8B"},
    {"id": "s004", "name": "Sneha Gupta",      "class": "8B"},
    # Borderline students (avg 50-58)
    {"id": "s005", "name": "Karan Mehta",      "class": "8A"},
    {"id": "s006", "name": "Pooja Yadav",      "class": "8B"},
    {"id": "s007", "name": "Rohan Joshi",      "class": "8A"},
    # Normal students (avg 60-95)
    {"id": "s008", "name": "Ananya Singh",     "class": "8A"},
    {"id": "s009", "name": "Vikram Nair",      "class": "8B"},
    {"id": "s010", "name": "Divya Reddy",      "class": "8A"},
    {"id": "s011", "name": "Arjun Kapoor",     "class": "8B"},
    {"id": "s012", "name": "Meera Iyer",       "class": "8A"},
    {"id": "s013", "name": "Siddharth Roy",    "class": "8B"},
    {"id": "s014", "name": "Kavya Menon",      "class": "8A"},
    {"id": "s015", "name": "Aditya Kumar",     "class": "8B"},
    {"id": "s016", "name": "Ishaan Bhat",      "class": "8A"},
    {"id": "s017", "name": "Tanvi Desai",      "class": "8B"},
    {"id": "s018", "name": "Nikhil Pandey",    "class": "8A"},
    {"id": "s019", "name": "Shreya Agarwal",   "class": "8B"},
    {"id": "s020", "name": "Yash Malhotra",    "class": "8A"},
]

SUBJECTS = ["Math", "Science", "English", "Social Studies", "Hindi"]
EXAMS    = ["Unit Test 1", "Unit Test 2", "Mid-Term", "Unit Test 3", "Unit Test 4",
            "Surprise Test", "Assignment", "Unit Test 5", "Pre-Final", "Final Exam"]

def score_for(student_index: int, subject: str, exam_index: int) -> int:
    if student_index < 4:      # Weak
        base = random.randint(28, 45)
        if subject == "Math" and student_index < 2:
            base = random.randint(22, 38)
    elif student_index < 7:    # Borderline
        base = random.randint(48, 58)
    else:                       # Normal
        base = random.randint(62, 92)
    # Add slight downward trend for the first 4 students
    if student_index < 4:
        base = max(20, base - exam_index * 1)
    return min(100, max(10, base + random.randint(-3, 3)))

def main():
    school_id = sys.argv[1] if len(sys.argv) > 1 else "demo"
    out_dir = Path(f"./data/schools/{school_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "events.jsonl"

    events = []
    start_date = datetime(2025, 6, 1)

    for idx, student in enumerate(STUDENTS):
        for exam_idx, exam in enumerate(EXAMS):
            for subject in SUBJECTS:
                event_date = start_date + timedelta(weeks=exam_idx * 2)
                event = {
                    "student_id": student["id"],
                    "name":       student["name"],
                    "class":      student["class"],
                    "subject":    subject,
                    "score":      score_for(idx, subject, exam_idx),
                    "date":       event_date.strftime("%Y-%m-%d"),
                    "exam_name":  exam,
                }
                events.append(event)

    with open(out_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    print(f"✅ Seeded {len(events)} events for {len(STUDENTS)} students → {out_file}")
    print(f"   Weak students: s001-s004 (Rahul, Priya, Amit, Sneha)")
    print(f"   Borderline:    s005-s007 (Karan, Pooja, Rohan)")
    print(f"   Normal:        s008-s020")
    print(f"\nNow test:")
    print(f"  curl -X POST http://localhost:8000/students/weak \\")
    print(f"       -H 'Content-Type: application/json' \\")
    print(f"       -H 'Authorization: Bearer YOUR_TOKEN' \\")
    print(f"       -d '{{\"school_id\":\"{school_id}\"}}'")

if __name__ == "__main__":
    main()
