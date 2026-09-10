from fastapi import FastAPI

app = FastAPI(title="Elementary School Timetable System")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
