"""SchoolBrain.ai — Intervention & Lesson Plan Routers"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.schemas import (
    InterventionRequest, InterventionResponse, PlanDay,
    LessonPlanRequest, LessonPlanResponse,
)
from auth_utils import get_current_user
from ai_helper import generate_json, build_intervention_prompt, build_lesson_plan_prompt
from memory_system import episodic
from database import get_db, UsageLog, User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/intervention/plan", response_model=InterventionResponse)
def generate_intervention(
    req: InterventionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = current_user.school_id
    students = episodic.get_all_students(school_id)
    student = students.get(req.student_id)
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {req.student_id} not found")

    # Find weakest subject
    subject_avgs = {}
    for subj, score_list in student["scores"].items():
        scores = [s["score"] for s in score_list]
        subject_avgs[subj] = sum(scores) / len(scores)

    if subject_avgs:
        weakest = min(subject_avgs, key=subject_avgs.get)
        avg_score = subject_avgs[weakest]
    else:
        weakest, avg_score = "General", 50.0

    prompt = build_intervention_prompt(student["name"], weakest, avg_score)
    schema = '[{day:int, activity:str, goal:str, resource:str}] — 7 items'

    raw_list = generate_json(prompt, schema_hint=schema)

    plan_days = []
    for item in raw_list:
        try:
            plan_days.append(PlanDay(**item))
        except Exception as e:
            logger.warning(f"Skipping invalid plan day: {e}")

    db.add(UsageLog(school_id=school_id, endpoint="/intervention/plan", latency_ms=0, user_id=current_user.id))
    db.commit()

    return InterventionResponse(
        student_id=req.student_id,
        student_name=student["name"],
        plan=plan_days,
        generated_at=datetime.utcnow().isoformat(),
    )


@router.post("/lesson/plan", response_model=LessonPlanResponse)
def generate_lesson_plan(
    req: LessonPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = build_lesson_plan_prompt(req.topic, req.class_grade, req.duration_mins, req.board)
    schema = '{objective, warm_up, main_activity, guided_practice, assessment, homework}'

    raw = generate_json(prompt, schema_hint=schema)

    db.add(UsageLog(school_id=current_user.school_id, endpoint="/lesson/plan", latency_ms=0, user_id=current_user.id))
    db.commit()

    return LessonPlanResponse(
        topic=req.topic,
        class_grade=req.class_grade,
        board=req.board,
        **{k: raw.get(k, "") for k in ["objective", "warm_up", "main_activity", "guided_practice", "assessment", "homework"]},
    )
