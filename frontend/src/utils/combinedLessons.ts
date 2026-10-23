// 共同排課 (combined lessons): the wizard step's rules as the backend
// enforces them (app/services/combined_lesson.py), and how a timetable shows
// a 合併節. Pure functions, no React, no requests.

import { parseLessonPattern } from "./lessonPattern";
import type { CombinedLesson } from "../types/combinedLesson";

// --- the dialog ---

export interface MergeableRequirement {
  id: number;
  class_id: number;
  weekly_periods: number;
  lesson_pattern?: string | null;
}

// Whether `candidate` may be merged with `host`: another class, the same
// weekly periods and lesson pattern, and not in another combined lesson.
export function canMergeWith(
  host: MergeableRequirement,
  candidate: MergeableRequirement,
  combinedRequirementIds: ReadonlySet<number>,
): boolean {
  return (
    candidate.id !== host.id &&
    candidate.class_id !== host.class_id &&
    candidate.weekly_periods === host.weekly_periods &&
    (candidate.lesson_pattern ?? null) === (host.lesson_pattern ?? null) &&
    !combinedRequirementIds.has(candidate.id)
  );
}

export interface BlockChoice {
  blockNo: number;
  size: number;
}

// The blocks a patterned requirement can merge (whole blocks only), or
// null without a pattern (then any count 1 .. weekly periods).
export function blockChoices(pattern: string | null | undefined): BlockChoice[] | null {
  if (pattern === null || pattern === undefined || pattern === "") {
    return null;
  }
  const blocks = parseLessonPattern(pattern);
  if (blocks === null) {
    return null;
  }
  return blocks.map((size, index) => ({ blockNo: index + 1, size }));
}

// 「第 1 組（2 節連堂）」
export function blockChoiceLabel(choice: BlockChoice): string {
  return choice.size === 1
    ? `第 ${choice.blockNo} 組（1 節）`
    : `第 ${choice.blockNo} 組（${choice.size} 節連堂）`;
}

// --- the timetable ---

// lesson_id -> the other members' lessons that share its time slot.
export function partnerLessonsOf(combinedLessons: readonly CombinedLesson[]): Map<number, number[]> {
  const partners = new Map<number, number[]>();
  for (const combined of combinedLessons) {
    for (const instance of combined.instances) {
      const size = Math.min(...instance.member_lesson_ids.map((ids) => ids.length));
      for (let index = 0; index < size; index += 1) {
        const sameSlot = instance.member_lesson_ids.map((ids) => ids[index]);
        for (const lessonId of sameSlot) {
          partners.set(
            lessonId,
            sameSlot.filter((other) => other !== lessonId),
          );
        }
      }
    }
  }
  return partners;
}

// lesson_id -> its combined lesson (for the room it is held in).
export function combinedLessonOf(combinedLessons: readonly CombinedLesson[]): Map<number, CombinedLesson> {
  const byLesson = new Map<number, CombinedLesson>();
  for (const combined of combinedLessons) {
    for (const instance of combined.instances) {
      for (const lessonIds of instance.member_lesson_ids) {
        for (const lessonId of lessonIds) {
          byLesson.set(lessonId, combined);
        }
      }
    }
  }
  return byLesson;
}

export interface TeacherOfRow {
  lessonId: number;
  teacherId: number | null;
  teacherName: string | null;
}

// A combined lesson's teachers as one line: every member's teacher once,
// the row's own class's teacher marked with *, e.g. 「王老師*、李老師」.
// A lesson of no combined lesson: just its own teacher.
export function combinedTeacherText(
  row: TeacherOfRow,
  partners: readonly TeacherOfRow[],
): string | null {
  if (partners.length === 0) {
    return row.teacherName;
  }
  const names: string[] = [];
  const seen = new Set<number | null>();
  for (const item of [row, ...partners]) {
    if (item.teacherName === null || seen.has(item.teacherId)) {
      continue;
    }
    seen.add(item.teacherId);
    names.push(item.teacherId === row.teacherId ? `${item.teacherName}*` : item.teacherName);
  }
  return names.length === 0 ? null : names.join("、");
}

// What combinedForDisplay() reads and changes of a timetable row.
export interface DisplayRow {
  scheduleId: number;
  lessonId: number;
  classId: number;
  className: string;
  teacherId: number | null;
  teacherName: string | null;
  roomId: number | null;
  specialRoomName: string | null;
}

export type DisplayViewMode = "class" | "teacher" | "room";

// The rows as the timetable shows them, 共同排課 taken into account:
// - class view: every row stays; its teacher line lists all the
//   合併節's teachers (the class's own marked *), and a 合併節 held in
//   another member class's own room says so (「＠一年甲班原班教室」);
// - teacher / room view: a 合併節 is one lesson -- one row per cell
//   (per teacher; in a class's own room, the row of that class), whose
//   class line names every class of it.
// Rows of no combined lesson are returned unchanged.
export function combinedForDisplay<T extends DisplayRow>(
  rows: readonly T[],
  combinedLessons: readonly CombinedLesson[],
  viewMode: DisplayViewMode,
): T[] {
  if (combinedLessons.length === 0) {
    return [...rows];
  }
  const partners = partnerLessonsOf(combinedLessons);
  const combinedOf = combinedLessonOf(combinedLessons);
  const rowOfLesson = new Map(rows.map((row) => [row.lessonId, row]));
  const partnerRows = (row: T): T[] =>
    (partners.get(row.lessonId) ?? [])
      .map((lessonId) => rowOfLesson.get(lessonId))
      .filter((item): item is T => item !== undefined);

  if (viewMode === "class") {
    return rows.map((row) => {
      const others = partnerRows(row);
      const combined = combinedOf.get(row.lessonId);
      if (others.length === 0 || combined === undefined) {
        return row;
      }
      const homeroom =
        combined.room_id === null && combined.homeroom_class_id !== row.classId
          ? [row, ...others].find((item) => item.classId === combined.homeroom_class_id)
          : undefined;
      return {
        ...row,
        teacherName: combinedTeacherText(row, others),
        specialRoomName: homeroom === undefined ? row.specialRoomName : `${homeroom.className}原班教室`,
      };
    });
  }

  const result: T[] = [];
  for (const row of rows) {
    const others = partnerRows(row);
    const combined = combinedOf.get(row.lessonId);
    if (others.length === 0 || combined === undefined) {
      result.push(row);
      continue;
    }
    const all = [row, ...others];
    const sameCell =
      viewMode === "teacher"
        ? all.filter((item) => item.teacherId === row.teacherId)
        : combined.room_id === null
          ? all.filter((item) => item.classId === combined.homeroom_class_id)
          : all;
    const representative = [...sameCell].sort((a, b) => a.scheduleId - b.scheduleId)[0];
    if (representative === undefined || representative.scheduleId !== row.scheduleId) {
      continue;
    }
    const classNames = [...all].sort((a, b) => a.classId - b.classId).map((item) => item.className);
    result.push({ ...row, className: classNames.join("、") });
  }
  return result;
}
