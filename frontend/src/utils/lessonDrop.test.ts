import { describe, expect, it } from "vitest";
import {
  canMoveLessonTo,
  canSwapLessons,
  homeroomTargetId,
  lessonTargetId,
  pickDraggedLesson,
} from "./lessonDrop";
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
    specialRoomName: null,
    // Task 90: no lesson block.
    requirementId: 40,
    blockNo: null,
    blockSeq: null,
    blockSize: 0,
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

describe("lessonTargetId (Task 84)", () => {
  it("is the class, teacher or room the lesson is listed under in each view", () => {
    const row = { ...lesson(1, 100), classId: 10, teacherId: 1, roomId: 7 };

    expect(lessonTargetId(row, "class")).toBe(10);
    expect(lessonTargetId(row, "teacher")).toBe(1);
    expect(lessonTargetId(row, "room")).toBe(7);
  });

  it("lists a lesson without a room under its class's own classroom", () => {
    expect(lessonTargetId(lesson(2, 100), "room")).toBe(homeroomTargetId(10));
    expect(homeroomTargetId(10)).toBe(-10);
  });
});

describe("pickDraggedLesson", () => {
  const schedules = [{ scheduleId: 1 }, { scheduleId: 2 }];

  // Regression (Task 103): the drop hint said 「移到這裡」, but the drop read
  // only the drag data, which some browsers handed back unreadable -- the
  // lesson the grid saw start the drag must win.
  it("uses the lesson the drag started with, whatever the drag data says", () => {
    expect(pickDraggedLesson(schedules[1], "", schedules)).toBe(schedules[1]);
    expect(pickDraggedLesson(schedules[1], "not a number", schedules)).toBe(schedules[1]);
    expect(pickDraggedLesson(schedules[1], "1", schedules)).toBe(schedules[1]);
  });

  it("falls back to the drag data's scheduleId", () => {
    expect(pickDraggedLesson(null, "1", schedules)).toBe(schedules[0]);
  });

  it("is no lesson for a card's drag data, nothing, or a lesson no longer listed", () => {
    expect(pickDraggedLesson(null, "place:12-3", schedules)).toBeUndefined();
    expect(pickDraggedLesson(null, "", schedules)).toBeUndefined();
    expect(pickDraggedLesson({ scheduleId: 9 }, "", schedules)).toBeUndefined();
  });
});
