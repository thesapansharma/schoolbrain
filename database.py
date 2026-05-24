"""
SchoolBrain.ai — SQLite Database (SQLAlchemy)
Stores: users, schools, alert configs, usage logs
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./schoolbrain.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Models ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    school_id     = Column(String, index=True, nullable=False)
    role          = Column(String, default="teacher")   # superadmin|school_admin|teacher|parent
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class School(Base):
    __tablename__ = "schools"
    id          = Column(Integer, primary_key=True, index=True)
    school_id   = Column(String, unique=True, index=True)
    name        = Column(String)
    plan        = Column(String, default="Starter")
    mrr         = Column(Float, default=0.0)
    status      = Column(String, default="Trial")       # Active|Trial|Churned
    created_at  = Column(DateTime, default=datetime.utcnow)


class AlertConfig(Base):
    __tablename__ = "alert_configs"
    id               = Column(Integer, primary_key=True)
    school_id        = Column(String, index=True)
    threshold_score  = Column(Integer, default=40)
    whatsapp_number  = Column(String, nullable=True)
    email            = Column(String, nullable=True)
    enabled          = Column(Boolean, default=True)


class UsageLog(Base):
    __tablename__ = "usage_logs"
    id          = Column(Integer, primary_key=True)
    school_id   = Column(String, index=True)
    endpoint    = Column(String)
    latency_ms  = Column(Float)
    user_id     = Column(Integer, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


# ── Init ──────────────────────────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)


# ── Dependency ────────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
