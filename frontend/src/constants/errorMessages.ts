import axios from "axios";
import type { ApiErrorResponse } from "../types/api";

// Known backend error message (English, verbatim from `detail`) -> 繁體中文.
// This is a translation, not a rewording: the reason reported to the user
// stays exactly what the backend said, just in Chinese instead of English
// -- it does not weaken the "忠實呈現後端內容" (faithfully show the
// backend's content) principle from docs/FRONTEND_REQUIREMENTS.md 第 6 節.
//
// Only messages the backend is actually known to produce belong here.
// Keying by the exact string is intentionally simple and admittedly
// brittle (a backend wording change silently stops matching), but the
// fallback below means that failure mode is safe: an untranslated message
// still displays, in English, rather than disappearing or being replaced
// by a vague generic string.
//
// Task 54: every VALUE here (the Chinese actually shown to the user) uses
// full-width punctuation (，。：；！？（）), consistent across the whole
// frontend. The KEYS never change for this -- they're the backend's own
// literal `detail` string (half-width ASCII, however the backend happens
// to write it), used for an exact match against what main.py actually
// sends; changing a key's punctuation would just break the lookup.
const KNOWN_ERROR_MESSAGES: Record<string, string> = {
  // POST /api/v1/auth/login -- backend/app/routers/auth.py's only 401 case.
  "Incorrect username or password": "帳號或密碼錯誤",
  // Task 42's CRUD tables (School/Subject/Room) -- each router's own
  // literal 404 detail string for GET one/PATCH/DELETE on an id that
  // doesn't exist, e.g. deleted concurrently by someone else.
  "School not found": "此學校資料已不存在，請重新整理頁面",
  "Subject not found": "此科目資料已不存在，請重新整理頁面",
  "Room not found": "此教室資料已不存在，請重新整理頁面",
  // Task 44's CRUD tables (AcademicYear/Semester/Class) -- same "deleted
  // concurrently by someone else" 404 case as above.
  "AcademicYear not found": "此學年度資料已不存在，請重新整理頁面",
  "Semester not found": "此學期資料已不存在，請重新整理頁面",
  "Class not found": "此班級資料已不存在，請重新整理頁面",
  // Task 45's CRUD tables (Grade/Teacher/TimeSlot) -- same "deleted
  // concurrently by someone else" 404 case as above.
  "Grade not found": "此年級資料已不存在，請重新整理頁面",
  "Teacher not found": "此教師資料已不存在，請重新整理頁面",
  "TimeSlot not found": "此時段資料已不存在，請重新整理頁面",
  // Task 46's teacher sub-resources (任教資格/不可用時段) -- the DELETE
  // endpoint's 404 when the record was already removed (e.g. by someone
  // else, concurrently).
  "Qualification record not found": "此任教資格已不存在，請重新整理頁面",
  "Unavailable-slot record not found": "此不可用時段已不存在，請重新整理頁面",
  // Task 47's CRUD table (ClassSubjectRequirement) -- same "deleted
  // concurrently by someone else" 404 case as above.
  "ClassSubjectRequirement not found": "此排課需求已不存在，請重新整理頁面",
  // Task 53: these three were never actually unreachable (every one of
  // Lesson/Schedule/ScheduleVersion's own GET one/PATCH/DELETE routes can
  // 404 this way), they just hadn't been added here yet -- same "deleted
  // concurrently by someone else" case as everything else in this table.
  "Lesson not found": "此課程已不存在，請重新整理頁面",
  "Schedule not found": "此排課結果已不存在，請重新整理頁面",
  "ScheduleVersion not found": "此排課版本已不存在，請重新整理頁面",
  // Task 59: account management (帳號管理) and register. "User not found"
  // is backend/app/routers/users.py's own 404; the other three come from
  // backend/app/core/dependencies.py (require_admin's 403,
  // get_current_user's 401) and FastAPI's own OAuth2PasswordBearer 401
  // when no token is sent at all. A 401 also sends the user back to
  // /login (api/client.ts), but the message is still translated in case
  // it is ever shown first.
  "User not found": "此帳號已不存在，請重新整理頁面",
  "This action requires ADMIN role": "此操作需要管理員權限",
  "Not authenticated": "尚未登入，請重新登入",
  "Could not validate credentials": "登入狀態已失效，請重新登入",
  // Task 53 originally added entries here for
  // handle_schedule_version_already_scheduled()'s and
  // handle_lesson_over_provisioned()'s messages, which at the time had
  // "Schedule"/"Lesson"/"weekly_periods" baked into otherwise-Chinese
  // text. backend/app/main.py's own wording has since been edited
  // directly to drop those English fragments (and use full-width
  // punctuation) -- the backend now already sends correct, displayable
  // Chinese for both, so no translation entry is needed here any more.
};

