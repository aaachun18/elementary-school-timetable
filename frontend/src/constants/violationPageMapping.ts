// Task 37: ConstraintViolationDetail.type -> which frontend page can help a
// 教務人員 fix it, for the "請至 {頁面} 修正" line FailureDiagnostics.tsx
// renders under every violation sentence. Decided together with the user
// (see conversation record); the short version, as of Task 98 (the
// settings moved into the scheduling wizard):
//
// - Problems that live on the ClassSubjectRequirement itself (每週節數/
//   指定教師/指定教室/連堂樣式) -> the wizard's 科目需求 step.
// - Teacher-side problems (參與本學期/可用時段/節數上下限) -> the wizard's
//   教師設定 step: all of them are the semester's own settings.
//   H8_TEACHER_MAX_WORKLOAD in particular points there: it only ever
//   carries a teacher_id -- there is no single requirement to send the user
//   to.
// - Grade time slot problems (H13) -> the wizard's 年級可排節次 step.
// - Inactive-entity problems (H12_ACTIVE_STATUS/STATIC_INACTIVE_ENTITY_
//   CONFLICT) -> dynamically resolved to whichever 學校資料 tab (or, for a
//   teacher, 帳號管理) the actually-inactive entity lives on, via resolveInactiveEntities() in
//   utils/failureDiagnostics.ts (the same function the violation sentence's
//   {inactiveEntities} text is built from, so the two can never disagree).
// - H1_TEACHER_CONFLICT/H2_CLASS_CONFLICT/H3_ROOM_CONFLICT/
//   H11_NON_TEACHING_PERIOD get no link at all, by explicit user decision:
//   these 4 types are unreachable through the current API in practice (only
//   scheduling_engine/algorithms/greedy.py's explain path produces them;
//   backend/app/services/scheduler.py only ever calls schedule_backtracking),
//   and even if one did surface, /timetable has nothing to show for it (a
//   failed run writes zero Schedule rows -- see run_scheduler()'s atomicity
//   guarantee) and no page edits Lesson.fixed_time_slot_id (H11's root
//   cause) at all. Rather than point at a page that can't actually help,
//   these render a fixed line instead of a link.

import type { ConstraintViolationDetail } from "../types/scheduler";
import {
  resolveInactiveEntities,
  type InactiveEntityTab,
  type NameLookups,
} from "../utils/failureDiagnostics";

export interface ViolationPageLink {
  kind: "link";
  label: string;
  path: string;
}

export interface ViolationPageText {
  kind: "text";
  message: string;
}

export type ViolationPageTarget = ViolationPageLink | ViolationPageText;

// Shown for H1/H2/H3/H11 (see module docstring) and as the safe fallback for
// any type this table doesn't otherwise recognize -- never guess a link.
const ENGINE_INTERNAL_TEXT: ViolationPageText = {
  kind: "text",
  message: "此為排課引擎內部判斷，請聯絡系統開發者確認",
};

// Task 98: the settings are the scheduling wizard's steps now
// (pages/SchedulingWizard.tsx, ?step= opens one directly).
const REQUIREMENTS_PAGE: ViolationPageLink = {
  kind: "link",
  label: "開始排課（科目需求）",
  path: "/wizard?step=requirements",
};

const TEACHERS_PAGE: ViolationPageLink = {
  kind: "link",
  label: "開始排課（教師設定）",
  path: "/wizard?step=teachers",
};

const GRADE_SLOTS_PAGE: ViolationPageLink = {
  kind: "link",
  label: "開始排課（年級可排節次）",
  path: "/wizard?step=grades",
};

// A deactivated teacher is an 一般老師 account to 啟用 again; the rest are
// 學校資料 tabs.
const INACTIVE_ENTITY_PAGE: Record<InactiveEntityTab, ViolationPageLink> = {
  teachers: { kind: "link", label: "帳號管理", path: "/users" },
  classes: { kind: "link", label: "學校資料（班級分頁）", path: "/data?tab=classes" },
  subjects: { kind: "link", label: "學校資料（科目分頁）", path: "/data?tab=subjects" },
  rooms: { kind: "link", label: "學校資料（教室分頁）", path: "/data?tab=rooms" },
};

// Task 81: a lesson's fixed time slot is set on the schedule record's page
// (「設定固定時段」), so every fixed-slot pre-check problem points there.
const FIXED_SLOT_PAGE: ViolationPageLink = {
  kind: "link",
  label: "排課紀錄（設定固定時段）",
  path: "/records",
};

// Task 93: where a class's homeroom (導師班教室) is set.
const CLASSES_TAB_PAGE = INACTIVE_ENTITY_PAGE.classes;

