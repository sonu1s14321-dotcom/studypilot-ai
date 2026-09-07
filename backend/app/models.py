from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    daily_hours: Mapped[float] = mapped_column(Float, default=3.0)
    preferred_start_hour: Mapped[int] = mapped_column(Integer, default=18)
    session_minutes: Mapped[int] = mapped_column(Integer, default=50)
    break_minutes: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    subjects: Mapped[list["Subject"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[list["StudyTask"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    logs: Mapped[list["StudyLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    exam_date: Mapped[date] = mapped_column(Date, index=True)
    importance: Mapped[int] = mapped_column(Integer, default=3)
    target_score: Mapped[int] = mapped_column(Integer, default=80)
    color: Mapped[str] = mapped_column(String(20), default="#6D5DFB")
    notes: Mapped[str] = mapped_column(Text, default="")
    user: Mapped["User"] = relationship(back_populates="subjects")
    topics: Mapped[list["Topic"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    tasks: Mapped[list["StudyTask"]] = relationship(back_populates="subject", cascade="all, delete-orphan")

class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    mastery: Mapped[int] = mapped_column(Integer, default=30)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=120)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    subject: Mapped["Subject"] = relationship(back_populates="topics")
    tasks: Mapped[list["StudyTask"]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    logs: Mapped[list["StudyLog"]] = relationship(back_populates="topic", cascade="all, delete-orphan")

class StudyTask(Base):
    __tablename__ = "study_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    task_date: Mapped[date] = mapped_column(Date, index=True)
    start_minute: Mapped[int] = mapped_column(Integer, default=1080)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=50)
    task_type: Mapped[str] = mapped_column(String(30), default="Learn")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    priority: Mapped[float] = mapped_column(Float, default=0.0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped["User"] = relationship(back_populates="tasks")
    subject: Mapped["Subject"] = relationship(back_populates="tasks")
    topic: Mapped["Topic"] = relationship(back_populates="tasks")

class StudyLog(Base):
    __tablename__ = "study_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    studied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    quiz_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user: Mapped["User"] = relationship(back_populates="logs")
    topic: Mapped["Topic"] = relationship(back_populates="logs")