// Falls back to the original (untranslated) message when it isn't in the
// table above -- never swallowed, never replaced with a generic string.
export function translateErrorMessage(message: string): string {
  return KNOWN_ERROR_MESSAGES[message] ?? message;
}

// Task 42: the same "pull `detail` out of an axios error, translate it,
// fall back to a generic message" sequence useResource.ts already
// does internally -- pulled out here so per-row CRUD error handling
// (useCrudList.ts) doesn't have to duplicate it. Every global exception
// handler in backend/app/main.py, and every router's own HTTPException,
// returns at least {detail: "..."} (see types/api.ts), so this covers
// every error shape a create/update/delete call can produce EXCEPT
// run-scheduler's structured 422 (RunSchedulerFailureResponse), which has
// its own dedicated handling in SchedulerConsole.tsx and never flows
// through here.
//
// Task 60: FastAPI's own request-validation 422 is the one other shape --
// its `detail` is an ARRAY of {loc, msg, type, ...} items, not a string.
// Before this, that array fell through to the connectivity message below,
// which was simply wrong (the server did answer). It is now turned into
// readable Chinese by formatValidationErrorDetail().
//
// The connectivity message is reserved for "no response at all". A
// response that is neither of the two shapes above (e.g. a plain-text 500,
// an unexpected object) means the server DID answer, just not in a form
// this function understands -- that gets SERVER_RESPONSE_ERROR_MESSAGE.
const NO_RESPONSE_MESSAGE = "無法連線到伺服器，請確認後端服務是否啟動。";
const SERVER_RESPONSE_ERROR_MESSAGE = "伺服器回應異常，請稍後再試或聯絡管理員";

export function extractApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorResponse>(error) && typeof error.response?.data?.detail === "string") {
    return translateErrorMessage(error.response.data.detail);
  }
  if (axios.isAxiosError(error) && isValidationErrorResponse(error.response)) {
    return formatValidationErrorDetail(error.response.data.detail);
  }
  if (axios.isAxiosError(error) && error.response !== undefined) {
    return SERVER_RESPONSE_ERROR_MESSAGE;
  }
  return NO_RESPONSE_MESSAGE;
}

// --- Task 60: FastAPI 422 validation-error array -------------------------

// One item of FastAPI's 422 `detail` array (pydantic's ValidationError
// entries). Only the two fields read below are declared; the rest (loc,
// input, ctx, url) are deliberately ignored -- `loc` is an English field
// path, not something to show a user.
interface ValidationErrorItem {
  msg?: unknown;
  type?: unknown;
}

interface ValidationErrorResponse {
  status: number;
  data: { detail: ValidationErrorItem[] };
}

const HTTP_UNPROCESSABLE_ENTITY = 422;
const MAX_VALIDATION_MESSAGES = 3;

// pydantic prefixes a custom validator's ValueError message with this
// (e.g. backend/app/schemas/user.py's password rule arrives as
// "Value error, 密碼至少需要 8 個字元").
const PYDANTIC_VALUE_ERROR_PREFIX = "Value error, ";