const STATIC_TARGET_BY_TYPE: Record<string, ViolationPageTarget> = {
  // 需求本身的設定問題.
  STATIC_TEACHER_WORKLOAD_EXCEEDED: TEACHERS_PAGE,
  H7_WEEKLY_PERIODS: REQUIREMENTS_PAGE,
  H6_REQUIRED_TEACHER: REQUIREMENTS_PAGE,
  H9_REQUIRED_ROOM: REQUIREMENTS_PAGE,

  // 教師參與本學期/可用時段/節數上限問題(Task 98:都是每學期的設定).
  H5_TEACHER_NOT_PARTICIPATING: TEACHERS_PAGE,
  H6_REQUIRED_TEACHER_NOT_PARTICIPATING: TEACHERS_PAGE,
  NO_CANDIDATE_TEACHER: TEACHERS_PAGE,
  H4_TEACHER_AVAILABILITY: TEACHERS_PAGE,
  STATIC_TEACHER_AVAILABILITY_INSUFFICIENT: TEACHERS_PAGE,
  H8_TEACHER_MAX_WORKLOAD: TEACHERS_PAGE,

  // 年級可排節次(Task 98, H13).
  H13_CLASS_TIME_SLOT: GRADE_SLOTS_PAGE,
  STATIC_CLASS_SLOTS_INSUFFICIENT: GRADE_SLOTS_PAGE,
  STATIC_FIXED_SLOT_CLASS_CLOSED: FIXED_SLOT_PAGE,

  // 固定時段的設定問題(Task 81).
  STATIC_FIXED_SLOT_UNKNOWN: FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_NON_TEACHING: FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE: FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_CLASS_CLASH: FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_TEACHER_CLASH: FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_ROOM_CLASH: FIXED_SLOT_PAGE,

  // 連堂組合的設定問題(Task 90):樣式本身 -> 科目需求(連堂樣式);
  // 固定時段 -> 排課紀錄;教師不可排課時段 -> 教師設定.
  STATIC_BLOCK_TOO_LONG: REQUIREMENTS_PAGE,
  STATIC_BLOCK_TOO_MANY_DAYS: REQUIREMENTS_PAGE,
  STATIC_BLOCK_NOT_ENOUGH_DAYS: REQUIREMENTS_PAGE,
  BLOCK_NO_WINDOW: REQUIREMENTS_PAGE,
  STATIC_BLOCK_FIXED_CONFLICT: FIXED_SLOT_PAGE,
  STATIC_BLOCK_FIXED_SAME_DAY: FIXED_SLOT_PAGE,
  STATIC_BLOCK_TEACHER_UNAVAILABLE: TEACHERS_PAGE,
  // 已存在課表的檢查結果(Task 88);TEACHER_MIN_WORKLOAD 的最低節數在教師設定.
  BLOCK_NOT_CONSECUTIVE: REQUIREMENTS_PAGE,
  BLOCK_SAME_DAY: REQUIREMENTS_PAGE,
  TEACHER_MIN_WORKLOAD: TEACHERS_PAGE,
  // Task 98: the lesson lost its room -> give it back on the timetable;
  // the required room itself is a requirement setting.
  REQUIRED_ROOM_MISSING: REQUIREMENTS_PAGE,

  // 教室的預檢(Task 93 / 98):一間教室的課多於教學時段 -> 班級分頁(導師
  // 教室)或科目需求(指定教室);共用教室的固定課衝突 -> 排課紀錄.
  STATIC_ROOM_OVERBOOKED: CLASSES_TAB_PAGE,
  // 排課引擎內部判斷,無對應可修正頁面.
  H1_TEACHER_CONFLICT: ENGINE_INTERNAL_TEXT,
  H2_CLASS_CONFLICT: ENGINE_INTERNAL_TEXT,
  H3_ROOM_CONFLICT: ENGINE_INTERNAL_TEXT,
  H11_NON_TEACHING_PERIOD: ENGINE_INTERNAL_TEXT,
};

// H12_ACTIVE_STATUS/STATIC_INACTIVE_ENTITY_CONFLICT: not in
// STATIC_TARGET_BY_TYPE because their target page depends on WHICH entity is
// actually inactive, not just the violation's type -- resolved dynamically
// here instead. resolveInactiveEntities() can return more than one entity
// (H12 can flag several at once); the first is used as the single link
// target, in the same teacher->class->subject->room priority order the
// sentence itself lists them in.
const DYNAMIC_TARGET_TYPES = new Set(["H12_ACTIVE_STATUS", "STATIC_INACTIVE_ENTITY_CONFLICT"]);

function resolveDynamicTarget(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): ViolationPageTarget {
  const [firstInactiveEntity] = resolveInactiveEntities(violation, lookups);
  if (firstInactiveEntity === undefined) {
    return ENGINE_INTERNAL_TEXT;
  }
  return INACTIVE_ENTITY_PAGE[firstInactiveEntity.tab];
}

export function resolveViolationPageTarget(
  violation: ConstraintViolationDetail,
  lookups: NameLookups,
): ViolationPageTarget {
  if (DYNAMIC_TARGET_TYPES.has(violation.type)) {
    return resolveDynamicTarget(violation, lookups);
  }
  return STATIC_TARGET_BY_TYPE[violation.type] ?? ENGINE_INTERNAL_TEXT;
}
