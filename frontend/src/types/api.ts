// Generic shape of every error response produced by backend/app/main.py's
// global exception handlers and FastAPI's own HTTPException -- all of them
// return at least {"detail": "..."} (some, like the over-provisioned-lesson
// case, add extra fields, but `detail` is always present and is the one
// piece every error-handling call site can rely on).
export interface ApiErrorResponse {
  detail: string;
}