const MISSING_FIELD_MESSAGE = "缺少必填欄位";
const INVALID_FORMAT_MESSAGE = "欄位格式不正確";
const INVALID_CHOICE_MESSAGE = "欄位值不在允許的選項內";
const GENERIC_VALIDATION_MESSAGE = "輸入的資料格式不正確，請檢查後再送出";

// pydantic error `type` -> short Chinese. Anything not listed here uses
// GENERIC_VALIDATION_MESSAGE.
const VALIDATION_TYPE_MESSAGES: Record<string, string> = {
  missing: MISSING_FIELD_MESSAGE,
  string_type: INVALID_FORMAT_MESSAGE,
  int_type: INVALID_FORMAT_MESSAGE,
  int_parsing: INVALID_FORMAT_MESSAGE,
  float_type: INVALID_FORMAT_MESSAGE,
  float_parsing: INVALID_FORMAT_MESSAGE,
  bool_type: INVALID_FORMAT_MESSAGE,
  bool_parsing: INVALID_FORMAT_MESSAGE,
  literal_error: INVALID_CHOICE_MESSAGE,
  enum: INVALID_CHOICE_MESSAGE,
};

const CJK_CHARACTER = /[一-鿿]/;

function isValidationErrorResponse(
  response: { status: number; data: unknown } | undefined,
): response is ValidationErrorResponse {
  if (response === undefined || response.status !== HTTP_UNPROCESSABLE_ENTITY) {
    return false;
  }
  const data = response.data;
  return (
    typeof data === "object" &&
    data !== null &&
    "detail" in data &&
    Array.isArray((data as { detail: unknown }).detail)
  );
}

// A backend-written Chinese message (custom validator) is shown as-is;
// otherwise the pydantic error type decides the wording.
function getValidationItemMessage(item: ValidationErrorItem): string {
  if (typeof item.msg === "string" && item.msg.startsWith(PYDANTIC_VALUE_ERROR_PREFIX)) {
    const customMessage = item.msg.slice(PYDANTIC_VALUE_ERROR_PREFIX.length);
    if (CJK_CHARACTER.test(customMessage)) {
      return customMessage;
    }
  }
  // hasOwnProperty, not `in`: `in` would also match inherited keys such as
  // "toString".
  if (
    typeof item.type === "string" &&
    Object.prototype.hasOwnProperty.call(VALIDATION_TYPE_MESSAGES, item.type)
  ) {
    return VALIDATION_TYPE_MESSAGES[item.type];
  }
  return GENERIC_VALIDATION_MESSAGE;
}

function formatValidationErrorDetail(detail: ValidationErrorItem[]): string {
  const messages = detail.map((item) =>
    typeof item === "object" && item !== null
      ? getValidationItemMessage(item)
      : GENERIC_VALIDATION_MESSAGE,
  );
  const uniqueMessages = Array.from(new Set(messages)).slice(0, MAX_VALIDATION_MESSAGES);
  if (uniqueMessages.length === 0) {
    return GENERIC_VALIDATION_MESSAGE;
  }
  return uniqueMessages.join("；");
}

// Task 36: RunSchedulerFailureResponse.failure_type -> 繁體中文 overall
// conclusion. Exhaustively covers every value SchedulerFailureDetail.failure_type
// can hold (backend/app/schemas/scheduler.py): the 3 BacktrackingResult search
// outcomes it mirrors 1:1 (DEFINITELY_INFEASIBLE/SEARCH_LIMIT_EXCEEDED/TIMEOUT),
// plus its own 2 non-search-level labels (REQUIREMENT_PERIODS_MISMATCH/
// STATIC_CHECK_FAILED). Same fallback stance as KNOWN_ERROR_MESSAGES above: an
// unrecognized value still displays (the raw string), never blank.
const FAILURE_TYPE_MESSAGES: Record<string, string> = {
  DEFINITELY_INFEASIBLE: "確定無法排出課表",
  SEARCH_LIMIT_EXCEEDED: "排課嘗試次數已達上限，但不代表無解，可調整條件後重新嘗試",
  TIMEOUT: "排課時間已達上限，但不代表無解，可調整條件後重新嘗試",
  REQUIREMENT_PERIODS_MISMATCH: "每堂課都已排入時段，但部分需求的每週節數與實際排定堂數不符",
  STATIC_CHECK_FAILED: "排課前的可行性檢查未通過（尚未開始搜尋課表）",
};

