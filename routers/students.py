"""SchoolBrain.ai — Students Router"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.schemas import WeakStudentRequest, WeakStudentsResponse, WeakStudent, StudentScoreHistory, StudentScore
from auth_utils import get_current_user
from ai_helper import generate_json, build_weak_student_prompt
from memory_system import episodic
from database import get_db, UsageLog, User

router = APIRouter()
logger = logging.getLogger(__name__)


def _summarise_students(students_dict: dict) -> str:
    """Convert student dict to compact JSON string for the AI prompt."""
    summary = []
    for sid, data in students_dict.items():
        subject_avgs = {}
        for subject, score_list in data["scores"].items():
            scores = [s["score"] for s in score_list]
            subject_avgs[subject] = round(sum(scores) / len(scores), 1)
            # detect trend: compare first half vs second half
            mid = max(1, len(scores) // 2)
            first_half_avg = sum(scores[:mid]) / mid
            second_half_avg = sum(scores[mid:]) / max(1, len(scores) - mid) if len(scores) > mid else first_half_avg
            subject_avgs[f"{subject}_trend"] = (
                "dropping" if second_half_avg < first_half_avg - 5
                else "improving" if second_half_avg > first_half_avg + 5
                else "stable"
            )
        summary.append({
            "student_id": sid,
            "name": data["name"],
            "class": data["class_name"],
            "subject_averages": subject_avgs,
        })
    return json.dumps(summary, indent=2)


@router.post("/weak", response_model=WeakStudentsResponse)
def get_weak_students(
    req: WeakStudentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = current_user.school_id

    students = episodic.get_all_students(school_id)
    if not students:
        return WeakStudentsResponse(students=[], total=0, school_id=school_id)

    summary = _summarise_students(students)
    prompt = build_weak_student_prompt(summary)

    schema = '[{student_id, name, risk_level, weakest_subject, avg_score, trend, recommendation}]'
    raw_list = generate_json(prompt, schema_hint=schema)

    validated = []
    for item in raw_list:
        try:
            # Attach class_name from episodic data
            item["class_name"] = students.get(item.get("student_id", ""), {}).get("class_name", "Unknown")
            validated.append(WeakStudent(**item))
        except Exception as e:
            logger.warning(f"Skipping invalid student record: {e} — {item}")

    # Sort: High → Medium → Low
    order = {"High": 0, "Medium": 1, "Low": 2}
    validated.sort(key=lambda s: order.get(s.risk_level, 3))

    db.add(UsageLog(school_id=school_id, endpoint="/students/weak", latency_ms=0, user_id=current_user.id))
    db.commit()

    return WeakStudentsResponse(students=validated, total=len(validated), school_id=school_id)


@router.get("/list")
def list_students(
    current_user: User = Depends(get_current_user),
):
    students = episodic.get_all_students(current_user.school_id)
    result = [
        {"student_id": sid, "name": d["name"], "class_name": d["class_name"]}
        for sid, d in students.items()
    ]
    return {"students": result, "total": len(result)}


@router.get("/{student_id}/scores", response_model=StudentScoreHistory)
def get_student_scores(
    student_id: str,
    current_user: User = Depends(get_current_user),
):
    events = episodic.get_events(current_user.school_id, student_id=student_id)
    if not events:
        raise HTTPException(status_code=404, detail="Student not found")

    student_name = events[0].get("name", student_id)
    scores = [
        StudentScore(
            date=ev.get("date", ""),
            subject=ev.get("subject", ""),
            score=ev.get("score", 0),
            exam_name=ev.get("exam_name", ""),
        )
        for ev in events
    ]
    scores.sort(key=lambda s: s.date)
    return StudentScoreHistory(student_id=student_id, name=student_name, scores=scores)
