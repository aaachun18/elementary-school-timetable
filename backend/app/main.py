from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routers.class_ import router as class_router
from app.routers.grade import router as grade_router
from app.routers.room import router as room_router
from app.routers.school import router as school_router
from app.routers.subject import router as subject_router
from app.routers.time_slot import router as time_slot_router
from app.services.exceptions import (
    DependentRecordsExistError,
    DuplicateValueError,
    InvalidReferenceError,
)

app = FastAPI(title="Elementary School Timetable System")

app.include_router(school_router)
app.include_router(grade_router)
app.include_router(subject_router)
app.include_router(room_router)
app.include_router(time_slot_router)
app.include_router(class_router)

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
