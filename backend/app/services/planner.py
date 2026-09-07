from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from math import ceil
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..models import StudyTask, Subject, Topic, User


APP_TIMEZONE = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------
# PRIORITY
# ---------------------------------------------------------

def _priority(
    topic: Topic,
    subject: Subject,
    today: date,
) -> float:

    days_left = max(
        (subject.exam_date - today).days,
        0,
    )

    urgency = min(
        1.0,
        (1 / (days_left + 1)) * 10,
    )

    weakness = (
        100 - topic.mastery
    ) / 100

    difficulty = (
        topic.difficulty / 5
    )

    importance = (
        subject.importance / 5
    )

    return round(
        0.38 * weakness
        + 0.27 * urgency
        + 0.20 * importance
        + 0.15 * difficulty,
        4,
    )


# ---------------------------------------------------------
# STUDY STAGES
# ---------------------------------------------------------

def _study_sequence(
    core_sessions: int,
    mastery: int,
    available_days: int,
) -> list[str]:

    sequence: list[str] = []

    # Student already knows the topic reasonably well.
    if mastery >= 70:
        sequence.append("Revision")
    else:
        sequence.append("Learn")

    # Required learning workload.
    for index in range(
        1,
        core_sessions,
    ):
        if index == core_sessions - 1:
            sequence.append("Practice")
        elif index % 2 == 0:
            sequence.append("Practice")
        else:
            sequence.append("Revision")

    # Long-term retention stages.
    if available_days >= 7:
        sequence.append(
            "Active Recall"
        )

    if available_days >= 12:
        sequence.append(
            "Final Revision"
        )

    # Same topic is never planned twice
    # on the same day.
    return sequence[
        :available_days
    ]


# ---------------------------------------------------------
# SPACED TARGET DATES
# ---------------------------------------------------------

def _target_dates(
    start_day: date,
    end_day: date,
    count: int,
    topic_id: int,
) -> list[date]:

    if count <= 0:
        return []

    span = max(
        0,
        (end_day - start_day).days,
    )

    if count == 1 or span == 0:
        return [start_day]

    # Slight deterministic staggering prevents every
    # topic from having its final revision on the same day.
    end_shift = topic_id % 3

    usable_end = max(
        count - 1,
        span - end_shift,
    )

    usable_end = min(
        usable_end,
        span,
    )

    offsets: list[int] = []

    for index in range(count):

        raw_offset = round(
            index
            * usable_end
            / (count - 1)
        )

        if offsets:
            raw_offset = max(
                raw_offset,
                offsets[-1] + 1,
            )

        remaining_events = (
            count - index - 1
        )

        latest_possible = (
            span - remaining_events
        )

        raw_offset = min(
            raw_offset,
            latest_possible,
        )

        raw_offset = max(
            0,
            raw_offset,
        )

        offsets.append(
            raw_offset
        )

    return [
        start_day
        + timedelta(days=offset)
        for offset in offsets
    ]


# ---------------------------------------------------------
# AVAILABLE DAILY TIME SLOTS
# ---------------------------------------------------------

def _valid_slots(
    user: User,
    day: date,
    now: datetime,
    maximum_sessions: int,
    occupied_starts: set[int],
) -> list[int]:

    slots: list[int] = []

    gap = (
        user.session_minutes
        + user.break_minutes
    )

    current_minute = (
        now.hour * 60
        + now.minute
    )

    for slot_index in range(
        maximum_sessions
    ):

        start_minute = (
            user.preferred_start_hour
            * 60
            + slot_index * gap
        )

        # Do not cross midnight.
        if (
            start_minute
            + user.session_minutes
            > 24 * 60
        ):
            continue

        # Never schedule into the past.
        if (
            day == now.date()
            and start_minute
            <= current_minute
        ):
            continue

        if (
            start_minute
            in occupied_starts
        ):
            continue

        slots.append(
            start_minute
        )

    return slots


# ---------------------------------------------------------
# MAIN SMART PLANNER
# ---------------------------------------------------------

