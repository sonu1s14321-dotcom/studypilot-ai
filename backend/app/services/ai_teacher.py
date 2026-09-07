from __future__ import annotations
from datetime import date
from google import genai
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from ..database import settings
from ..models import Subject, Topic, User

def _context(db: Session, user: User) -> str:
    subjects = db.scalars(select(Subject).where(Subject.user_id == user.id).options(selectinload(Subject.topics)).order_by(Subject.exam_date)).all()
    lines = [f"Student: {user.name}", f"Daily study time: {user.daily_hours} hours", f"Preferred session: {user.session_minutes} minutes", f"Today: {date.today().isoformat()}", "Subjects and topics:"]
    for subject in subjects[:10]:
        lines.append(f"- {subject.name}; exam {subject.exam_date}; importance {subject.importance}/5; target {subject.target_score}%")
        for topic in subject.topics[:20]:
            lines.append(f"  * {topic.name}: mastery {topic.mastery}%, difficulty {topic.difficulty}/5, estimated {topic.estimated_minutes} min")
    return "\n".join(lines)

def _fallback_coach(db: Session, user: User, message: str) -> str:
    topics = db.scalars(select(Topic).join(Subject).where(Subject.user_id == user.id, Topic.completed.is_(False)).order_by(Topic.mastery.asc(), Topic.difficulty.desc()).limit(3)).all()
    if not topics:
        return "Add your subjects, exam dates and topics first. Then generate a smart plan. I will prioritize weak topics, difficult chapters and the nearest exams."
    focus = ", ".join(t.name for t in topics)
    return f"Teacher plan: start with {focus}. Use one focused session to understand the concept, close your notes and recall the key points from memory, then solve or create practice questions. End each session by rating your confidence from 1–5. Complete today's planned tasks before adding extra topics. StudyPilot is currently using its built-in study coach for this response."

def coach(db: Session, user: User, message: str) -> dict:
    if not settings.gemini_api_key:
        return {"mode":"built-in","answer":_fallback_coach(db,user,message)}
    system = '''You are StudyPilot AI, a supportive exam-preparation teacher.
Use only the student's supplied subjects/topics as authoritative syllabus data.
Do not invent deadlines, marks, chapters, or completed work.
Prioritize weak concepts, upcoming exams, active recall, spaced review, timed practice, reasonable breaks and achievable daily workload.
When the student asks for a plan, provide concrete ordered actions.
When uncertain, say what information is missing.
Do not claim that a readiness score guarantees an exam result.
Keep the answer concise, practical, and teacher-like.'''
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(model=settings.gemini_model, contents=f"{system}\n\nSTUDENT CONTEXT\n{_context(db,user)}\n\nQUESTION\n{message}")
        return {"mode":"gemini","answer":response.text}
    except Exception as e:
     print("Gemini coach error:", repr(e))

    return {
        "mode": "built-in",
        "answer": _fallback_coach(db, user, message),
    }

def generate_quiz(db: Session, user: User, topic: Topic, count: int, style: str) -> dict:
    fallback = [f"Explain {topic.name} in your own words without looking at notes.",f"List the five most important facts, steps, or ideas in {topic.name}.",f"Create one exam-style problem or scenario involving {topic.name}, then solve it.",f"What are two common mistakes a student might make in {topic.name}?",f"Compare {topic.name} with the closest related concept in this subject.",f"Write a 60-second summary of {topic.name} as if teaching a classmate.",f"Which part of {topic.name} are you least confident about, and why?",f"Create three flashcards for {topic.name}.",f"Give one real-world application of {topic.name}.",f"Write a mini answer suitable for a 5-mark question on {topic.name}."][:count]
    if not settings.gemini_api_key: return {"mode":"built-in","questions":fallback}
    prompt = f"Create exactly {count} exam-preparation questions for the topic '{topic.name}'. Style: {style}. Difficulty {topic.difficulty}/5; mastery {topic.mastery}%. Mix active recall, conceptual understanding and application. Return only numbered questions. Do not invent a university syllabus."
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        lines = [line.strip() for line in (response.text or "").splitlines() if line.strip()]
        questions = [line.split(".",1)[-1].strip() for line in lines if any(ch.isdigit() for ch in line[:3])]
        return {"mode":"gemini","questions":(questions or fallback)[:count]}
    except Exception:
        return {"mode":"built-in","questions":fallback}
