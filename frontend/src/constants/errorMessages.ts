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
  "This action requires ADMIN role": "此操作需要系統管理員權限",
  // Task 98: require_manager's 403 (系統管理員 or 教學組長),
  // require_coordinator's (教學組長 only) and require_school_member's (a
  // school account -- the 系統管理員 has no scheduling data).
  "This action requires ADMIN or COORDINATOR role": "此操作需要系統管理員或教學組長權限",
  "This action requires COORDINATOR role": "此操作需要教學組長權限",
  "This action requires a school account": "此操作需要學校帳號（教學組長或一般老師）",
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

// 「此資料仍被其他資料參照，無法刪除」 (409) also carries `delete_steps`:
// what to delete first, in order (backend/app/services/delete_guidance.py).
// [] for any other error, or when the backend has no steps to offer.
export function extractDeleteSteps(error: unknown): string[] {
  if (!axios.isAxiosError<ApiErrorResponse>(error)) {
    return [];
  }
  const steps = error.response?.data?.delete_steps;
  return Array.isArray(steps) ? steps.filter((step): step is string => typeof step === "string") : [];
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
// - scheduling_engine/constraints/*.py: H1/H2/H3/H4/H5/H6/H7/H8/H9/H11/H12/H13
//   (no H10 constraint exists in this codebase)
// - scheduling_engine/algorithms/resources.py's no_candidate_teacher_violation():
//   NO_CANDIDATE_TEACHER, H6_REQUIRED_TEACHER_NOT_PARTICIPATING
// - scheduling_engine/static_feasibility.py's checks:
//   STATIC_TEACHER_WORKLOAD_EXCEEDED, STATIC_TEACHER_AVAILABILITY_INSUFFICIENT,
//   STATIC_INACTIVE_ENTITY_CONFLICT, and (Task 81) the fixed-time-slot ones,
//   STATIC_FIXED_SLOT_UNKNOWN / _NON_TEACHING / _TEACHER_UNAVAILABLE /
//   _CLASS_CLASH / _TEACHER_CLASH / _ROOM_CLASH / _CLASS_CLOSED (each names its lesson's
//   class, subject and fixed slot)
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
  H3_ROOM_CONFLICT: "{roomName}在{timeSlotLabel}排的班級超過這間教室能同時容納的數量！",
  H14_COMBINED_LESSON_SPLIT: "{className}的{subjectName}是共同排課，但和合併的班級沒有排在同一個時段！",
  STATIC_COMBINED_FIXED_CONFLICT: "{className}的{subjectName}是共同排課，但各班固定在不同的時段！",
  H4_TEACHER_AVAILABILITY:
    "{teacherName}在{timeSlotLabel}已標記為不可排課，但仍被排入該時段！",
  H5_TEACHER_NOT_PARTICIPATING: "{teacherName}沒有參與本學期排課，卻被排入{className}的{subjectName}！",
  H6_REQUIRED_TEACHER:
    "{className}的{subjectName}指定了特定教師，但實際排定的教師（{teacherName}）與指定教師不符！",
  H7_WEEKLY_PERIODS: "{requirementLabel}的每週排課節數，與需求設定的節數不符！",
  H8_TEACHER_MAX_WORKLOAD: "{teacherName}的排課總節數超過每週授課節數上限！",
  H9_REQUIRED_ROOM:
    "{className}的{subjectName}指定了上課教室，但實際排定的教室（{roomName}）不是指定的教室！",
  H13_CLASS_TIME_SLOT: "{className}的{subjectName}被排入所屬年級沒有開放的節次（{timeSlotLabel}）！",
  H11_NON_TEACHING_PERIOD: "{className}的{subjectName}被排入非教學時段（{timeSlotLabel}）！",
  H12_ACTIVE_STATUS: "{className}的{subjectName}課程涉及已停用的項目：{inactiveEntities}！",
  NO_CANDIDATE_TEACHER: "本學期沒有參與排課的教師，{className}的{subjectName}無法排定！",
  H6_REQUIRED_TEACHER_NOT_PARTICIPATING:
    "指定教師{teacherName}沒有參與本學期排課，{className}的{subjectName}無法排定！",
  STATIC_TEACHER_WORKLOAD_EXCEEDED: "{teacherName}被指定的課程總節數超過每週授課節數上限！",
  STATIC_TEACHER_AVAILABILITY_INSUFFICIENT:
    "{teacherName}被指定的課程數超過其可用時段數量，無法排入課表！",
  STATIC_INACTIVE_ENTITY_CONFLICT: "{requirementLabel}涉及已停用的項目：{inactiveEntities}！",
  STATIC_FIXED_SLOT_UNKNOWN: "{className}的{subjectName}被固定的時段不存在（{timeSlotLabel}）！",
  STATIC_FIXED_SLOT_NON_TEACHING:
    "{className}的{subjectName}被固定在{timeSlotLabel}，但這不是教學時段！",
  STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE:
    "{className}的{subjectName}被固定在{timeSlotLabel}，但{teacherName}在這個時段不可排課！",
  STATIC_FIXED_SLOT_CLASS_CLASH:
    "{className}的{subjectName}被固定在{timeSlotLabel}，但{className}在同一時段還有其他固定的課！",
  STATIC_FIXED_SLOT_TEACHER_CLASH:
    "{className}的{subjectName}被固定在{timeSlotLabel}，但只能由{teacherName}授課，而{teacherName}在同一時段還有其他固定的課！",
  STATIC_FIXED_SLOT_ROOM_CLASH:
    "{className}的{subjectName}被固定在{timeSlotLabel}，但在同一間教室（{roomName}）上課的另一班同一時段也有固定的課！",
  STATIC_FIXED_SLOT_CLASS_CLOSED:
    "{className}的{subjectName}被固定在{timeSlotLabel}，但所屬年級沒有開放這個節次！",
  INCOMPLETE_SCHEDULE_ROW: "{className}的{subjectName}有一筆排課資料缺少{missingFields}！",
  FIXED_TIME_SLOT_MISMATCH:
    "{className}的{subjectName}被固定在{fixedTimeSlotLabel}，但目前排在{timeSlotLabel}！",
  // Task 90: lesson blocks (連堂, backend Task 87/88) -- {blockLabel} is
  // 「第 N 組」 from the violation's block_no ("" without it), {weekdayLabel}
  // the weekday of its time slot. The STATIC_BLOCK_* pre-checks carry no
  // block_no, so they speak of the requirement's pattern as a whole.
  BLOCK_NOT_CONSECUTIVE: "{className}的{subjectName}{blockLabel}連堂沒有排在同一天相鄰的節次！",
  BLOCK_SAME_DAY: "{className}的{subjectName}有不同組的連堂排在同一天（{weekdayLabel}）！",
  TEACHER_MIN_WORKLOAD: "{teacherName}的排課總節數低於每週最低授課節數！",
  // Task 98: a WARNING -- a special room is required but the lesson has no room.
  REQUIRED_ROOM_MISSING:
    "{className}的{subjectName}指定了上課教室，但{timeSlotLabel}這堂課沒有教室！",
  BLOCK_NO_WINDOW: "{className}的{subjectName}的連堂找不到同一天足夠的連續教學節次！",
  STATIC_BLOCK_TOO_LONG:
    "{className}的{subjectName}的連堂樣式中，有一組的節數超過任何一天可連續上課的節數！",
  STATIC_BLOCK_TOO_MANY_DAYS: "{className}的{subjectName}的連堂組數多於一週的上課天數！",
  STATIC_BLOCK_NOT_ENOUGH_DAYS:
    "{className}的{subjectName}的各組連堂要排在不同天，但有足夠連續節次的天數不夠！",
  STATIC_BLOCK_FIXED_CONFLICT:
    "{className}的{subjectName}同一組連堂的固定時段，無法排成同一天依序相鄰的節次！",
  STATIC_BLOCK_FIXED_SAME_DAY: "{className}的{subjectName}有不同組的連堂被固定在同一天！",
  STATIC_BLOCK_TEACHER_UNAVAILABLE:
    "{className}的{subjectName}的連堂排不進去：{teacherName}在每一段可用的連續節次中都有不可排課的時段！",
  // Task 93 / 98: the room and grade-slot pre-checks.
  STATIC_ROOM_OVERBOOKED: "教室{roomName}要上的課多於一週的教學時段，在這間教室上課的班級排不下！",
  STATIC_CLASS_SLOTS_INSUFFICIENT: "{className}每週要上的課多於所屬年級開放的可排節次！",
};

