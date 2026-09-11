"""Seed a complete, deliberately generous test dataset for exercising the
scheduler end-to-end (generate-lessons -> run-scheduler) without having to
click through Swagger UI by hand.

Design choice: Service layer, not the HTTP API
------------------------------------------------
This script calls app.services.* functions directly against a real Session
(the exact same functions the routers call), rather than going through
FastAPI/TestClient/requests. Reasoning:
- It reuses every bit of the routers' underlying validation (FK existence,
  UNIQUE/CHECK violations -> the same DuplicateValueError/
  InvalidReferenceError the API would raise) for free, since that logic
  lives in the service layer, not in the routers themselves.
- It's much faster to iterate with (no HTTP roundtrips, no JWT/auth setup
  needed for a trusted local script).
- It deliberately does NOT import app.main -- nothing here constructs the
  FastAPI app object or touches routers, so there is no FastAPI-related
  side effect at all from running this script (see the impact-assessment
  notes in the Task 24 report).

Impact assessment (Task 24) -- summary, see the full report for detail:
1. No side-effect-triggering imports: only app.config / app.database /
   app.models / app.schemas / app.services.* are imported. app.main (and
   therefore every app.routers.* module) is never imported.
2. Dev vs test database: app.config.Settings only declares `database_url`
   (from DATABASE_URL) as a field -- TEST_DATABASE_URL isn't a recognized
   field at all (see SettingsConfigDict(extra="ignore")), so there is no
   code path by which this script could end up reading TEST_DATABASE_URL.
   The resolved URL is also printed (password redacted) before anything is
   written, as a final human sanity check.
3. Not pytest-collectible: this file's name starts with "seed_", matching
   neither of pytest's default collection patterns (test_*.py / *_test.py),
   and it lives under scripts/, outside the `tests/` path that this
   project's test invocations always pass explicitly.
4. tests/ uses a completely separate database (TEST_DATABASE_URL) and its
   own engine (tests/conftest.py) -- this script never imports anything
   from tests/, so it cannot affect it, and running `pytest tests/ -v`
   cannot import this script either (see point 3).

Usage:
    python scripts/seed_test_data.py             # first run / clean slate
    python scripts/seed_test_data.py --confirm    # wipe a PREVIOUS run of
                                                   # this exact script first
                                                   # (see manifest notes
                                                   # below), then reseed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# scripts/seed_test_data.py -> parent.parent is the repo root, which holds
# backend/ (the `app` package). Same cross-directory import bootstrap as
# backend/alembic/env.py and tests/conftest.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import get_session_local  # noqa: E402
from app.models.academic_year import AcademicYear, Semester  # noqa: E402
from app.models.class_subject_requirement import ClassSubjectRequirement  # noqa: E402
from app.models.grade_class import Class, Grade  # noqa: E402
from app.models.lesson import Lesson  # noqa: E402
from app.models.schedule import Schedule  # noqa: E402
from app.models.schedule_version import ScheduleVersion  # noqa: E402
from app.models.school import School  # noqa: E402
from app.models.subject import Subject  # noqa: E402
from app.models.teacher import Teacher, TeacherAvailability, TeacherSubject  # noqa: E402
from app.models.time_slot import TimeSlot  # noqa: E402
from app.schemas.academic_year import AcademicYearCreate  # noqa: E402
from app.schemas.class_ import ClassCreate  # noqa: E402
from app.schemas.class_subject_requirement import (  # noqa: E402
    ClassSubjectRequirementCreate,
)
from app.schemas.grade import GradeCreate  # noqa: E402
from app.schemas.schedule_version import ScheduleVersionCreate  # noqa: E402
from app.schemas.school import SchoolCreate  # noqa: E402
from app.schemas.semester import SemesterCreate  # noqa: E402
from app.schemas.subject import SubjectCreate  # noqa: E402
from app.schemas.teacher import TeacherCreate  # noqa: E402
from app.schemas.time_slot import TimeSlotCreate  # noqa: E402
from app.services import academic_year as academic_year_service  # noqa: E402
from app.services import class_ as class_service  # noqa: E402
from app.services import class_subject_requirement as csr_service  # noqa: E402
from app.services import grade as grade_service  # noqa: E402
from app.services import schedule_version as schedule_version_service  # noqa: E402
from app.services import school as school_service  # noqa: E402
from app.services import semester as semester_service  # noqa: E402
from app.services import subject as subject_service  # noqa: E402
from app.services import teacher as teacher_service  # noqa: E402
from app.services import time_slot as time_slot_service  # noqa: E402

# Distinctive, unrealistic marker values -- chosen specifically so they can
# never collide with genuine dev data (a real academic year is never 9999;
# a real elementary grade level is never 901-903), used both for human
# readability in Swagger UI and as the "does seed data already exist"
# detection anchor.
SEED_YEAR = 9999
SEED_TAG = "[SEED]"
GRADE_LEVELS = [901, 902, 903]
CLASSES_PER_GRADE = 2
SUBJECT_NAMES = ["國語", "數學", "英語", "自然", "藝術"]
WEEKDAYS = [1, 2, 3, 4, 5]
PERIODS_PER_DAY = [1, 2, 3, 4, 5, 6]
TEACHER_NAMES = ["王老師", "林老師", "陳老師", "李老師", "楊老師"]
# teacher index -> subject names they're qualified for. Every subject has
# >= 2 qualified teachers, so no single teacher is a bottleneck.
TEACHER_QUALIFICATIONS = [
    ["國語", "數學"],
    ["國語", "英語"],
    ["數學", "自然"],
    ["英語", "藝術"],
    ["自然", "藝術"],
]

MANIFEST_PATH = Path(__file__).resolve().parent / ".seed_manifest.json"


def _redact_db_url(url: str) -> str:
    """Hide the password portion of a SQLAlchemy URL for safe printing."""
    if "@" not in url or "://" not in url:
        return url
    scheme_and_creds, host_part = url.rsplit("@", 1)
    scheme, creds = scheme_and_creds.split("://", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host_part}"


def _load_manifest() -> dict | None:
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _wipe_previous_seed(db: Session, manifest: dict) -> None:
    """Delete EXACTLY the rows recorded in a previous run's manifest, in
    dependency order (children before parents). Using the manifest's exact
    IDs -- rather than guessing from names/markers -- means this can never
    touch a row it didn't itself create, even if unrelated dev data happens
    to share a naming convention.
    """
    sv_id = manifest["schedule_version_id"]
    semester_id = manifest["semester_id"]
    academic_year_id = manifest["academic_year_id"]
    school_id = manifest["school_id"]
    requirement_ids = manifest["requirement_ids"]
    teacher_ids = manifest["teacher_ids"]
    class_ids = manifest["class_ids"]
    grade_ids = manifest["grade_ids"]
    subject_ids = manifest["subject_ids"]
    time_slot_ids = manifest["time_slot_ids"]

    db.execute(delete(Schedule).where(Schedule.schedule_version_id == sv_id))
    db.execute(
        delete(Lesson).where(Lesson.class_subject_requirement_id.in_(requirement_ids))
    )
    db.execute(
        delete(ClassSubjectRequirement).where(
            ClassSubjectRequirement.id.in_(requirement_ids)
        )
    )
    db.execute(delete(ScheduleVersion).where(ScheduleVersion.id == sv_id))
    db.execute(delete(Semester).where(Semester.id == semester_id))
    db.execute(delete(AcademicYear).where(AcademicYear.id == academic_year_id))
    db.execute(
        delete(TeacherAvailability).where(
            TeacherAvailability.teacher_id.in_(teacher_ids)
            | TeacherAvailability.time_slot_id.in_(time_slot_ids)
        )
    )
    db.execute(delete(TeacherSubject).where(TeacherSubject.teacher_id.in_(teacher_ids)))
    db.execute(delete(Teacher).where(Teacher.id.in_(teacher_ids)))
    db.execute(delete(Class).where(Class.id.in_(class_ids)))
    db.execute(delete(Grade).where(Grade.id.in_(grade_ids)))
    db.execute(delete(Subject).where(Subject.id.in_(subject_ids)))
    db.execute(delete(TimeSlot).where(TimeSlot.id.in_(time_slot_ids)))
    db.execute(delete(School).where(School.id == school_id))
    db.commit()


def _seed(db: Session) -> dict:
    school = school_service.create_school(
        db, SchoolCreate(name=f"{SEED_TAG} 測試國小")
    )
    academic_year = academic_year_service.create_academic_year(
        db, AcademicYearCreate(year=SEED_YEAR)
    )
    semester = semester_service.create_semester(
        db, SemesterCreate(academic_year_id=academic_year.id, number=1)
    )

    grades = [
        grade_service.create_grade(
            db, GradeCreate(name=f"{SEED_TAG} 第{i + 1}級", level=level)
        )
        for i, level in enumerate(GRADE_LEVELS)
    ]

    classes: list[Class] = []
    for grade in grades:
        for section in range(CLASSES_PER_GRADE):
            label = chr(ord("A") + section)
            classes.append(
                class_service.create_class(
                    db,
                    ClassCreate(
                        grade_id=grade.id, name=f"{SEED_TAG} {grade.level}班{label}"
                    ),
                )
            )

    subjects = {
        name: subject_service.create_subject(
            db, SubjectCreate(name=f"{SEED_TAG} {name}")
        )
        for name in SUBJECT_NAMES
    }

    time_slots: list[TimeSlot] = []
    for weekday in WEEKDAYS:
        for period in PERIODS_PER_DAY:
            time_slots.append(
                time_slot_service.create_time_slot(
                    db, TimeSlotCreate(weekday=weekday, period=period)
                )
            )

    teachers: list[Teacher] = []
    for name, qualified_subjects in zip(
        TEACHER_NAMES, TEACHER_QUALIFICATIONS, strict=True
    ):
        teacher = teacher_service.create_teacher(
            db,
            TeacherCreate(
                name=f"{SEED_TAG} {name}",
                min_weekly_periods=0,
                # Generous on purpose: with only 30 time slots and no
                # requirement needing more than 4 weekly periods, nothing
                # here is meant to be a tight constraint.
                max_weekly_periods=20,
            ),
        )
        for subject_name in qualified_subjects:
            teacher_service.add_teacher_subject(
                db, teacher.id, subjects[subject_name].id
            )
        teachers.append(teacher)

    # 8 requirements across the 6 classes. Only two pin a required_teacher
    # (per the Task 24 spec: "大部分不指定...只留 1-2 筆示範"), and both
    # pinned teachers are: (a) actually qualified for that subject, and (b)
    # nowhere near their max_weekly_periods or availability limits -- see
    # scheduling_engine/static_feasibility.py (Task 23), which would reject
    # this dataset outright if either weren't true.
    teacher_by_name = {t.name.removeprefix(f"{SEED_TAG} "): t for t in teachers}
    requirement_specs = [
        (classes[0], "國語", 4, None),
        (classes[0], "數學", 4, teacher_by_name["王老師"].id),
        (classes[1], "英語", 3, None),
        (classes[2], "自然", 3, None),
        (classes[3], "藝術", 2, None),
        (classes[4], "國語", 4, None),
        (classes[5], "數學", 4, teacher_by_name["陳老師"].id),
        (classes[4], "英語", 2, None),
    ]
    requirements: list[ClassSubjectRequirement] = []
    for class_obj, subject_name, weekly_periods, required_teacher_id in requirement_specs:
        requirements.append(
            csr_service.create_class_subject_requirement(
                db,
                ClassSubjectRequirementCreate(
                    semester_id=semester.id,
                    class_id=class_obj.id,
                    subject_id=subjects[subject_name].id,
                    weekly_periods=weekly_periods,
                    required_teacher_id=required_teacher_id,
                ),
            )
        )

    schedule_version = schedule_version_service.create_schedule_version(
        db,
        ScheduleVersionCreate(
            semester_id=semester.id, version_number=1, status="DRAFT"
        ),
    )

    manifest = {
        "school_id": school.id,
        "academic_year_id": academic_year.id,
        "semester_id": semester.id,
        "schedule_version_id": schedule_version.id,
        "grade_ids": [g.id for g in grades],
        "class_ids": [c.id for c in classes],
        "subject_ids": [s.id for s in subjects.values()],
        "time_slot_ids": [t.id for t in time_slots],
        "teacher_ids": [t.id for t in teachers],
        "requirement_ids": [r.id for r in requirements],
    }

    print(f"School: 1 ({school.name}, id={school.id})")
    print(f"AcademicYear/Semester: year={academic_year.year}, semester_id={semester.id}")
    print(f"Grades: {len(grades)}, Classes: {len(classes)}")
    print(f"Subjects: {len(subjects)} ({', '.join(subjects)})")
    print(f"TimeSlots: {len(time_slots)} ({len(WEEKDAYS)} days x {len(PERIODS_PER_DAY)} periods)")
    print(f"Teachers: {len(teachers)}")
    print(f"ClassSubjectRequirements: {len(requirements)} "
          f"({sum(1 for *_, rt in requirement_specs if rt is not None)} with required_teacher_id)")
    print(f"ScheduleVersion: id={schedule_version.id} (status=DRAFT, version_number=1)")
    print()
    print("Next step -- copy/paste ready:")
    print(f"  POST /api/v1/schedule-versions/{schedule_version.id}/generate-lessons")
    print(f"  POST /api/v1/schedule-versions/{schedule_version.id}/run-scheduler")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Wipe a previous run of this script (tracked in "
        f"{MANIFEST_PATH.name}) before reseeding. Required whenever "
        "previously-seeded data is detected; refused otherwise to avoid "
        "accidental data loss.",
    )
    args = parser.parse_args()

    settings = get_settings()
    print(f"Connecting to: {_redact_db_url(settings.database_url)}")

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        manifest = _load_manifest()
        existing_marker = db.scalars(
            select(AcademicYear).where(AcademicYear.year == SEED_YEAR)
        ).first()

        if manifest is not None:
            if not args.confirm:
                print(
                    f"\nSeed data from a previous run was found (tracked in "
                    f"{MANIFEST_PATH}).\n"
                    "Re-run with --confirm to wipe it and reseed:\n"
                    "  python scripts/seed_test_data.py --confirm"
                )
                sys.exit(1)
            print("Wiping previous seed data...")
            _wipe_previous_seed(db, manifest)
            MANIFEST_PATH.unlink(missing_ok=True)
        elif existing_marker is not None:
            # Orphaned data: an AcademicYear(year=9999) exists, but we have
            # no manifest recording what else belongs to it -- deleting
            # blind here risks touching rows this script didn't create.
            print(
                f"\nAn AcademicYear with year={SEED_YEAR} already exists "
                f"(id={existing_marker.id}), but {MANIFEST_PATH.name} is "
                "missing, so this script doesn't know what else it is "
                "safe to delete. Refusing to proceed -- please clean this "
                "up manually (or restore the manifest file) before "
                "re-running."
            )
            sys.exit(1)

        print("Seeding test data...\n")
        new_manifest = _seed(db)
        _save_manifest(new_manifest)
    finally:
        db.close()


if __name__ == "__main__":
    main()
