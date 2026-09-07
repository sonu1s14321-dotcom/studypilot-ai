from __future__ import annotations
from datetime import date, datetime, timedelta
from statistics import mean
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload
from .database import Base, engine, get_db, settings
from .models import StudyLog, StudyTask, Subject, Topic, User
from .schemas import CoachIn, CompleteTaskIn, GeneratePlanIn, LoginIn, QuizIn, RegisterIn, SubjectCreate, SubjectWithTopics, TopicCreate, TopicOut, TopicUpdate, UserOut, UserSettingsIn
from .security import create_access_token, get_current_user, hash_password, verify_password
from .services.ai_teacher import coach, generate_quiz
from .services.planner import generate_plan
from .services.resources import search_resources

app = FastAPI(title="StudyPilot AI API", version="1.0.0", description="Smart study planning, exam readiness, AI coaching, and free learning resources.")
origins = [o.strip() for o in settings.frontend_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)

@app.get("/")
def root(): return {"name":"StudyPilot AI API","docs":"/docs"}

@app.get("/health")
def health(): return {"status":"ok"}

@app.post("/auth/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if existing: raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(name=payload.name.strip(), email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token":create_access_token(user.id),"user":UserOut.model_validate(user)}

@app.post("/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return {"access_token":create_access_token(user.id),"user":UserOut.model_validate(user)}

@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)): return user

@app.patch("/users/me", response_model=UserOut)
def update_me(payload: UserSettingsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for key, value in payload.model_dump(exclude_none=True).items(): setattr(user,key,value)
    db.commit(); db.refresh(user); return user

@app.get("/subjects", response_model=list[SubjectWithTopics])
def list_subjects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Subject).where(Subject.user_id == user.id).options(selectinload(Subject.topics)).order_by(Subject.exam_date)).all()

