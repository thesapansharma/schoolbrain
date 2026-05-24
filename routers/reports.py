"""SchoolBrain.ai — PDF Report Generator (ReportLab)"""

import io
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth_utils import get_current_user, require_role
from memory_system import episodic
from ai_helper import _ollama_chat
from database import get_db, User

router = APIRouter()
logger = logging.getLogger(__name__)


def _grade(score: float) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 40: return "D"
    return "F"


def _trend_arrow(scores: list) -> str:
    if len(scores) < 2:
        return "→"
    return "↑" if scores[-1] > scores[0] + 5 else ("↓" if scores[-1] < scores[0] - 5 else "→")


def _generate_pdf_bytes(student_id: str, school_id: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
    except ImportError:
        raise RuntimeError("ReportLab not installed. Run: pip install reportlab")

    students = episodic.get_all_students(school_id)
    student = students.get(student_id)
    if not student:
        raise ValueError(f"Student {student_id} not found")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                             leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    title_style = ParagraphStyle("Title", fontSize=22, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#1e3a5f"), spaceAfter=4)
    sub_style   = ParagraphStyle("Sub", fontSize=12, textColor=colors.grey)
    body_style  = ParagraphStyle("Body", fontSize=10, leading=16)

    story.append(Paragraph("SchoolBrain.ai — Student Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%d %b %Y')}", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1e3a5f")))
    story.append(Spacer(1, 0.4*cm))

    # ── Student Info ──────────────────────────────────────────────────────────
    story.append(Paragraph(f"<b>Student:</b> {student['name']}", body_style))
    story.append(Paragraph(f"<b>Class:</b> {student['class_name']}", body_style))
    story.append(Spacer(1, 0.4*cm))

    # ── Score Table ───────────────────────────────────────────────────────────
    table_data = [["Subject", "Latest Score", "Average", "Grade", "Trend"]]
    subject_avgs = {}
    for subj, score_list in student["scores"].items():
        scores = [s["score"] for s in sorted(score_list, key=lambda x: x["date"])]
        avg = sum(scores) / len(scores)
        subject_avgs[subj] = avg
        table_data.append([
            subj,
            str(int(scores[-1])),
            f"{avg:.1f}",
            _grade(avg),
            _trend_arrow(scores),
        ])

    def _row_color(row):
        try:
            avg = float(row[2])
            if avg < 40:  return colors.HexColor("#ffd6d6")
            if avg < 60:  return colors.HexColor("#fff3cd")
            return colors.HexColor("#d6f5d6")
        except Exception:
            return colors.white

    tbl = Table(table_data, colWidths=[5*cm, 3*cm, 3*cm, 2*cm, 2*cm])
    ts = [
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white]),
        ("ALIGN",        (1, 0), (-1, -1), "CENTER"),
    ]
    for i, row in enumerate(table_data[1:], start=1):
        ts.append(("BACKGROUND", (0, i), (-1, i), _row_color(row)))
    tbl.setStyle(TableStyle(ts))
    story.append(tbl)
    story.append(Spacer(1, 0.6*cm))

    # ── AI Summary ────────────────────────────────────────────────────────────
    overall_avg = sum(subject_avgs.values()) / len(subject_avgs) if subject_avgs else 0
    ai_prompt = [{"role": "user", "content":
        f"Write a 3-sentence teacher summary for student {student['name']} "
        f"with an overall average of {overall_avg:.1f}/100 across {', '.join(subject_avgs.keys())}. "
        f"Be professional and constructive. Focus on strengths and one area for improvement."}]
    try:
        summary_text = _ollama_chat(ai_prompt, temperature=0.5)
    except Exception:
        summary_text = f"{student['name']} has an overall average of {overall_avg:.1f}/100."

    story.append(Paragraph("<b>AI Teacher Summary</b>", styles["Heading3"]))
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 0.8*cm))

    # ── Intervention Plan (if at risk) ────────────────────────────────────────
    if overall_avg < 60:
        story.append(Paragraph("<b>7-Day Intervention Plan</b>", styles["Heading3"]))
        plan_data = [["Day", "Activity", "Goal"]]
        activities = [
            ("Review weak topics", "Identify gaps"),
            ("Practice exercises", "Apply knowledge"),
            ("Peer learning", "Consolidate"),
            ("Teacher Q&A", "Clarify doubts"),
            ("Mock test", "Assess progress"),
            ("Error analysis", "Learn from mistakes"),
            ("Revision + rest", "Consolidate gains"),
        ]
        for i, (act, goal) in enumerate(activities, 1):
            plan_data.append([str(i), act, goal])
        plan_tbl = Table(plan_data, colWidths=[2*cm, 8*cm, 5*cm])
        plan_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8522a")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
        ]))
        story.append(plan_tbl)

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        f"<font size='8' color='grey'>Confidential — Powered by SchoolBrain.ai — {datetime.utcnow().strftime('%d %b %Y')}</font>",
        body_style
    ))

    doc.build(story)
    return buf.getvalue()


@router.get("/pdf")
def download_student_report(
    student_id: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    pdf_bytes = _generate_pdf_bytes(student_id, current_user.school_id)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{student_id}.pdf"},
    )


@router.post("/generate-all")
def generate_all_reports(
    current_user: User = Depends(require_role("school_admin", "superadmin")),
):
    """Trigger PDF generation for all students (returns count, actual files saved to disk)."""
    import os
    students = episodic.get_all_students(current_user.school_id)
    out_dir = f"./reports/{current_user.school_id}"
    os.makedirs(out_dir, exist_ok=True)
    generated = []
    for sid in students:
        try:
            pdf_bytes = _generate_pdf_bytes(sid, current_user.school_id)
            path = f"{out_dir}/{sid}.pdf"
            with open(path, "wb") as f:
                f.write(pdf_bytes)
            generated.append(sid)
        except Exception as e:
            logger.error(f"Failed to generate report for {sid}: {e}")
    return {"generated": len(generated), "student_ids": generated}
