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
const KNOWN_ERROR_MESSAGES: Record<string, string> = {
  // POST /api/v1/auth/login -- backend/app/routers/auth.py's only 401 case.
  "Incorrect username or password": "帳號或密碼錯誤",
};

// Falls back to the original (untranslated) message when it isn't in the
// table above -- never swallowed, never replaced with a generic string.
export function translateErrorMessage(message: string): string {
  return KNOWN_ERROR_MESSAGES[message] ?? message;
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
  SEARCH_LIMIT_EXCEEDED: "排課嘗試次數已達上限,但不代表無解,可調整條件後重新嘗試",
  TIMEOUT: "排課時間已達上限,但不代表無解,可調整條件後重新嘗試",
  REQUIREMENT_PERIODS_MISMATCH: "每堂課都已排入時段,但部分需求的每週節數與實際排定堂數不符",
  STATIC_CHECK_FAILED: "排課前的可行性檢查未通過(尚未開始搜尋課表)",
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
//
// Any type not in this table (e.g. a future constraint) falls back to the
// violation's own English `message` -- see getViolationSentence().
//
// Task 37: every template is a plain statement ending in "!", with no
// embedded suggested-action clause -- FailureDiagnostics.tsx now renders a
// second, separate line ("請至 {頁面} 修正", via
// constants/violationPageMapping.ts) instead of the removed suggested_action
// text, so a template repeating "請...調整/改指派" here would just duplicate
// that second line in different words.
export const VIOLATION_TYPE_TEMPLATES: Record<string, string> = {
  H1_TEACHER_CONFLICT: "{teacherName}在{timeSlotLabel}被同時排定兩堂課!",
  H2_CLASS_CONFLICT: "{className}在{timeSlotLabel}被同時排定兩堂課!",
  H3_ROOM_CONFLICT: "{roomName}在{timeSlotLabel}被同時排定兩堂課!",
  H4_TEACHER_AVAILABILITY:
    "{teacherName}在{timeSlotLabel}已標記為不可排課,但仍被排入該時段!",
  H5_TEACHER_QUALIFICATION: "{teacherName}未具備教授{subjectName}的資格!",
  H6_REQUIRED_TEACHER:
    "{className}的{subjectName}指定了特定教師,但實際排定的教師({teacherName})與指定教師不符!",
  H7_WEEKLY_PERIODS: "{requirementLabel}的每週排課節數,與需求設定的節數不符!",
  H8_TEACHER_MAX_WORKLOAD: "{teacherName}的排課總節數超過每週授課節數上限!",
  H9_ROOM_TYPE:
    "{className}的{subjectName}指定了教室類型,但實際排定的教室({roomName})類型不符!",
  H11_NON_TEACHING_PERIOD: "{className}的{subjectName}被排入非教學時段({timeSlotLabel})!",
  H12_ACTIVE_STATUS: "{className}的{subjectName}課程涉及已停用的項目:{inactiveEntities}!",
  NO_CANDIDATE_TEACHER: "找不到可教授{subjectName}的教師,{className}的這堂課無法排定!",
  H6_REQUIRED_TEACHER_NOT_QUALIFIED:
    "指定教師{teacherName}不具備教授{subjectName}的資格,{className}的這堂課無法排定!",
  STATIC_TEACHER_WORKLOAD_EXCEEDED: "{teacherName}被指定的課程總節數超過每週授課節數上限!",
  STATIC_TEACHER_AVAILABILITY_INSUFFICIENT:
    "{teacherName}被指定的課程數超過其可用時段數量,無法排入課表!",
  STATIC_INACTIVE_ENTITY_CONFLICT: "{requirementLabel}涉及已停用的項目:{inactiveEntities}!",
};

// Task 39: the "reason" clause only -- no leading punctuation, no trailing
// "!", and (unlike VIOLATION_TYPE_TEMPLATES above) no restatement of
// {className}/{subjectName} where the original template's ending was
// SPECIFICALLY "..., {className}的這堂課無法排定!" (NO_CANDIDATE_TEACHER /
// H6_REQUIRED_TEACHER_NOT_QUALIFIED) or where {className}/{subjectName}
// opened the sentence right before a fact that doesn't need them repeated
// (H2/H6_REQUIRED_TEACHER/H9/H11/H12). Used by
// utils/failureDiagnostics.ts's getGroupedLessonFailureSentence() to build
// "{班級}的{科目}(共 N 堂課):{reason},這些課無法排定!" -- the class+subject
// and the "can't be placed" conclusion are already supplied by that
// surrounding sentence, so repeating them here would read as "二年甲班的
// 體育(共 2 堂課):二年甲班的體育...,這些課無法排定!", doubled.
//
// Only the types that can actually appear inside a LessonFailure.reasons
// entry belong here (H7/H8/STATIC_* are always whole-batch, never
// per-Lesson -- see scheduling_engine/constraints/weekly_periods.py,
// teacher_workload.py, and static_feasibility.py's own checks, none of
// which ever attach a lesson_id). A type missing from this table falls back
// to VIOLATION_TYPE_TEMPLATES' full sentence (minus its trailing "!") --
// see getGroupedLessonFailureSentence()'s own fallback.
export const LESSON_FAILURE_REASON_TEMPLATES: Record<string, string> = {
  H1_TEACHER_CONFLICT: "{teacherName}在{timeSlotLabel}被同時排定兩堂課",
  H2_CLASS_CONFLICT: "在{timeSlotLabel}被同時排定兩堂課",
  H3_ROOM_CONFLICT: "{roomName}在{timeSlotLabel}被同時排定兩堂課",
  H4_TEACHER_AVAILABILITY: "{teacherName}在{timeSlotLabel}已標記為不可排課,但仍被排入該時段",
  H5_TEACHER_QUALIFICATION: "{teacherName}未具備教授{subjectName}的資格",
  H6_REQUIRED_TEACHER: "指定了特定教師,但實際排定的教師({teacherName})與指定教師不符",
  H9_ROOM_TYPE: "指定了教室類型,但實際排定的教室({roomName})類型不符",
  H11_NON_TEACHING_PERIOD: "被排入非教學時段({timeSlotLabel})",
  H12_ACTIVE_STATUS: "涉及已停用的項目:{inactiveEntities}",
  NO_CANDIDATE_TEACHER: "找不到可教授{subjectName}的教師",
  H6_REQUIRED_TEACHER_NOT_QUALIFIED: "指定教師{teacherName}不具備教授{subjectName}的資格",
};
