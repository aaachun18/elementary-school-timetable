// Task 37: ConstraintViolationDetail.type -> which frontend page can help a
// 教務人員 fix it, for the "請至 {頁面} 修正" line FailureDiagnostics.tsx
// renders under every violation sentence. Decided together with the user
// (see conversation record); the short version:
//
// - Problems that live on the ClassSubjectRequirement itself (每週節數/
//   指定教師/指定教室類型) -> 排課需求總覽 (/requirements), which already
//   has a column for each of those fields.
// - Teacher-side problems (資格/可用時段/工作量上限) -> 基礎資料瀏覽的老師
//   分頁 (/data?tab=teachers): expanding a teacher row there shows both
//   their 任教資格 and 不可用時段 (DataBrowser.tsx's TeacherDetail), and the
//   table itself shows 最高每週節數.
//   H8_TEACHER_MAX_WORKLOAD in particular points here rather than
//   /requirements: unlike STATIC_TEACHER_WORKLOAD_EXCEEDED (whose message
//   names the specific requirement_ids at fault), H8 only ever carries a
//   teacher_id -- there is no single requirement row to send the user to.
// - Inactive-entity problems (H12_ACTIVE_STATUS/STATIC_INACTIVE_ENTITY_
//   CONFLICT) -> dynamically resolved to whichever DataBrowser tab(s) the
//   actually-inactive entity lives on, via resolveInactiveEntities() in
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

const REQUIREMENTS_PAGE: ViolationPageLink = {
  kind: "link",
  label: "排課需求總覽",
  path: "/requirements",
};

const TEACHERS_TAB_PAGE: ViolationPageLink = {
  kind: "link",
  label: "基礎資料瀏覽（老師分頁）",
  path: "/data?tab=teachers",
};

const DATA_BROWSER_TAB_LABEL: Record<InactiveEntityTab, string> = {
  teachers: "基礎資料瀏覽（老師分頁）",
  classes: "基礎資料瀏覽（班級分頁）",
  subjects: "基礎資料瀏覽（科目分頁）",
  rooms: "基礎資料瀏覽（教室分頁）",
};

// Task 81: a lesson's fixed time slot is set in the scheduler console
// (「設定固定時段」), so every fixed-slot pre-check problem points there.
const SCHEDULER_FIXED_SLOT_PAGE: ViolationPageLink = {
  kind: "link",
  label: "排課控制台（設定固定時段）",
  path: "/scheduler",
};

// Task 94: where a room's type is set.
const ROOMS_TAB_PAGE: ViolationPageLink = {
  kind: "link",
  label: DATA_BROWSER_TAB_LABEL.rooms,
  path: "/data?tab=rooms",
};

// Task 93: where a class's homeroom (導師班教室) is set.
const CLASSES_TAB_PAGE: ViolationPageLink = {
  kind: "link",
  label: DATA_BROWSER_TAB_LABEL.classes,
  path: "/data?tab=classes",
};

const STATIC_TARGET_BY_TYPE: Record<string, ViolationPageTarget> = {
  // 需求本身的設定問題.
  STATIC_TEACHER_WORKLOAD_EXCEEDED: REQUIREMENTS_PAGE,
  H7_WEEKLY_PERIODS: REQUIREMENTS_PAGE,
  H6_REQUIRED_TEACHER: REQUIREMENTS_PAGE,
  H9_ROOM_TYPE: REQUIREMENTS_PAGE,

  // 教師資格/可用時段/工作量上限問題.
  H5_TEACHER_QUALIFICATION: TEACHERS_TAB_PAGE,
  H6_REQUIRED_TEACHER_NOT_QUALIFIED: TEACHERS_TAB_PAGE,
  NO_CANDIDATE_TEACHER: TEACHERS_TAB_PAGE,
  H4_TEACHER_AVAILABILITY: TEACHERS_TAB_PAGE,
  STATIC_TEACHER_AVAILABILITY_INSUFFICIENT: TEACHERS_TAB_PAGE,
  H8_TEACHER_MAX_WORKLOAD: TEACHERS_TAB_PAGE,

  // 固定時段的設定問題(Task 81).
  STATIC_FIXED_SLOT_UNKNOWN: SCHEDULER_FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_NON_TEACHING: SCHEDULER_FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE: SCHEDULER_FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_CLASS_CLASH: SCHEDULER_FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_TEACHER_CLASH: SCHEDULER_FIXED_SLOT_PAGE,
  STATIC_FIXED_SLOT_ROOM_SHORTAGE: SCHEDULER_FIXED_SLOT_PAGE,

  // 連堂組合的設定問題(Task 90):樣式本身 -> 排課需求總覽(連堂樣式欄);
  // 固定時段 -> 排課控制台;教師不可排課時段 -> 老師分頁.
  STATIC_BLOCK_TOO_LONG: REQUIREMENTS_PAGE,
  STATIC_BLOCK_TOO_MANY_DAYS: REQUIREMENTS_PAGE,
  STATIC_BLOCK_NOT_ENOUGH_DAYS: REQUIREMENTS_PAGE,
  BLOCK_NO_WINDOW: REQUIREMENTS_PAGE,
  STATIC_BLOCK_FIXED_CONFLICT: SCHEDULER_FIXED_SLOT_PAGE,
  STATIC_BLOCK_FIXED_SAME_DAY: SCHEDULER_FIXED_SLOT_PAGE,
  STATIC_BLOCK_TEACHER_UNAVAILABLE: TEACHERS_TAB_PAGE,
  // 已存在課表的檢查結果(Task 88);TEACHER_MIN_WORKLOAD 的最低節數在老師分頁.
  BLOCK_NOT_CONSECUTIVE: REQUIREMENTS_PAGE,
  BLOCK_SAME_DAY: REQUIREMENTS_PAGE,
  TEACHER_MIN_WORKLOAD: TEACHERS_TAB_PAGE,
  // Task 94: usually no room has exactly the required type -> the rooms tab.
  ROOM_MISSING_FOR_TYPE: ROOMS_TAB_PAGE,

  // 教室的預檢(Task 93,後端 Task 92B):類型對不上 -> 排課需求總覽(指定教室類型欄,
  // 也可能是教室資料少了這個類型);導師教室超量 -> 班級分頁(導師班教室欄);
  // 共用導師教室的固定課衝突 -> 排課控制台.
  STATIC_ROOM_TYPE_NOT_FOUND: REQUIREMENTS_PAGE,
  STATIC_HOMEROOM_OVERBOOKED: CLASSES_TAB_PAGE,
  STATIC_FIXED_SLOT_HOMEROOM_CLASH: SCHEDULER_FIXED_SLOT_PAGE,

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
  return {
    kind: "link",
    label: DATA_BROWSER_TAB_LABEL[firstInactiveEntity.tab],
    path: `/data?tab=${firstInactiveEntity.tab}`,
  };
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
