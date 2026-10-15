import { describe, expect, it } from "vitest";
import { canMoveLessonTo, canSwapLessons } from "./lessonDrop";
import type { EnrichedSchedule } from "../hooks/useTimetableData";
import type { TimeSlot } from "../types/timeSlot";

function lesson(scheduleId: number, timeSlotId: number): EnrichedSchedule {
  return {
    scheduleId,
    lessonId: scheduleId,
    timeSlotId,
    weekday: 1,
    period: 1,
    classId: 10,
    className: "901班A",
    subjectId: 20,
    subjectName: "國語",
    teacherId: 1,
    teacherName: "王老師",
    roomId: null,
    roomName: null,
  };
}

function timeSlot(id: number, teaching = true): TimeSlot {
  return {
    id,
    weekday: 1,
    period: 1,
    is_teaching_period: teaching,
    label: teaching ? null : "午休",
    created_at: "",
    updated_at: "",
  } as TimeSlot;
}

describe("canMoveLessonTo", () => {
  const dragged = lesson(1, 101);

  it("allows another teaching period", () => {
    expect(canMoveLessonTo(dragged, timeSlot(102))).toBe(true);
  });

  it("refuses a non-teaching period", () => {
    expect(canMoveLessonTo(dragged, timeSlot(103, false))).toBe(false);
  });

  it("refuses the lesson's own time slot", () => {
    expect(canMoveLessonTo(dragged, timeSlot(101))).toBe(false);
  });

  it("refuses a cell with no TimeSlot record", () => {
    expect(canMoveLessonTo(dragged, undefined)).toBe(false);
  });
});

describe("canSwapLessons", () => {
  it("allows a lesson in another time slot", () => {
    expect(canSwapLessons(lesson(1, 101), lesson(2, 102))).toBe(true);
  });

  it("refuses a lesson in the same time slot (nothing would change)", () => {
    expect(canSwapLessons(lesson(1, 101), lesson(3, 101))).toBe(false);
  });

  it("refuses the lesson itself", () => {
    expect(canSwapLessons(lesson(1, 101), lesson(1, 101))).toBe(false);
  });
});
