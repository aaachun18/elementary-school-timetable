// Generic shape of every error response produced by backend/app/main.py's
// global exception handlers and FastAPI's own HTTPException -- all of them
// return at least {"detail": "..."} (some, like the over-provisioned-lesson
// case, add extra fields, but `detail` is always present and is the one
// piece every error-handling call site can rely on).
export interface ApiErrorResponse {
  detail: string;
  // Only on 「此資料仍被其他資料參照，無法刪除」: what to delete first.
  delete_steps?: unknown;
  // Only on a class in use (code CLASS_IN_USE): how many 排課紀錄 use it.
  code?: unknown;
  record_count?: unknown;
}