// Task 90: STATIC_BLOCK_TEACHER_UNAVAILABLE without a teacher_id -- every
// teacher who could teach the block is unavailable somewhere in every
// window.
export const BLOCK_ALL_TEACHERS_UNAVAILABLE_TEMPLATE =
  "{className}的{subjectName}的連堂排不進去：所有可教授{subjectName}的教師在每一段可用的連續節次中都有不可排課的時段！";

// Task 68: FIXED_TIME_SLOT_MISMATCH when the fixed slot can't be resolved
// (no Lesson lookup passed in, or the Lesson isn't in it) -- still a full
// sentence, never one with a blank where the fixed slot should be.
export const FIXED_TIME_SLOT_MISMATCH_UNKNOWN_SLOT_TEMPLATE =
  "{className}的{subjectName}設有固定時段，但目前排在{timeSlotLabel}，不在固定時段內！";

// Task 81: STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE without a teacher_id --
// no required teacher, and EVERY teacher taking part is unavailable then.
export const FIXED_SLOT_ALL_TEACHERS_UNAVAILABLE_TEMPLATE =
  "{className}的{subjectName}被固定在{timeSlotLabel}，但所有可教授{subjectName}的教師在這個時段都不可排課！";

// Task 68: one heading per violation type for the conflict checklist
// (components/ConflictChecklist.tsx), in the order the groups are shown.
// Every type GET /schedule-versions/{id}/check can return is listed; an
// unlisted (future) type is grouped under UNKNOWN_VIOLATION_TYPE_HEADING,
// after these.
export const VIOLATION_TYPE_HEADINGS: Record<string, string> = {
  H1_TEACHER_CONFLICT: "老師衝堂",
  H2_CLASS_CONFLICT: "班級衝堂",
  H3_ROOM_CONFLICT: "教室衝堂",
  H14_COMBINED_LESSON_SPLIT: "共同排課被拆開",
  STATIC_COMBINED_FIXED_CONFLICT: "共同排課的固定時段不一致",
  H4_TEACHER_AVAILABILITY: "排在老師不可排課的時段",
  H5_TEACHER_NOT_PARTICIPATING: "老師沒有參與本學期排課",
  H6_REQUIRED_TEACHER: "與指定教師不符",
  H7_WEEKLY_PERIODS: "每週節數不符",
  H8_TEACHER_MAX_WORKLOAD: "超過每週授課節數上限",
  H9_REQUIRED_ROOM: "不在指定的教室",
  H13_CLASS_TIME_SLOT: "排入年級沒有開放的節次",
  H11_NON_TEACHING_PERIOD: "排入非教學時段",
  H12_ACTIVE_STATUS: "涉及已停用的項目",
  INCOMPLETE_SCHEDULE_ROW: "排課資料不完整",
  FIXED_TIME_SLOT_MISMATCH: "不在固定時段",
  BLOCK_NOT_CONSECUTIVE: "連堂被拆開或不相鄰",
  BLOCK_SAME_DAY: "同一門課的不同組排在同一天",
  // Task 90: the only WARNING type -- listed last.
  TEACHER_MIN_WORKLOAD: "教師授課節數低於最低要求（警告）",
  // Task 94: the other WARNING type.
  REQUIRED_ROOM_MISSING: "指定了教室卻沒有教室（警告）",
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
  H14_COMBINED_LESSON_SPLIT: "把合併的各班這一節移回同一個時段。",
  STATIC_COMBINED_FIXED_CONFLICT: "把合併的各班這一節固定在同一個時段，或取消固定時段。",
  H4_TEACHER_AVAILABILITY:
    "把這堂課移到老師可排課的節次，或到開始排課的教師設定調整不可排課時段。",
  H5_TEACHER_NOT_PARTICIPATING:
    "改由參與本學期排課的老師授課，或到開始排課的教師設定把這位老師加入本學期。",
  H6_REQUIRED_TEACHER: "改回需求指定的教師，或到開始排課的科目需求修改指定教師。",
  H7_WEEKLY_PERIODS: "補排或移除這門課的節次，讓排定堂數與需求的每週節數一致。",
  H8_TEACHER_MAX_WORKLOAD: "把這位老師的部分課改由其他老師授課，或調整老師的每週授課節數上限。",
  H9_REQUIRED_ROOM: "把這堂課改回需求指定的教室。",
  H13_CLASS_TIME_SLOT: "把這堂課移到所屬年級開放的節次，或到開始排課的年級可排節次開放這個節次。",
  H11_NON_TEACHING_PERIOD: "把這堂課移到教學時段。",
  H12_ACTIVE_STATUS: "改用啟用中的項目，或到學校資料、帳號管理重新啟用相關項目。",
  INCOMPLETE_SCHEDULE_ROW: "為這筆排課資料補上缺少的時段或老師。",
  FIXED_TIME_SLOT_MISMATCH: "把這堂課移回固定時段，或到排課紀錄修改這堂課的固定時段。",
  BLOCK_NOT_CONSECUTIVE: "把這組連堂整組移到同一天相鄰的教學節次（拖曳其中一節即可整組移動）。",
  BLOCK_SAME_DAY: "把其中一組移到另一天。",
  TEACHER_MIN_WORKLOAD: "可為這位老師多安排課程，或到開始排課的教師設定調整最低每週節數；這是提醒，不影響課表是否合法。",
  REQUIRED_ROOM_MISSING: "在編輯模式為這堂課選回指定的教室；這是提醒，不影響課表是否合法。",
};

