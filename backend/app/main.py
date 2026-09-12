from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routers.academic_year import router as academic_year_router
from app.routers.auth import router as auth_router
from app.routers.class_ import router as class_router
from app.routers.class_subject_requirement import (
    router as class_subject_requirement_router,
)
from app.routers.grade import router as grade_router
from app.routers.lesson import router as lesson_router
from app.routers.room import router as room_router
from app.routers.schedule import router as schedule_router
from app.routers.schedule_version import router as schedule_version_router
from app.routers.school import router as school_router
from app.routers.semester import router as semester_router
from app.routers.subject import router as subject_router
from app.routers.teacher import router as teacher_router
from app.routers.time_slot import router as time_slot_router
from app.services.exceptions import (
    DependentRecordsExistError,
    DuplicateValueError,
    InvalidReferenceError,
    LessonOverProvisionedError,
    PublishedVersionImmutableError,
    ScheduleVersionAlreadyScheduledError,
)

app = FastAPI(title="Elementary School Timetable System")

app.include_router(auth_router)
app.include_router(school_router)
app.include_router(grade_router)
app.include_router(subject_router)
app.include_router(room_router)
app.include_router(time_slot_router)
app.include_router(class_router)
app.include_router(academic_year_router)
app.include_router(semester_router)
app.include_router(teacher_router)
app.include_router(class_subject_requirement_router)
app.include_router(lesson_router)
app.include_router(schedule_version_router)
app.include_router(schedule_router)

# Convention: every service-layer delete_xxx()/create_xxx()/update_xxx() that
# can hit a SQLAlchemy IntegrityError raises one of the three exceptions
# below instead (see app/services/exceptions.py) -- never HTTPException,
# since the service layer must stay independent of FastAPI. Routers should
# NOT catch these themselves; the global handlers here are the single place
# that translates them into HTTP responses, so every future router (for the
# other 10 tables) gets this behavior for free.


@app.exception_handler(DependentRecordsExistError)
def handle_dependent_records_exist(
    request: Request, exc: DependentRecordsExistError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "此資料仍被其他資料參照,無法刪除"},
    )


@app.exception_handler(InvalidReferenceError)
def handle_invalid_reference(
    request: Request, exc: InvalidReferenceError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "關聯的資料不存在,請確認外鍵欄位是否正確"},
    )


@app.exception_handler(DuplicateValueError)
def handle_duplicate_value(
    request: Request, exc: DuplicateValueError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "資料重複或違反欄位限制,請確認輸入內容"},
    )


@app.exception_handler(LessonOverProvisionedError)
def handle_lesson_over_provisioned(
    request: Request, exc: LessonOverProvisionedError
) -> JSONResponse:
    detail = "部分需求的 Lesson 數量已超過 weekly_periods,系統不會自動刪除,請人工確認後處理"
    if any(item.get("includes_fixed_lesson") for item in exc.over_provisioned):
        # Task 28: never let this fact go unmentioned -- a fixed lesson
        # being among the "excess" ones needs a human decision, not a
        # generic over-provisioning message that reads the same either way.
        detail += "。其中包含已手動固定時段的課程,需先手動處理"
    return JSONResponse(
        status_code=409,
        content={
            "detail": detail,
            "over_provisioned": exc.over_provisioned,
        },
    )


@app.exception_handler(ScheduleVersionAlreadyScheduledError)
def handle_schedule_version_already_scheduled(
    request: Request, exc: ScheduleVersionAlreadyScheduledError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": "此版本已有排課結果,系統不會自動覆蓋,"
            "請先刪除既有 Schedule 記錄後再重新執行排課"
        },
    )


@app.exception_handler(PublishedVersionImmutableError)
def handle_published_version_immutable(
    request: Request, exc: PublishedVersionImmutableError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "已發布版本不可修改,請建立新草稿版本"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