export function translateFailureType(failureType: string): string {
  return FAILURE_TYPE_MESSAGES[failureType] ?? failureType;
}

// ConstraintViolation.type (scheduling_engine/constraints/base.py) ->
// 繁體中文樣板. Placeholders ({teacherName}/{className}/{subjectName}/
// {roomName}/{timeSlotLabel}/{requirementLabel}/{inactiveEntities}) are
// substituted by frontend/src/utils/failureDiagnostics.ts, which also
// supplies "" for a placeholder whose underlying id is null (never the
// literal text "null").
//
// Exhaustive list, one entry per VIOLATION_TYPE constant found by scanning:
// - scheduling_engine/constraints/*.py: H1/H2/H3/H4/H5/H6/H7/H8/H9/H11/H12
//   (no H10 constraint exists in this codebase)
// - scheduling_engine/algorithms/resources.py's no_candidate_teacher_violation():
//   NO_CANDIDATE_TEACHER, H6_REQUIRED_TEACHER_NOT_QUALIFIED
// - scheduling_engine/static_feasibility.py's three checks:
//   STATIC_TEACHER_WORKLOAD_EXCEEDED, STATIC_TEACHER_AVAILABILITY_INSUFFICIENT,
//   STATIC_INACTIVE_ENTITY_CONFLICT
// - backend/app/services/schedule_check.py's own two (Task 68; only ever in
//   GET /schedule-versions/{id}/check, never in a run-scheduler failure):
//   INCOMPLETE_SCHEDULE_ROW ({missingFields}), FIXED_TIME_SLOT_MISMATCH
//   ({fixedTimeSlotLabel}, looked up through the Lesson -- the violation
//   itself only carries the actual time slot)
//
// Any type not in this table (e.g. a future constraint) falls back to the
// violation's own English `message` -- see getViolationSentence().
//
// Task 37: every template is a plain statement ending in "！", with no
// embedded suggested-action clause -- FailureDiagnostics.tsx now renders a
// second, separate line ("請至 {頁面} 修正", via
// constants/violationPageMapping.ts) instead of the removed suggested_action
// text, so a template repeating "請...調整/改指派" here would just duplicate
// that second line in different words.
export const VIOLATION_TYPE_TEMPLATES: Record<string, string> = {
  H1_TEACHER_CONFLICT: "{teacherName}在{timeSlotLabel}被同時排定兩堂課！",
  H2_CLASS_CONFLICT: "{className}在{timeSlotLabel}被同時排定兩堂課！",
  H3_ROOM_CONFLICT: "{roomName}在{timeSlotLabel}被同時排定兩堂課！",
  H4_TEACHER_AVAILABILITY:
    "{teacherName}在{timeSlotLabel}已標記為不可排課，但仍被排入該時段！",
  H5_TEACHER_QUALIFICATION: "{teacherName}未具備教授{subjectName}的資格！",
  H6_REQUIRED_TEACHER:
    "{className}的{subjectName}指定了特定教師，但實際排定的教師（{teacherName}）與指定教師不符！",
  H7_WEEKLY_PERIODS: "{requirementLabel}的每週排課節數，與需求設定的節數不符！",
  H8_TEACHER_MAX_WORKLOAD: "{teacherName}的排課總節數超過每週授課節數上限！",
  H9_ROOM_TYPE:
    "{className}的{subjectName}指定了教室類型，但實際排定的教室（{roomName}）類型不符！",
  H11_NON_TEACHING_PERIOD: "{className}的{subjectName}被排入非教學時段（{timeSlotLabel}）！",
  H12_ACTIVE_STATUS: "{className}的{subjectName}課程涉及已停用的項目：{inactiveEntities}！",
  NO_CANDIDATE_TEACHER: "找不到可教授{subjectName}的教師，{className}的這堂課無法排定！",
  H6_REQUIRED_TEACHER_NOT_QUALIFIED:
    "指定教師{teacherName}不具備教授{subjectName}的資格，{className}的這堂課無法排定！",
  STATIC_TEACHER_WORKLOAD_EXCEEDED: "{teacherName}被指定的課程總節數超過每週授課節數上限！",
  STATIC_TEACHER_AVAILABILITY_INSUFFICIENT:
    "{teacherName}被指定的課程數超過其可用時段數量，無法排入課表！",
  STATIC_INACTIVE_ENTITY_CONFLICT: "{requirementLabel}涉及已停用的項目：{inactiveEntities}！",
  INCOMPLETE_SCHEDULE_ROW: "{className}的{subjectName}有一筆排課資料缺少{missingFields}！",
  FIXED_TIME_SLOT_MISMATCH:
    "{className}的{subjectName}被固定在{fixedTimeSlotLabel}，但目前排在{timeSlotLabel}！",
};

