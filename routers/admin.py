"""SchoolBrain.ai — Super Admin Router"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from auth_utils import get_current_user, require_role, hash_password
from database import get_db, User, School, UsageLog
from models.schemas import CreateSchoolRequest

router = APIRouter()


@router.get("/schools")
def list_schools(
    db: Session = Depends(get_db),
    _admin=Depends(require_role("superadmin")),
):
    schools = db.query(School).all()
    result = []
    for s in schools:
        active_users = db.query(User).filter(User.school_id == s.school_id, User.is_active == True).count()
        last_log = db.query(UsageLog).filter(UsageLog.school_id == s.school_id)\
                     .order_by(UsageLog.created_at.desc()).first()
        result.append({
            "school_id": s.school_id,
            "name": s.name,
            "plan": s.plan,
            "mrr": s.mrr,
            "active_users": active_users,
            "last_api_call": last_log.created_at.isoformat() if last_log else None,
            "status": s.status,
        })
    return {"schools": result, "total": len(result)}


@router.post("/schools")
def create_school(
    req: CreateSchoolRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("superadmin")),
):
    if db.query(School).filter(School.school_id == req.school_id).first():
        raise HTTPException(status_code=400, detail="School ID already exists")
    school = School(school_id=req.school_id, name=req.name, plan=req.plan)
    db.add(school)

    admin_user = User(
        email=req.admin_email,
        hashed_password=hash_password(req.admin_password),
        school_id=req.school_id,
        role="school_admin",
    )
    db.add(admin_user)
    db.commit()
    return {"school_id": req.school_id, "name": req.name, "status": "created"}


@router.get("/revenue")
def revenue_overview(
    db: Session = Depends(get_db),
    _admin=Depends(require_role("superadmin")),
):
    schools = db.query(School).filter(School.status == "Active").all()
    total_mrr = sum(s.mrr for s in schools)
    avg_mrr = total_mrr / len(schools) if schools else 0
    return {
        "total_mrr": total_mrr,
        "total_schools": len(schools),
        "avg_revenue_per_school": round(avg_mrr, 2),
    }


@router.get("/usage")
def usage_overview(
    db: Session = Depends(get_db),
    _admin=Depends(require_role("superadmin")),
):
    rows = db.query(
        UsageLog.school_id,
        func.count(UsageLog.id).label("total_calls"),
        func.avg(UsageLog.latency_ms).label("avg_latency"),
    ).group_by(UsageLog.school_id).all()
    return {"usage": [{"school_id": r.school_id, "total_calls": r.total_calls, "avg_latency_ms": round(r.avg_latency or 0, 1)} for r in rows]}
