"""
SchoolBrain.ai — All Pydantic v2 Request/Response Models
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from datetime import datetime


# ── Health ────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


# ── Auth ──────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    school_id: str
    role: Literal["superadmin", "school_admin", "teacher", "parent"] = "teacher"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    school_id: str

class UserOut(BaseModel):
    id: int
    email: str
    school_id: str
    role: str


# ── Chat ──────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    school_id: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatResponse(BaseModel):
    response: str
    school_id: str
    sources: List[str] = []


# ── Students ──────────────────────────────────────────────────────────────────
class WeakStudentRequest(BaseModel):
    school_id: str

class WeakStudent(BaseModel):
    student_id: str
    name: str
    class_name: str
    risk_level: Literal["High", "Medium", "Low"]
    weakest_subject: str
    avg_score: float
    trend: Literal["dropping", "stable", "improving"]
    recommendation: str

class WeakStudentsResponse(BaseModel):
    students: List[WeakStudent]
    total: int
    school_id: str

class StudentScore(BaseModel):
    date: str
    subject: str
    score: float
    exam_name: str

class StudentScoreHistory(BaseModel):
    student_id: str
    name: str
    scores: List[StudentScore]


# ── Quiz ──────────────────────────────────────────────────────────────────────
class QuizRequest(BaseModel):
    topic: str
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"
    count: int = Field(default=10, ge=3, le=20)
    school_id: str

class MCQItem(BaseModel):
    question: str
    options: List[str] = Field(..., min_length=4, max_length=4)
    answer: str
    explanation: str

class QuizResponse(BaseModel):
    topic: str
    difficulty: str
    questions: List[MCQItem]


# ── Intervention Plan ─────────────────────────────────────────────────────────
class InterventionRequest(BaseModel):
    student_id: str
    school_id: str

class PlanDay(BaseModel):
    day: int
    activity: str
    goal: str
    resource: str

class InterventionResponse(BaseModel):
    student_id: str
    student_name: str
    plan: List[PlanDay]
    generated_at: str


# ── Lesson Plan ───────────────────────────────────────────────────────────────
class LessonPlanRequest(BaseModel):
    topic: str
    class_grade: str
    duration_mins: int = Field(default=45, ge=20, le=120)
    board: str = "CBSE"
    school_id: str

class LessonPlanResponse(BaseModel):
    topic: str
    class_grade: str
    board: str
    objective: str
    warm_up: str
    main_activity: str
    guided_practice: str
    assessment: str
    homework: str


# ── Analytics ─────────────────────────────────────────────────────────────────
class SubjectChart(BaseModel):
    subject: str
    avg: float
    below_passing_pct: float

class WeeklyTrend(BaseModel):
    week: str
    avg: float
    at_risk: int

class AnalyticsOverview(BaseModel):
    total_students: int
    at_risk_count: int
    avg_score: float
    open_alerts: int
    chart_data: List[SubjectChart]
    weekly_trend: List[WeeklyTrend]


# ── Memory / Index ────────────────────────────────────────────────────────────
class IndexRequest(BaseModel):
    text: str
    school_id: str
    source: str = "manual"
    subject: Optional[str] = None
    grade: Optional[str] = None

class IndexResponse(BaseModel):
    indexed: bool
    chunks: int
    school_id: str


# ── Alerts ────────────────────────────────────────────────────────────────────
class AlertConfig(BaseModel):
    school_id: str
    threshold_score: int = Field(default=40, ge=0, le=100)
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    enabled: bool = True


# ── Admin ─────────────────────────────────────────────────────────────────────
class SchoolRecord(BaseModel):
    school_id: str
    name: str
    plan: Literal["Starter", "Growth", "Elite", "Enterprise"] = "Starter"
    mrr: float = 0
    active_users: int = 0
    last_api_call: Optional[str] = None
    status: Literal["Active", "Trial", "Churned"] = "Trial"

class CreateSchoolRequest(BaseModel):
    school_id: str
    name: str
    admin_email: EmailStr
    admin_password: str
    plan: str = "Starter"
