from datetime import date
from typing import Literal
from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    daily_hours: float
    preferred_start_hour: int
    session_minutes: int
    break_minutes: int
    model_config = {"from_attributes": True}

class UserSettingsIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    daily_hours: float | None = Field(default=None, ge=0.5, le=12)
    preferred_start_hour: int | None = Field(default=None, ge=0, le=23)
    session_minutes: int | None = Field(default=None, ge=20, le=120)
    break_minutes: int | None = Field(default=None, ge=5, le=45)

class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    exam_date: date
    importance: int = Field(default=3, ge=1, le=5)
    target_score: int = Field(default=80, ge=35, le=100)
    color: str = "#6D5DFB"
    notes: str = Field(default="", max_length=2000)

class SubjectOut(BaseModel):
    id: int
    name: str
    exam_date: date
    importance: int
    target_score: int
    color: str
    notes: str
    model_config = {"from_attributes": True}

class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    difficulty: int = Field(default=3, ge=1, le=5)
    mastery: int = Field(default=30, ge=0, le=100)
    estimated_minutes: int = Field(default=120, ge=20, le=3000)

class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    mastery: int | None = Field(default=None, ge=0, le=100)
    estimated_minutes: int | None = Field(default=None, ge=20, le=3000)
    completed: bool | None = None

class TopicOut(BaseModel):
    id: int
    subject_id: int
    name: str
    difficulty: int
    mastery: int
    estimated_minutes: int
    completed: bool
    model_config = {"from_attributes": True}

class SubjectWithTopics(SubjectOut):
    topics: list[TopicOut] = []

class GeneratePlanIn(BaseModel):
    horizon_days: int = Field(default=21, ge=3, le=60)

class CompleteTaskIn(BaseModel):
    quiz_score: int | None = Field(default=None, ge=0, le=100)
    confidence: int | None = Field(default=None, ge=1, le=5)

class CoachIn(BaseModel):
    message: str = Field(min_length=2, max_length=3000)

class QuizIn(BaseModel):
    topic_id: int
    count: int = Field(default=5, ge=3, le=10)
    style: Literal["mixed", "short", "application"] = "mixed"
