"""SchoolBrain.ai — Analytics Router"""

from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from models.schemas import AnalyticsOverview, SubjectChart, WeeklyTrend
from auth_utils import get_current_user, require_role
from memory_system import episodic
from database import get_db, User

router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(
    days: int = Query(default=30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
):
    school_id = current_user.school_id
    students = episodic.get_all_students(school_id)

    total_students = len(students)
    all_scores, at_risk_count = [], 0
    subject_scores: dict = defaultdict(list)

    for sid, data in students.items():
        student_avgs = []
        for subj, score_list in data["scores"].items():
            scores = [s["score"] for s in score_list]
            avg = sum(scores) / len(scores)
            subject_scores[subj].extend(scores)
            student_avgs.append(avg)
        if student_avgs:
            student_overall = sum(student_avgs) / len(student_avgs)
            all_scores.append(student_overall)
            if student_overall < 60:
                at_risk_count += 1

    avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0

    chart_data = []
    for subj, scores in subject_scores.items():
        subj_avg = sum(scores) / len(scores)
        below_pct = round(len([s for s in scores if s < 60]) / len(scores) * 100, 1)
        chart_data.append(SubjectChart(subject=subj, avg=round(subj_avg, 1), below_passing_pct=below_pct))

    # Weekly trend (last 8 weeks, from episodic events)
    events = episodic.get_events(school_id, limit=5000)
    weekly: dict = defaultdict(list)
    for ev in events:
        try:
            date = datetime.fromisoformat(ev.get("date", ""))
            # ISO week
            week_label = date.strftime("%Y-W%W")
            weekly[week_label].append(ev.get("score", 0))
        except Exception:
            pass

    weekly_trend = []
    for week in sorted(weekly.keys())[-8:]:
        scores = weekly[week]
        w_avg = sum(scores) / len(scores)
        at_risk_week = len([s for s in scores if s < 60])
        weekly_trend.append(WeeklyTrend(week=week, avg=round(w_avg, 1), at_risk=at_risk_week))

    return AnalyticsOverview(
        total_students=total_students,
        at_risk_count=at_risk_count,
        avg_score=avg_score,
        open_alerts=at_risk_count,  # simplified
        chart_data=chart_data,
        weekly_trend=weekly_trend,
    )