@app.post("/subjects", response_model=SubjectWithTopics)
def add_subject(payload: SubjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.exam_date < date.today(): raise HTTPException(status_code=400, detail="Exam date cannot be in the past")
    subject = Subject(user_id=user.id, **payload.model_dump()); db.add(subject); db.commit(); db.refresh(subject); subject.topics=[]; return subject

@app.delete("/subjects/{subject_id}")
def remove_subject(subject_id:int, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    subject=db.scalar(select(Subject).where(Subject.id==subject_id, Subject.user_id==user.id))
    if not subject: raise HTTPException(status_code=404, detail="Subject not found")
    db.delete(subject); db.commit(); return {"ok":True}

@app.post("/subjects/{subject_id}/topics", response_model=TopicOut)
def add_topic(subject_id:int,payload:TopicCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    subject=db.scalar(select(Subject).where(Subject.id==subject_id, Subject.user_id==user.id))
    if not subject: raise HTTPException(status_code=404, detail="Subject not found")
    topic=Topic(subject_id=subject_id, **payload.model_dump()); db.add(topic); db.commit(); db.refresh(topic); return topic

@app.patch("/topics/{topic_id}", response_model=TopicOut)
def edit_topic(topic_id:int,payload:TopicUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    topic=db.scalar(select(Topic).join(Subject).where(Topic.id==topic_id, Subject.user_id==user.id))
    if not topic: raise HTTPException(status_code=404, detail="Topic not found")
    for key,value in payload.model_dump(exclude_none=True).items(): setattr(topic,key,value)
    db.commit(); db.refresh(topic); return topic

@app.delete("/topics/{topic_id}")
def remove_topic(topic_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    topic=db.scalar(select(Topic).join(Subject).where(Topic.id==topic_id, Subject.user_id==user.id))
    if not topic: raise HTTPException(status_code=404, detail="Topic not found")
    db.delete(topic); db.commit(); return {"ok":True}

def serialize_task(task:StudyTask)->dict:
    return {"id":task.id,"subject_id":task.subject_id,"subject_name":task.subject.name,"subject_color":task.subject.color,"topic_id":task.topic_id,"topic_name":task.topic.name,"task_date":task.task_date.isoformat(),"start_minute":task.start_minute,"duration_minutes":task.duration_minutes,"task_type":task.task_type,"status":task.status,"priority":task.priority}

@app.post("/planner/generate")
def build_plan(payload:GeneratePlanIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    topics_count=db.scalar(select(func.count(Topic.id)).join(Subject).where(Subject.user_id==user.id))
    if not topics_count: raise HTTPException(status_code=400, detail="Add at least one subject and topic first")
    generate_plan(db,user,payload.horizon_days)
    tasks=db.scalars(select(StudyTask).where(StudyTask.user_id==user.id,StudyTask.task_date>=date.today(),StudyTask.task_date<=date.today()+timedelta(days=payload.horizon_days-1)).options(selectinload(StudyTask.subject),selectinload(StudyTask.topic)).order_by(StudyTask.task_date,StudyTask.start_minute)).all()
    return {"count":len(tasks),"tasks":[serialize_task(t) for t in tasks]}

@app.get("/tasks")
def tasks(from_date:date|None=Query(default=None),to_date:date|None=Query(default=None),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    start=from_date or date.today(); end=to_date or start+timedelta(days=13)
    rows=db.scalars(select(StudyTask).where(StudyTask.user_id==user.id,StudyTask.task_date>=start,StudyTask.task_date<=end).options(selectinload(StudyTask.subject),selectinload(StudyTask.topic)).order_by(StudyTask.task_date,StudyTask.start_minute)).all()
    return [serialize_task(t) for t in rows]

@app.post("/tasks/{task_id}/complete")
def complete_task(task_id:int,payload:CompleteTaskIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    task=db.scalar(select(StudyTask).where(StudyTask.id==task_id,StudyTask.user_id==user.id).options(selectinload(StudyTask.topic)))
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "completed":
        task.status="completed"; task.completed_at=datetime.utcnow()
        db.add(StudyLog(user_id=user.id,topic_id=task.topic_id,minutes=task.duration_minutes,quiz_score=payload.quiz_score,confidence=payload.confidence))
        gain=4
        if payload.quiz_score is not None: gain += max(-3,min(8,round((payload.quiz_score-60)/10)))
        task.topic.mastery=max(0,min(100,task.topic.mastery+gain))
        if task.topic.mastery>=95: task.topic.completed=True
    db.commit(); return {"ok":True,"mastery":task.topic.mastery}

def readiness_data(db: Session, user: User) -> dict:

    subjects = db.scalars(
        select(Subject)
        .where(Subject.user_id == user.id)
        .options(selectinload(Subject.topics))
    ).all()

    rows = [
        (subject, topic)
        for subject in subjects
        for topic in subject.topics
    ]

    if not rows:
        return {
            "overall": 0,
            "mastery": 0,
            "completion": 0,
            "quiz": None,
            "label": "Add topics",
        }

    weights = [
        max(1, subject.importance)
        for subject, topic in rows
    ]

    mastery = sum(
        topic.mastery * weight
        for (subject, topic), weight
        in zip(rows, weights)
    ) / sum(weights)

    total = db.scalar(
        select(func.count(StudyTask.id))
        .where(
            StudyTask.user_id == user.id
        )
    ) or 0

    done = db.scalar(
        select(func.count(StudyTask.id))
        .where(
            StudyTask.user_id == user.id,
            StudyTask.status == "completed",
        )
    ) or 0

    completion = (
        done / total * 100
        if total
        else 0
    )

    logs = db.scalars(
        select(StudyLog)
        .where(
            StudyLog.user_id == user.id,
            StudyLog.quiz_score.is_not(None),
        )
        .order_by(
            StudyLog.studied_at.desc()
        )
        .limit(12)
    ).all()

    if logs:

        quiz = mean(
            log.quiz_score
            for log in logs
        )

        overall = round(
            0.50 * mastery
            + 0.30 * completion
            + 0.20 * quiz
        )

    else:

        quiz = None

        overall = round(
            0.625 * mastery
            + 0.375 * completion
        )

    label = "Building foundation"

    if overall >= 80:
        label = "Strong revision stage"

    elif overall >= 60:
        label = "Progressing well"

    elif overall >= 40:
        label = "Needs focused revision"

    return {
        "overall": max(
            0,
            min(100, overall)
        ),
        "mastery": round(mastery),
        "completion": round(completion),
        "quiz": (
            round(quiz)
            if quiz is not None
            else None
        ),
        "label": label,
    }
@app.get("/dashboard")
def dashboard(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    today=date.today()
    today_tasks=db.scalars(select(StudyTask).where(StudyTask.user_id==user.id,StudyTask.task_date==today).options(selectinload(StudyTask.subject),selectinload(StudyTask.topic)).order_by(StudyTask.start_minute)).all()
    subjects=db.scalars(select(Subject).where(Subject.user_id==user.id,Subject.exam_date>=today).options(selectinload(Subject.topics)).order_by(Subject.exam_date)).all()
    upcoming=[]
    for s in subjects[:5]:
        avg=round(mean([t.mastery for t in s.topics])) if s.topics else 0
        upcoming.append({"id":s.id,"name":s.name,"exam_date":s.exam_date.isoformat(),"days_left":(s.exam_date-today).days,"mastery":avg,"color":s.color})
    raw_dates={str(row[0])[:10] for row in db.execute(select(func.date(StudyLog.studied_at)).where(StudyLog.user_id==user.id).distinct()).all()}
    streak=0; cursor=today
    while cursor.isoformat() in raw_dates:
        streak+=1; cursor-=timedelta(days=1)
    return {"readiness":readiness_data(db,user),"today_tasks":[serialize_task(t) for t in today_tasks],"upcoming_exams":upcoming,"streak":streak}

@app.get("/readiness")
def readiness(db:Session=Depends(get_db),user:User=Depends(get_current_user)): return readiness_data(db,user)

@app.get("/resources/search")
async def resources(q:str=Query(min_length=2,max_length=150),user:User=Depends(get_current_user)): return await search_resources(q)

@app.post("/ai/coach")
def ai_coach(payload:CoachIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)): return coach(db,user,payload.message)

@app.post("/ai/quiz")
def ai_quiz(payload:QuizIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    topic=db.scalar(select(Topic).join(Subject).where(Topic.id==payload.topic_id,Subject.user_id==user.id))
    if not topic: raise HTTPException(status_code=404,detail="Topic not found")
    return generate_quiz(db,user,topic,payload.count,payload.style)

@app.post("/demo/seed")
def seed_demo(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    existing=db.scalar(select(func.count(Subject.id)).where(Subject.user_id==user.id)) or 0
    if existing: raise HTTPException(status_code=400,detail="Demo data can only be loaded into an empty account")
    today=date.today()
    demos=[(Subject(user_id=user.id,name="Machine Learning",exam_date=today+timedelta(days=24),importance=5,target_score=85,color="#6D5DFB",notes="Concepts and problem solving"),[Topic(name="Linear & Logistic Regression",difficulty=3,mastery=45,estimated_minutes=180),Topic(name="Decision Trees & Random Forests",difficulty=3,mastery=35,estimated_minutes=160),Topic(name="SVM and Kernels",difficulty=4,mastery=25,estimated_minutes=200)]),(Subject(user_id=user.id,name="Computer Networks",exam_date=today+timedelta(days=31),importance=4,target_score=80,color="#00A88B",notes="Diagrams and protocols"),[Topic(name="OSI & TCP/IP Models",difficulty=2,mastery=60,estimated_minutes=120),Topic(name="Routing Algorithms",difficulty=4,mastery=30,estimated_minutes=200),Topic(name="Transport Layer",difficulty=3,mastery=40,estimated_minutes=180)])]
    for subject,topics in demos:
        db.add(subject); db.flush()
        for topic in topics: topic.subject_id=subject.id; db.add(topic)
    db.commit(); return {"ok":True}
