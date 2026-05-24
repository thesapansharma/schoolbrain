"""SchoolBrain.ai — Auth Router"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, User, School
from auth_utils import hash_password, verify_password, create_access_token, require_role
from models.schemas import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email, User.is_active == True).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"user_id": user.id, "school_id": user.school_id, "role": user.role})
    return TokenResponse(access_token=token, role=user.role, school_id=user.school_id)


@router.post("/register", response_model=TokenResponse)
def register(
    req: RegisterRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("superadmin")),
):
    """Only superadmin can create new users."""
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        school_id=req.school_id,
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"user_id": user.id, "school_id": user.school_id, "role": user.role})
    return TokenResponse(access_token=token, role=user.role, school_id=user.school_id)


@router.post("/register/superadmin", response_model=TokenResponse, include_in_schema=False)
def register_first_superadmin(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    One-time bootstrap endpoint — creates the very first superadmin.
    Disable this route in production after initial setup.
    """
    existing = db.query(User).filter(User.role == "superadmin").first()
    if existing:
        raise HTTPException(status_code=403, detail="Superadmin already exists. Use /auth/register.")
    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        school_id=req.school_id or "platform",
        role="superadmin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"user_id": user.id, "school_id": user.school_id, "role": user.role})
    return TokenResponse(access_token=token, role=user.role, school_id=user.school_id)
