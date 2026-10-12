import { list as listLessons } from "../api/lessons";
import { list as listRequirements } from "../api/classSubjectRequirements";
import { list as listClasses } from "../api/classes";
import { list as listSubjects } from "../api/subjects";
import { list as listTimeSlots } from "../api/timeSlots";
import { useResource } from "./useResource";
import type { TimeSlot } from "../types/timeSlot";

// Same "fetch everything, join client-side" approach as
// useTimetableData.ts -- none of these list endpoints support a
// semester_id/class_subject_requirement_id filter, so a generously large
// limit is passed explicitly (see that file's FETCH_LIMIT comment for why
// the default of 100 isn't safe here).
const FETCH_LIMIT = 1000;

// One row per generated Lesson -- SchedulerConsole's "設定固定時段" section
// renders one <select> per row. fixedTimeSlotId mirrors
// Lesson.fixed_time_slot_id as of the last fetch/successful save; the
// console keeps its own copy of this (seeded from here, then updated
// optimistically on each PATCH) rather than re-reading it from here after
// every change.
export interface FixableLessonRow {
  lessonId: number;
  sequenceNumber: number;
  fixedTimeSlotId: number | null;
}

// One ClassSubjectRequirement's Lessons, grouped together -- e.g. "二年甲
// 班的地球公民" with its 2 weekly periods underneath. Only requirements
// that already have at least one generated Lesson are included (see
// buildFixedTimeSlotData below), since there is nothing to set a fixed
// time slot on otherwise.
export interface FixedTimeSlotGroup {
  requirementId: number;
  label: string;
  lessons: FixableLessonRow[];
}

export interface FixedTimeSlotData {
  groups: FixedTimeSlotGroup[];
  // is_teaching_period === true TimeSlots only, sorted by weekday then
  // period -- these are the only valid fixed-time-slot targets (a Lesson
  // fixed onto a non-teaching slot like 早自習/午休 would never be
  // schedulable), sorted for a stable, predictable dropdown order.
  teachingTimeSlots: TimeSlot[];
}

async function buildFixedTimeSlotData(semesterId: number): Promise<FixedTimeSlotData> {
  const [lessons, requirements, classes, subjects, timeSlots] = await Promise.all([
    listLessons(0, FETCH_LIMIT),
    listRequirements(0, FETCH_LIMIT),
    listClasses(0, FETCH_LIMIT),
    listSubjects(0, FETCH_LIMIT),
    listTimeSlots(0, FETCH_LIMIT),
  ]);

  const classNameById = new Map(classes.map((classItem) => [classItem.id, classItem.name]));
  const subjectNameById = new Map(subjects.map((subject) => [subject.id, subject.name]));

  // One empty group per requirement belonging to this semester, keyed by
  // requirement id -- Lessons are attached to these below. Requirements
  // from OTHER semesters are deliberately left out entirely (never even
  // get an empty group), since a Lesson can only belong to one semester's
  // requirement and showing an empty "0 堂" group for every other
  // semester's requirements would just be noise.
  const groupsByRequirementId = new Map<number, FixedTimeSlotGroup>();
  for (const requirement of requirements) {
    if (requirement.semester_id !== semesterId) {
      continue;
    }
    groupsByRequirementId.set(requirement.id, {
      requirementId: requirement.id,
      label: `${classNameById.get(requirement.class_id) ?? `班級 ID ${requirement.class_id}`}的${
        subjectNameById.get(requirement.subject_id) ?? `科目 ID ${requirement.subject_id}`
      }`,
      lessons: [],
    });
  }

  for (const lesson of lessons) {
    const group = groupsByRequirementId.get(lesson.class_subject_requirement_id);
    if (group === undefined) {
      // Either a different semester's requirement, or (in principle) a
      // requirement that's since been deleted -- either way, not
      // something this semester's "設定固定時段" section should show.
      continue;
    }
    group.lessons.push({
      lessonId: lesson.id,
      sequenceNumber: lesson.sequence_number,
      fixedTimeSlotId: lesson.fixed_time_slot_id,
    });
  }

  const groups = Array.from(groupsByRequirementId.values())
    .filter((group) => group.lessons.length > 0)
    .map((group) => ({
      ...group,
      lessons: [...group.lessons].sort((a, b) => a.sequenceNumber - b.sequenceNumber),
    }))
    .sort((a, b) => a.label.localeCompare(b.label, "zh-Hant"));

  const teachingTimeSlots = timeSlots
    .filter((timeSlot) => timeSlot.is_teaching_period)
    .sort((a, b) => a.weekday - b.weekday || a.period - b.period);

  return { groups, teachingTimeSlots };
}

// `refreshKey` deliberately has no meaning of its own -- it exists so a
// caller can force a refetch (e.g. SchedulerConsole passes generateResult,
// a fresh object every time 展開課程清單 succeeds again) without this hook
// needing to know why. semesterId alone would miss the case where the same
// version's Lessons are regenerated and the set of groups/rows changes.
export function useFixedTimeSlotData(
  semesterId: number | null,
  refreshKey: unknown,
): { data: FixedTimeSlotData | null; isLoading: boolean; errorMessage: string | null } {
  return useResource(
    () =>
      semesterId === null
        ? Promise.resolve<FixedTimeSlotData>({ groups: [], teachingTimeSlots: [] })
        : buildFixedTimeSlotData(semesterId),
    [semesterId, refreshKey],
  );
}
