import { list as listSchedules } from "../api/schedules";
import { list as listLessons } from "../api/lessons";
import { list as listRequirements } from "../api/classSubjectRequirements";
import { list as listTimeSlots } from "../api/timeSlots";
import { list as listTeachers } from "../api/teachers";
import { list as listClasses } from "../api/classes";
import { list as listSubjects } from "../api/subjects";
import { list as listRooms } from "../api/rooms";
import { useResource } from "./useResource";
import type { TimeSlot } from "../types/timeSlot";

// One flattened, ready-to-render row: everything TimetableView.tsx's grid
// needs, with every id already resolved to a display name. This is the
// "clear intermediate type" the Task explicitly asked for, so the join
// logic below reads as a straight-line assembly instead of nested lookups
// scattered through the page component.
export interface EnrichedSchedule {
  scheduleId: number;
  weekday: number;
  period: number;
  classId: number;
  className: string;
  subjectId: number;
  subjectName: string;
  teacherId: number | null;
  teacherName: string | null;
  roomId: number | null;
  roomName: string | null;
}

// Task 35.5: a (weekday, period) TimeSlot lookup key. Task 35 originally
// picked one "representative" TimeSlot per period (lowest weekday) for the
// whole row, which silently collapsed different labels on different
// weekdays (e.g. Monday period 0 = "早自習", Wednesday period 0 = "導師
// 時間") into a single row-level label. Cells now look up their own
// (weekday, period) TimeSlot independently, so this key is what makes
// that possible without an O(n) scan per cell.
function timeSlotKey(weekday: number, period: number): string {
  return `${weekday}-${period}`;
}

export interface TimetableData {
  schedules: EnrichedSchedule[];
  // Task 35.5: the row axis is now just the distinct period numbers in
  // use, sorted -- purely a row count/order, carrying no label or
  // is_teaching_period of its own, since those are per-cell now.
  periods: number[];
  // Every TimeSlot keyed by (weekday, period) via timeSlotKey(), so
  // TimetableView.tsx can decide each individual cell's teaching/
  // non-teaching status and label without depending on any other weekday.
  timeSlotByWeekdayAndPeriod: Map<string, TimeSlot>;
}

// GET /api/v1/schedules/ has no schedule_version_id filter (confirmed by
// reading backend/app/routers/schedule.py, not guessed) -- every list()
// call here fetches everything and this function filters/joins client-side.
// A generously large limit is passed explicitly rather than relying on the
// usual default of 100: the schedules table alone already holds 100+ rows
// across every ScheduleVersion this project's dev database has ever had a
// successful run-scheduler call for.
const FETCH_LIMIT = 1000;

// Task 35: TimeSlot has no semester_id/school_id column at all (see
// backend/app/models/time_slot.py) -- the school's period structure is a
// single global thing, not scoped per semester. So "全校" isn't a choice
// made among options, it's the only scope the data model actually
// supports; there is no per-semester TimeSlot data to narrow to.
function buildPeriods(timeSlots: TimeSlot[]): number[] {
  return Array.from(new Set(timeSlots.map((timeSlot) => timeSlot.period))).sort(
    (a, b) => a - b,
  );
}

async function buildTimetableData(scheduleVersionId: number): Promise<TimetableData> {
  const [schedules, lessons, requirements, timeSlots, teachers, classes, subjects, rooms] =
    await Promise.all([
      listSchedules(0, FETCH_LIMIT),
      listLessons(0, FETCH_LIMIT),
      listRequirements(0, FETCH_LIMIT),
      listTimeSlots(0, FETCH_LIMIT),
      listTeachers(0, FETCH_LIMIT),
      listClasses(0, FETCH_LIMIT),
      listSubjects(0, FETCH_LIMIT),
      listRooms(0, FETCH_LIMIT),
    ]);

  const relevantSchedules = schedules.filter(
    (schedule) => schedule.schedule_version_id === scheduleVersionId,
  );

  const lessonById = new Map(lessons.map((lesson) => [lesson.id, lesson]));
  const requirementById = new Map(
    requirements.map((requirement) => [requirement.id, requirement]),
  );
  const timeSlotById = new Map(timeSlots.map((timeSlot) => [timeSlot.id, timeSlot]));
  const teacherById = new Map(teachers.map((teacher) => [teacher.id, teacher]));
  const classById = new Map(classes.map((classItem) => [classItem.id, classItem]));
  const subjectById = new Map(subjects.map((subject) => [subject.id, subject]));
  const roomById = new Map(rooms.map((room) => [room.id, room]));

  const enriched: EnrichedSchedule[] = [];

  for (const schedule of relevantSchedules) {
    // Schedule.lesson_id -> Lesson.class_subject_requirement_id ->
    // ClassSubjectRequirement.{class_id, subject_id}
    const lesson = lessonById.get(schedule.lesson_id);
    if (lesson === undefined) {
      continue;
    }
    const requirement = requirementById.get(lesson.class_subject_requirement_id);
    if (requirement === undefined) {
      continue;
    }
    // Schedule.time_slot_id -> TimeSlot.{weekday, period}. A Schedule row
    // can exist with time_slot_id still null (see app/models/schedule.py)
    // -- there is no weekday/period to place it at on the grid, so it's
    // skipped rather than guessed at.
    if (schedule.time_slot_id === null) {
      continue;
    }
    const timeSlot = timeSlotById.get(schedule.time_slot_id);
    if (timeSlot === undefined) {
      continue;
    }

    const classItem = classById.get(requirement.class_id);
    const subject = subjectById.get(requirement.subject_id);
    const teacher =
      schedule.teacher_id !== null ? teacherById.get(schedule.teacher_id) : undefined;
    const room = schedule.room_id !== null ? roomById.get(schedule.room_id) : undefined;

    enriched.push({
      scheduleId: schedule.id,
      weekday: timeSlot.weekday,
      period: timeSlot.period,
      classId: requirement.class_id,
      className: classItem?.name ?? `班級 ID ${requirement.class_id}`,
      subjectId: requirement.subject_id,
      subjectName: subject?.name ?? `科目 ID ${requirement.subject_id}`,
      teacherId: schedule.teacher_id,
      teacherName:
        schedule.teacher_id === null
          ? null
          : (teacher?.name ?? `教師 ID ${schedule.teacher_id}`),
      roomId: schedule.room_id,
      roomName:
        schedule.room_id === null ? null : (room?.name ?? `教室 ID ${schedule.room_id}`),
    });
  }

  const timeSlotByWeekdayAndPeriod = new Map(
    timeSlots.map((timeSlot) => [
      timeSlotKey(timeSlot.weekday, timeSlot.period),
      timeSlot,
    ]),
  );

  return {
    schedules: enriched,
    periods: buildPeriods(timeSlots),
    timeSlotByWeekdayAndPeriod,
  };
}

export function useTimetableData(scheduleVersionId: number | null): {
  data: TimetableData | null;
  isLoading: boolean;
  errorMessage: string | null;
} {
  return useResource(
    () =>
      scheduleVersionId === null
        ? Promise.resolve<TimetableData>({
            schedules: [],
            periods: [],
            timeSlotByWeekdayAndPeriod: new Map(),
          })
        : buildTimetableData(scheduleVersionId),
    [scheduleVersionId],
  );
}

export { timeSlotKey };