// Task 68: FIXED_TIME_SLOT_MISMATCH when the fixed slot can't be resolved
// (no Lesson lookup passed in, or the Lesson isn't in it) -- still a full
// sentence, never one with a blank where the fixed slot should be.
export const FIXED_TIME_SLOT_MISMATCH_UNKNOWN_SLOT_TEMPLATE =
  "{className}的{subjectName}設有固定時段，但目前排在{timeSlotLabel}，不在固定時段內！";

// Task 68: one heading per violation type for the conflict checklist
// (components/ConflictChecklist.tsx), in the order the groups are shown.
// Every type GET /schedule-versions/{id}/check can return is listed; an
// unlisted (future) type is grouped under UNKNOWN_VIOLATION_TYPE_HEADING,
// after these.
export const VIOLATION_TYPE_HEADINGS: Record<string, string> = {
  H1_TEACHER_CONFLICT: "老師衝堂",
  H2_CLASS_CONFLICT: "班級衝堂",
  H3_ROOM_CONFLICT: "教室衝堂",
  H4_TEACHER_AVAILABILITY: "排在老師不可排課的時段",
  H5_TEACHER_QUALIFICATION: "老師不具任教資格",
  H6_REQUIRED_TEACHER: "與指定教師不符",
  H7_WEEKLY_PERIODS: "每週節數不符",
  H8_TEACHER_MAX_WORKLOAD: "超過每週授課節數上限",
  H9_ROOM_TYPE: "教室類型不符",
  H11_NON_TEACHING_PERIOD: "排入非教學時段",
  H12_ACTIVE_STATUS: "涉及已停用的項目",
  INCOMPLETE_SCHEDULE_ROW: "排課資料不完整",
  FIXED_TIME_SLOT_MISMATCH: "不在固定時段",
};

export const UNKNOWN_VIOLATION_TYPE_HEADING = "其他問題";

