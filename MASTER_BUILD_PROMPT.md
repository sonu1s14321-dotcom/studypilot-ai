# MASTER BUILD PROMPT — StudyPilot AI

You are a senior full-stack engineer, Python engineer, AI/ML engineer, UX designer, QA engineer, security reviewer and deployment engineer.

Build and improve **StudyPilot AI**, a production-style AI-powered smart study planner for students preparing for exams.

## Product goal
Turn a student's subjects, exam dates, topic list, difficulty, current mastery, available study time, study-session length, completed work and quiz performance into a realistic teacher-style daily study plan.

The system must help the student know:
1. what to study,
2. when to study,
3. how long to study,
4. when to revise,
5. when to practise questions,
6. which weak areas deserve priority,
7. how prepared the student currently appears based on recorded progress.

## Mandatory stack
- React + Vite frontend
- Python + FastAPI backend
- SQLAlchemy ORM
- SQLite locally
- PostgreSQL-compatible deployment database (Supabase compatible)
- Secure password hashing + JWT
- httpx for external APIs
- Optional Gemini Developer API through the current `google-genai` Python SDK
- Open Library + OpenAlex for free learning-resource discovery
- Vercel-compatible frontend deployment
- Render-compatible backend deployment
- No paid API may be mandatory

## Critical architecture rule
**Do not use an LLM to generate the core timetable.**

The timetable must be deterministic Python logic so it is reproducible, works without AI quota, is explainable and cannot silently ignore student constraints.

AI may enhance:
- tutoring,
- explanations,
- revision advice,
- active-recall questions,
- quiz generation,
- summaries of preparation.

If AI is unavailable, the app must fall back gracefully.

## Scheduling algorithm
For each topic calculate priority from:
- weakness / low mastery,
- days remaining until exam,
- difficulty,
- subject importance,
- remaining estimated workload.

Rules:
- never exceed configured daily study capacity,
- avoid the same subject in every consecutive slot when alternatives exist,
- use Learn / Revision / Practice tasks,
- never schedule after that subject's exam,
- preserve completed sessions when regenerating,
- replace unfinished future sessions,
- never claim the resulting plan guarantees marks.

## Readiness score
Show a transparent indicator based on:
- weighted topic mastery,
- plan completion,
- recent quiz performance.

Show the components. State that this is a planning indicator, not an exam-mark prediction.

## Required screens
1. Authentication
2. Dashboard
3. Smart Planner
4. Subjects & Topics
5. AI Coach
6. Learning Resources
7. Settings

## Dashboard
Show readiness, today's remaining focus time, study streak, today's plan, upcoming exams and subject mastery.

## Subjects
Allow subject name, exam date, importance 1–5, target score, color, topic name, topic difficulty 1–5, topic mastery 0–100 and estimated study minutes.

Never invent syllabus data. User-entered syllabus is authoritative.

## AI teacher behavior
- Practical, concise and teacher-like.
- Prioritize active recall, spaced review, timed practice and realistic workload.
- Never invent progress, deadlines or chapters.
- Never guarantee marks.
- Say what information is missing when uncertain.

## Free resources
Open Library:
- low-volume human book discovery only,
- identify the app with User-Agent/contact email,
- no scraping,
- no bulk harvesting.

OpenAlex:
- scholarly discovery,
- support keyless and optional free-key usage,
- keep keys server-side,
- handle quota/rate/network failure gracefully.

Resource API failure must never break scheduling.

## Security
- Hash passwords.
- Never store plaintext passwords.
- Keep JWT/API secrets in backend environment variables.
- Never expose Gemini/OpenAlex secrets in React.
- Restrict CORS to configured frontend origins.
- Validate inputs.
- Enforce user ownership for every subject/topic/task.
- Never commit `.env`.
- Use HTTPS in production.

## UI
Create a polished education SaaS interface:
- dark sidebar,
- bright content area,
- excellent spacing/typography,
- responsive mobile nav,
- subtle cards/shadows,
- subject color coding,
- readiness ring,
- accessible labels,
- good empty/error/loading states.

Avoid unnecessary UI dependencies if React + CSS can implement the feature reliably.

## Reliability rules
Every external request needs timeout, exception handling and a fallback.
Do not add a mandatory paid dependency.
Do not hardcode secrets.

## QA checklist
Before calling the project finished, test:
- register/login/wrong password,
- create subject,
- past exam rejection,
- add topics,
- generate schedule,
- daily capacity respected,
- no scheduling after exam,
- completed tasks remain after regeneration,
- completion updates mastery but stays 0–100,
- dashboard/readiness with and without quiz history,
- AI missing => built-in coach works,
- resource API failure is graceful,
- mobile UI,
- CORS,
- PostgreSQL connection,
- no secret in frontend bundle,
- `npm run build`,
- production FastAPI start command.

## Deployment
Backend command:
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Frontend variable:
`VITE_API_URL`

Provide exact GitHub → database → Render → Vercel → CORS steps.

## Bug-fixing behavior
When a bug appears:
1. identify root cause,
2. modify the smallest safe area,
3. preserve working behavior,
4. retest.

Prefer simple, safe and deployable solutions over unnecessary complexity.
