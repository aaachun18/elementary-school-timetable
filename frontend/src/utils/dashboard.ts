// Task 97: the home page dashboard (decision 33) -- turning the existing
// list / check / unscheduled-lessons responses into card data. Pure
// functions, no React, no API (dashboard.test.ts). Every function copes
// with empty input: no semester, no version, nothing at all.

import { violationIdentityKey } from "./violationMerge";
import type { Class } from "../types/class";
import type { Room } from "../types/room";
import type { ConstraintViolationDetail } from "../types/scheduler";
import type { ScheduleVersion } from "../types/scheduleVersion";
import type { Semester } from "../types/semester";
import type { Subject } from "../types/subject";
import type { Teacher } from "../types/teacher";

// --- The current semester and its versions ---

// The current semester -- the one whose timetable is in use: the latest
// ACTIVE semester (by academic year, then number) that has a PUBLISHED
// version; else the latest active one; else the latest one at all; with no
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
    versions.filter((version) => version.status === "PUBLISHED").map((version) => version.semester_id),
  );
  return (
    latestFirst.find((semester) => semester.is_active && published.has(semester.id)) ??
    latestFirst.find((semester) => semester.is_active) ??
    latestFirst[0] ??
    null
  );
}

// The draft being worked on: the most recently created DRAFT of any
// semester (the next semester's timetable is usually prepared while the
// current one is in use), or null.
export function pickLatestDraft(versions: readonly ScheduleVersion[]): ScheduleVersion | null {
  return versions
    .filter((version) => version.status === "DRAFT")
    .reduce<ScheduleVersion | null>((latest, version) => (latest === null || version.id > latest.id ? version : latest), null);
}

export interface SemesterVersions {
  published: ScheduleVersion | null;
  draftCount: number;
}

export function summarizeVersions(versions: readonly ScheduleVersion[], semesterId: number | null): SemesterVersions {
  const mine = semesterId === null ? [] : versions.filter((version) => version.semester_id === semesterId);
  return {
    published: mine.find((version) => version.status === "PUBLISHED") ?? null,
    draftCount: mine.filter((version) => version.status === "DRAFT").length,
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

// --- The latest draft's health ---

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

// --- Data health ---

export interface DataIssue {
  message: string;
  // Where to fix it (a 基礎資料 tab).
  path: string;
}

export interface DataHealth {
  teacherCount: number;
  classCount: number;
  subjectCount: number;
  roomCount: number;
  issues: DataIssue[];
}

// Counts are of active records. Issues: nothing of a kind yet, and active
// classes without a homeroom (原班上課 then gets no room, decision 29).
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
  const none: [number, string, string][] = [
    [teachers.length, "老師", "teachers"],
    [classes.length, "班級", "classes"],
    [subjects.length, "科目", "subjects"],
    [rooms.length, "教室", "rooms"],
  ];
  for (const [count, label, tab] of none) {
    if (count === 0) {
      issues.push({ message: `還沒有任何啟用中的${label}`, path: `/data?tab=${tab}` });
    }
  }
  const withoutHomeroom = classes.filter((item) => item.homeroom_room_id === null);
  if (withoutHomeroom.length > 0) {
    const names = withoutHomeroom.slice(0, 3).map((item) => item.name).join("、");
    const more = withoutHomeroom.length > 3 ? ` 等 ${withoutHomeroom.length} 班` : "";
    issues.push({
      message: `${withoutHomeroom.length} 個班級沒有設定導師班教室（${names}${more}），原班上課的課會沒有教室`,
      path: "/data?tab=classes",
    });
  }
  return {
    teacherCount: teachers.length,
    classCount: classes.length,
    subjectCount: subjects.length,
    roomCount: rooms.length,
    issues,
  };
}