def generate_plan(
    db: Session,
    user: User,
    horizon_days: int = 21,
) -> list[StudyTask]:

    now = datetime.now(
        APP_TIMEZONE
    )

    today = now.date()

    horizon_end = (
        today
        + timedelta(
            days=horizon_days - 1
        )
    )

    subjects = db.scalars(
        select(Subject)
        .where(
            Subject.user_id
            == user.id,

            Subject.exam_date
            >= today,
        )
        .options(
            selectinload(
                Subject.topics
            )
        )
        .order_by(
            Subject.exam_date
        )
    ).all()

    # -----------------------------------------------------
    # Preserve already completed work
    # -----------------------------------------------------

    completed_tasks = db.scalars(
        select(StudyTask)
        .where(
            StudyTask.user_id
            == user.id,

            StudyTask.task_date
            >= today,

            StudyTask.status
            == "completed",
        )
        .order_by(
            StudyTask.task_date,
            StudyTask.start_minute,
        )
    ).all()

    completed_by_day = defaultdict(
        list
    )

    completed_by_topic = defaultdict(
        int
    )

    for task in completed_tasks:

        completed_by_day[
            task.task_date
        ].append(task)

        completed_by_topic[
            task.topic_id
        ] += 1

    # Remove only unfinished future plan.
    db.execute(
        delete(
            StudyTask
        ).where(
            StudyTask.user_id
            == user.id,

            StudyTask.task_date
            >= today,

            StudyTask.status
            == "pending",
        )
    )

    db.flush()

    if not subjects:
        db.commit()
        return []

    # -----------------------------------------------------
    # Student capacity
    # -----------------------------------------------------

    session_minutes = (
        user.session_minutes
    )

    daily_capacity = max(
        session_minutes,
        int(
            user.daily_hours
            * 60
        ),
    )

    max_sessions = max(
        1,
        daily_capacity
        // session_minutes,
    )

    # -----------------------------------------------------
    # Build spaced study plans for each topic
    # -----------------------------------------------------

    topic_plans: list[dict] = []

    for subject in subjects:

        # Never plan after the exam.
        effective_end = min(
            horizon_end,
            subject.exam_date
            - timedelta(days=1),
        )

        if effective_end < today:
            continue

        available_days = (
            effective_end - today
        ).days + 1

        for topic in subject.topics:

            if topic.completed:
                continue

            remaining_factor = max(
                0.25,
                (
                    110
                    - topic.mastery
                )
                / 100,
            )

            remaining_minutes = max(
                session_minutes,
                int(
                    topic.estimated_minutes
                    * remaining_factor
                ),
            )

            core_sessions = max(
                1,
                ceil(
                    remaining_minutes
                    / session_minutes
                ),
            )

            sequence = _study_sequence(
                core_sessions,
                topic.mastery,
                available_days,
            )

            target_dates = (
                _target_dates(
                    start_day=today,
                    end_day=effective_end,
                    count=len(sequence),
                    topic_id=topic.id,
                )
            )

            already_completed = min(
                completed_by_topic[
                    topic.id
                ],
                len(sequence),
            )

            topic_plans.append(
                {
                    "subject": subject,
                    "topic": topic,
                    "sequence": sequence,
                    "target_dates": target_dates,
                    "next_index": already_completed,
                    "priority": _priority(
                        topic,
                        subject,
                        today,
                    ),
                    "effective_end": effective_end,
                }
            )

    created: list[
        StudyTask
    ] = []

    last_subject_id = None

    # -----------------------------------------------------
    # Schedule day by day
    # -----------------------------------------------------

    for offset in range(
        horizon_days
    ):

        day = (
            today
            + timedelta(
                days=offset
            )
        )

        completed_today = (
            completed_by_day.get(
                day,
                [],
            )
        )

        completed_minutes = sum(
            task.duration_minutes
            for task
            in completed_today
        )

        remaining_capacity = max(
            0,
            daily_capacity
            - completed_minutes,
        )

        session_limit = min(
            max_sessions,
            remaining_capacity
            // session_minutes,
        )

        if session_limit <= 0:
            continue

        used_topic_ids = {
            task.topic_id
            for task
            in completed_today
        }

        occupied_starts = {
            task.start_minute
            for task
            in completed_today
        }

        subject_counts = defaultdict(
            int
        )

        for task in completed_today:

            subject_counts[
                task.subject_id
            ] += 1

            last_subject_id = (
                task.subject_id
            )

        slots = _valid_slots(
            user=user,
            day=day,
            now=now,
            maximum_sessions=max_sessions,
            occupied_starts=occupied_starts,
        )

        slots = slots[
            :session_limit
        ]

        if not slots:
            continue

        for start_minute in slots:

            candidates = []

            for plan in topic_plans:

                index = plan[
                    "next_index"
                ]

                if (
                    index
                    >= len(
                        plan["sequence"]
                    )
                ):
                    continue

                if (
                    day
                    > plan[
                        "effective_end"
                    ]
                ):
                    continue

                topic = plan[
                    "topic"
                ]

                if (
                    topic.id
                    in used_topic_ids
                ):
                    continue

                target_day = (
                    plan[
                        "target_dates"
                    ][index]
                )

                # Don't drag future revision
                # sessions forward.
                if (
                    target_day
                    > day
                ):
                    continue

                candidates.append(
                    plan
                )

            if not candidates:
                break

            def candidate_score(
                plan: dict,
            ) -> float:

                index = plan[
                    "next_index"
                ]

                target_day = (
                    plan[
                        "target_dates"
                    ][index]
                )

                overdue_days = max(
                    0,
                    (
                        day
                        - target_day
                    ).days,
                )

                subject = plan[
                    "subject"
                ]

                exam_days = max(
                    0,
                    (
                        subject.exam_date
                        - day
                    ).days,
                )

                exam_pressure = min(
                    0.25,
                    (
                        1
                        / (exam_days + 1)
                    )
                    * 3,
                )

                same_subject_penalty = (
                    0.10
                    if subject.id
                    == last_subject_id
                    else 0
                )

                daily_subject_penalty = (
                    subject_counts[
                        subject.id
                    ]
                    * 0.07
                )

                return (
                    plan[
                        "priority"
                    ]
                    + exam_pressure
                    + overdue_days
                    * 0.06
                    - same_subject_penalty
                    - daily_subject_penalty
                )

            chosen = max(
                candidates,
                key=candidate_score,
            )

            subject = chosen[
                "subject"
            ]

            topic = chosen[
                "topic"
            ]

            index = chosen[
                "next_index"
            ]

            task_type = (
                chosen[
                    "sequence"
                ][index]
            )

            task = StudyTask(
                user_id=user.id,
                subject_id=subject.id,
                topic_id=topic.id,
                task_date=day,
                start_minute=start_minute,
                duration_minutes=session_minutes,
                task_type=task_type,
                status="pending",
                priority=chosen[
                    "priority"
                ],
            )

            db.add(task)

            created.append(
                task
            )

            chosen[
                "next_index"
            ] += 1

            used_topic_ids.add(
                topic.id
            )

            subject_counts[
                subject.id
            ] += 1

            last_subject_id = (
                subject.id
            )

    db.commit()

    for task in created:
        db.refresh(task)

    return created