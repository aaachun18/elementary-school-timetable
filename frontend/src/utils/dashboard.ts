// Task 97: the home page dashboard (decision 33) -- turning the existing
// list / check / unscheduled-lessons responses into card data. Pure
// functions, no React, no API (dashboard.test.ts). Every function copes
// with empty input: no semester, no record, nothing at all.

import { violationIdentityKey } from "./violationMerge";
import type { Class } from "../types/class";
import type { Room } from "../types/room";
import type { ConstraintViolationDetail } from "../types/scheduler";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";
import type { Subject } from "../types/subject";
import type { Teacher } from "../types/teacher";
import { hasTimetable } from "./scheduleVersionFormat";
import type { BadgeTone } from "./badgeTone";

// --- The current semester and its 排課紀錄 ---

// The current semester -- the one whose timetable is in use: the latest
// ACTIVE semester (by academic year, then number) that has a published
// record; else the latest active one; else the latest one at all; with no
// semester, null. (The data model has no single "current" flag, and the
// next semester is often active and being prepared while this one runs.)
export function pickCurrentSemester(
  semesters: readonly Semester[],
  academicYearById: ReadonlyMap<number, number>,
  versions: readonly ScheduleVersion[] = [],
): Semester | null {
  const yearOf = (semester: Semester): number => academicYearById.get(semester.academic_year_id) ?? 0;
  const latestFirst = [...semesters].sort(
    (a, b) => yearOf(b) - yearOf(a) || b.number - a.number || b.id - a.id,
  );
  const published = new Set(
    versions.filter((version) => version.is_published).map((version) => version.semester_id),
  );
  return (
    latestFirst.find((semester) => semester.is_active && published.has(semester.id)) ??
    latestFirst.find((semester) => semester.is_active) ??
    latestFirst[0] ??
    null
  );
}

// The timetable being worked on: the newest (highest 編號) unpublished
// record of any semester that has a timetable (the next semester's is
// usually prepared while the current one is in use), or null.
export function pickLatestUnpublished(versions: readonly ScheduleVersion[]): ScheduleVersion | null {
  return versions
    .filter((version) => !version.is_published && hasTimetable(version.status))
    .reduce<ScheduleVersion | null>(
      (latest, version) =>
        latest === null || (version.version_number ?? 0) > (latest.version_number ?? 0) ? version : latest,
      null,
    );
}

export interface SemesterVersions {
  published: ScheduleVersion | null;
  // Every other record of the semester.
  otherCount: number;
}

export function summarizeVersions(versions: readonly ScheduleVersion[], semesterId: number | null): SemesterVersions {
  const mine = semesterId === null ? [] : versions.filter((version) => version.semester_id === semesterId);
  return {
    published: mine.find((version) => version.is_published) ?? null,
    otherCount: mine.filter((version) => !version.is_published).length,
  };
}

// 「2026/10/19 14:03」 in local time; 「—」 for anything unreadable, never
// "Invalid Date" / NaN. The backend's timestamps carry no zone (columns
// without time zone, filled by the database's now(), which runs in UTC),
// so a zone-less value is read as UTC.
export function formatDateTime(iso: string | null | undefined): string {
  if (iso === null || iso === undefined || iso === "") {
    return "—";
  }
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const date = new Date(hasZone ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  const pad = (value: number): string => String(value).padStart(2, "0");
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// --- The latest unpublished timetable's health ---

export interface DraftHealth {
  // Distinct problems, as the checklist counts them: one problem reported
  // once per lesson involved (e.g. a teacher's double booking) is one.
  errorCount: number;
  warningCount: number;
  unscheduledCount: number;
  isHealthy: boolean;
}

function distinctCount(violations: readonly ConstraintViolationDetail[]): number {
  return new Set(violations.map(violationIdentityKey)).size;
}

export function summarizeDraftHealth(
  violations: readonly ConstraintViolationDetail[],
  unscheduledCount: number,
): DraftHealth {
  const warnings = violations.filter((violation) => violation.severity === "WARNING");
  const errors = violations.filter((violation) => violation.severity !== "WARNING");
  const errorCount = distinctCount(errors);
  const warningCount = distinctCount(warnings);
  return {
    errorCount,
    warningCount,
    unscheduledCount,
    isHealthy: errorCount === 0 && warningCount === 0 && unscheduledCount === 0,
  };
}

// Task 99: the badge right of the card's title -- errors first, then
// warnings, else 可發布.
export interface HealthBadge {
  tone: BadgeTone;
  label: string;
}

export function draftHealthBadge(health: Pick<DraftHealth, "errorCount" | "warningCount">): HealthBadge {
  if (health.errorCount > 0) {
    return { tone: "danger", label: `${health.errorCount} 個錯誤` };
  }
  if (health.warningCount > 0) {
    return { tone: "warning", label: `${health.warningCount} 個警告` };
  }
  return { tone: "success", label: "可發布" };
}

// The card's one button: fix the errors first, else go and publish.
export function draftHealthAction(health: Pick<DraftHealth, "errorCount">): string {
  return health.errorCount > 0 ? "前往修正" : "檢視並發布";
}

// A count's color: gray when 0, its own color only when there is something.
export type StatTone = "zero" | "problem" | "warning";

export function statTone(count: number, nonZeroTone: Exclude<StatTone, "zero">): StatTone {
  return count === 0 ? "zero" : nonZeroTone;
}

// --- Data health ---

export interface DataIssue {
  message: string;
  // Where to fix it (a 學校資料 tab, or 帳號管理 for teachers).
  path: string;
}

export interface DataHealth {
  teacherCount: number;
  classCount: number;
  subjectCount: number;
  roomCount: number;
  issues: DataIssue[];
}

// Counts are of active records (停用 classes too are left out). Issues:
// nothing of a kind yet.
export function summarizeDataHealth(data: {
  teachers: readonly Teacher[];
  classes: readonly Class[];
  subjects: readonly Subject[];
  rooms: readonly Room[];
}): DataHealth {
  const active = <T extends { is_active: boolean }>(items: readonly T[]): T[] => items.filter((item) => item.is_active);
  const teachers = active(data.teachers);
  const classes = active(data.classes);
  const subjects = active(data.subjects);
  const rooms = active(data.rooms);
  const issues: DataIssue[] = [];
  // Task 98: teachers are 一般老師 accounts (帳號管理); the rest are
  // 學校資料 tabs.
  const none: [number, string, string][] = [
    [teachers.length, "老師", "/users"],
    [classes.length, "班級", "/data?tab=classes"],
    [subjects.length, "科目", "/data?tab=subjects"],
    [rooms.length, "教室", "/data?tab=rooms"],
  ];
  for (const [count, label, path] of none) {
    if (count === 0) {
      issues.push({ message: `還沒有任何啟用中的${label}`, path });
    }
  }
  return {
    teacherCount: teachers.length,
    classCount: classes.length,
    subjectCount: subjects.length,
    roomCount: rooms.length,
    issues,
  };
}