// Task 90 (backend Task 89): why a lesson block can't go where it was
// dropped -- move-candidates' unavailable_reason / unsupported_swaps[].reason
// and the 409 `reason` of move-lesson / swap-lessons. Short, for a cell's
// tooltip and the message shown instead of sending the request.
export const BLOCK_REFUSAL_MESSAGES: Record<string, string> = {
  BLOCK_OUT_OF_RANGE: "整組放不下：會超出當天節次或跨過午休",
  BLOCK_TARGET_OCCUPIED: "整組會壓到本班其他課，請改拖到要對調的那堂課上",
  BLOCK_SWAP_UNSUPPORTED: "連堂只能與節數相同、已全部排課的另一組對調",
};

// The BLOCK_* reason of a 409 from move-lesson / swap-lessons, or null for
// any other error.
export function getBlockRefusalReason(error: unknown): string | null {
  if (!axios.isAxiosError(error) || error.response?.status !== 409) {
    return null;
  }
  const data: unknown = error.response.data;
  if (typeof data !== "object" || data === null || !("reason" in data)) {
    return null;
  }
  const reason = (data as { reason: unknown }).reason;
  return typeof reason === "string" && reason in BLOCK_REFUSAL_MESSAGES ? reason : null;
}

// Task 39: the "reason" clause only -- no leading punctuation, no trailing
// "！", and (unlike VIOLATION_TYPE_TEMPLATES above) no restatement of
// {className}/{subjectName} where the original template's ending was
// SPECIFICALLY "..., {className}的這堂課無法排定！" (NO_CANDIDATE_TEACHER /
// H6_REQUIRED_TEACHER_NOT_PARTICIPATING) or where {className}/{subjectName}
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
  H3_ROOM_CONFLICT: "{roomName}在{timeSlotLabel}排的班級超過能同時容納的數量",
  H4_TEACHER_AVAILABILITY: "{teacherName}在{timeSlotLabel}已標記為不可排課，但仍被排入該時段",
  H5_TEACHER_NOT_PARTICIPATING: "{teacherName}沒有參與本學期排課",
  H6_REQUIRED_TEACHER: "指定了特定教師，但實際排定的教師（{teacherName}）與指定教師不符",
  H9_REQUIRED_ROOM: "指定了上課教室，但實際排定的教室（{roomName}）不是指定的教室",
  H13_CLASS_TIME_SLOT: "被排入所屬年級沒有開放的節次（{timeSlotLabel}）",
  H11_NON_TEACHING_PERIOD: "被排入非教學時段（{timeSlotLabel}）",
  H12_ACTIVE_STATUS: "涉及已停用的項目：{inactiveEntities}",
  NO_CANDIDATE_TEACHER: "本學期沒有參與排課的教師",
  H6_REQUIRED_TEACHER_NOT_PARTICIPATING: "指定教師{teacherName}沒有參與本學期排課",
  BLOCK_NO_WINDOW: "連堂找不到同一天足夠的連續教學節次",
};