// Task 68: a short Chinese "what to do" line per type, shown in the conflict
// checklist instead of the backend's English suggested_action (which has no
// translation and often embeds raw ids). Deliberately generic per type -- a
// type without an entry simply shows no suggestion, never English text.
export const VIOLATION_TYPE_SUGGESTIONS: Record<string, string> = {
  H1_TEACHER_CONFLICT: "把其中一堂課移到這位老師沒有課的節次，或改由其他老師授課。",
  H2_CLASS_CONFLICT: "把其中一堂課移到這個班級沒有課的節次。",
  H3_ROOM_CONFLICT: "把其中一堂課移到其他節次，或改用其他教室。",
  H4_TEACHER_AVAILABILITY:
    "把這堂課移到老師可排課的節次，或到基礎資料調整老師的不可排課時段。",
  H5_TEACHER_QUALIFICATION:
    "改由具備這個科目任教資格的老師授課，或到基礎資料為老師加上任教資格。",
  H6_REQUIRED_TEACHER: "改回需求指定的教師，或到排課需求總覽修改指定教師。",
  H7_WEEKLY_PERIODS: "補排或移除這門課的節次，讓排定堂數與需求的每週節數一致。",
  H8_TEACHER_MAX_WORKLOAD: "把這位老師的部分課改由其他老師授課，或調整老師的每週授課節數上限。",
  H9_ROOM_TYPE: "改用符合需求教室類型的教室。",
  H11_NON_TEACHING_PERIOD: "把這堂課移到教學時段。",
  H12_ACTIVE_STATUS: "改用啟用中的項目，或到基礎資料重新啟用相關項目。",
  INCOMPLETE_SCHEDULE_ROW: "為這筆排課資料補上缺少的時段或老師。",
  FIXED_TIME_SLOT_MISMATCH: "把這堂課移回固定時段，或到排課控制台修改這堂課的固定時段。",
};

// Task 39: the "reason" clause only -- no leading punctuation, no trailing
// "！", and (unlike VIOLATION_TYPE_TEMPLATES above) no restatement of
// {className}/{subjectName} where the original template's ending was
// SPECIFICALLY "..., {className}的這堂課無法排定！" (NO_CANDIDATE_TEACHER /
// H6_REQUIRED_TEACHER_NOT_QUALIFIED) or where {className}/{subjectName}
// opened the sentence right before a fact that doesn't need them repeated
// (H2/H6_REQUIRED_TEACHER/H9/H11/H12). Used by
// utils/failureDiagnostics.ts's getGroupedLessonFailureSentence() to build
// "{班級}的{科目}（共 N 堂課）：{reason}，這些課無法排定！" -- the class+subject
// and the "can't be placed" conclusion are already supplied by that
// surrounding sentence, so repeating them here would read as "二年甲班的
// 體育（共 2 堂課）：二年甲班的體育...，這些課無法排定！", doubled.
//
// Only the types that can actually appear inside a LessonFailure.reasons
// entry belong here (H7/H8/STATIC_* are always whole-batch, never
// per-Lesson -- see scheduling_engine/constraints/weekly_periods.py,
// teacher_workload.py, and static_feasibility.py's own checks, none of
// which ever attach a lesson_id). A type missing from this table falls back
// to VIOLATION_TYPE_TEMPLATES' full sentence (minus its trailing "！") --
// see getGroupedLessonFailureSentence()'s own fallback.
export const LESSON_FAILURE_REASON_TEMPLATES: Record<string, string> = {
  H1_TEACHER_CONFLICT: "{teacherName}在{timeSlotLabel}被同時排定兩堂課",
  H2_CLASS_CONFLICT: "在{timeSlotLabel}被同時排定兩堂課",
  H3_ROOM_CONFLICT: "{roomName}在{timeSlotLabel}被同時排定兩堂課",
  H4_TEACHER_AVAILABILITY: "{teacherName}在{timeSlotLabel}已標記為不可排課，但仍被排入該時段",
  H5_TEACHER_QUALIFICATION: "{teacherName}未具備教授{subjectName}的資格",
  H6_REQUIRED_TEACHER: "指定了特定教師，但實際排定的教師（{teacherName}）與指定教師不符",
  H9_ROOM_TYPE: "指定了教室類型，但實際排定的教室（{roomName}）類型不符",
  H11_NON_TEACHING_PERIOD: "被排入非教學時段（{timeSlotLabel}）",
  H12_ACTIVE_STATUS: "涉及已停用的項目：{inactiveEntities}",
  NO_CANDIDATE_TEACHER: "找不到可教授{subjectName}的教師",
  H6_REQUIRED_TEACHER_NOT_QUALIFIED: "指定教師{teacherName}不具備教授{subjectName}的資格",
};
