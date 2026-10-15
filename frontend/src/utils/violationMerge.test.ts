import { describe, expect, it } from "vitest";
import { getViolationSentence, type NameLookups } from "./failureDiagnostics";
import {
  diffViolations,
  groupMergedViolationsByType,
  mergeViolationsBySentence,
  violationIdentityKey,
} from "./violationMerge";
import type { ConstraintViolationDetail } from "../types/scheduler";
import type { TimeSlot } from "../types/timeSlot";

function violation(fields: Partial<ConstraintViolationDetail>): ConstraintViolationDetail {
  return {
    type: "",
    severity: "ERROR",
    lesson_id: null,
    teacher_id: null,
    class_id: null,
    subject_id: null,
    time_slot_id: null,
    message: "english message",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: null,
    ...fields,
  };
}

function timeSlot(id: number, weekday: number, period: number, teaching = true): TimeSlot {
  return {
    id,
    weekday,
    period,
    is_teaching_period: teaching,
    label: teaching ? null : "午休",
    created_at: "",
    updated_at: "",
  } as TimeSlot;
}

// Names as in the demo data: 王老師 / 林老師, 901班A / 901班B, 國語 / 英語.
const MONDAY_1 = 501;
const WEDNESDAY_1 = 531;
const FRIDAY_8 = 558;
const MONDAY_LUNCH = 504;
const WEDNESDAY_LUNCH = 534;

const lookups: NameLookups = {
  teacherById: new Map([
    [1, { id: 1, name: "王老師", is_active: true }],
    [2, { id: 2, name: "林老師", is_active: true }],
  ] as never),
  classById: new Map([
    [10, { id: 10, name: "901班A", is_active: true }],
    [11, { id: 11, name: "901班B", is_active: true }],
  ] as never),
  subjectById: new Map([
    [20, { id: 20, name: "國語", is_active: true }],
    [21, { id: 21, name: "英語", is_active: true }],
  ] as never),
  roomById: new Map(),
  timeSlotById: new Map([
    [MONDAY_1, timeSlot(MONDAY_1, 1, 1)],
    [WEDNESDAY_1, timeSlot(WEDNESDAY_1, 3, 1)],
    [FRIDAY_8, timeSlot(FRIDAY_8, 5, 8)],
    [MONDAY_LUNCH, timeSlot(MONDAY_LUNCH, 1, 4, false)],
    [WEDNESDAY_LUNCH, timeSlot(WEDNESDAY_LUNCH, 3, 4, false)],
  ]),
  requirementById: new Map(),
  // 901班A 國語 (lesson 50) is pinned to Friday period 8.
  lessonById: new Map([[50, { id: 50, fixed_time_slot_id: FRIDAY_8 }]] as never),
};

const sentenceOf = (item: ConstraintViolationDetail): string => getViolationSentence(item, lookups);

const fixedMismatchAt = (slotId: number): ConstraintViolationDetail =>
  violation({
    type: "FIXED_TIME_SLOT_MISMATCH",
    lesson_id: 50,
    teacher_id: 1,
    class_id: 10,
    subject_id: 20,
    time_slot_id: slotId,
  });

const linUnavailable = violation({
  type: "H4_TEACHER_AVAILABILITY",
  lesson_id: 52,
  teacher_id: 2,
  class_id: 11,
  subject_id: 21,
  time_slot_id: MONDAY_1,
});

const wangDoubleBooked = (slotId: number, lessonId: number, classId: number) =>
  violation({
    type: "H1_TEACHER_CONFLICT",
    lesson_id: lessonId,
    teacher_id: 1,
    class_id: classId,
    subject_id: 20,
    time_slot_id: slotId,
  });

describe("mergeViolationsBySentence", () => {
  it("merges identical sentences into one line with ×N, keeping first-seen order", () => {
    const merged = mergeViolationsBySentence(
      [wangDoubleBooked(MONDAY_1, 50, 10), linUnavailable, wangDoubleBooked(MONDAY_1, 51, 11)],
      sentenceOf,
    );

    expect(merged.map((item) => [item.sentence, item.count])).toEqual([
      ["王老師在星期一第 1 節被同時排定兩堂課！", 2],
      ["林老師在星期一第 1 節已標記為不可排課，但仍被排入該時段！", 1],
    ]);
    expect(merged[0].violations.map((item) => item.lesson_id)).toEqual([50, 51]);
  });

  it("returns an empty list for no violations", () => {
    expect(mergeViolationsBySentence([], sentenceOf)).toEqual([]);
  });
});

describe("groupMergedViolationsByType", () => {
  it("orders groups by the given type order, then unknown types alphabetically", () => {
    const merged = mergeViolationsBySentence(
      [
        violation({ type: "Z_FUTURE", message: "z" }),
        linUnavailable,
        violation({ type: "A_FUTURE", message: "a" }),
        wangDoubleBooked(MONDAY_1, 50, 10),
      ],
      sentenceOf,
    );

    const groups = groupMergedViolationsByType(merged, [
      "H1_TEACHER_CONFLICT",
      "H4_TEACHER_AVAILABILITY",
    ]);

    expect(groups.map((group) => group.type)).toEqual([
      "H1_TEACHER_CONFLICT",
      "H4_TEACHER_AVAILABILITY",
      "A_FUTURE",
      "Z_FUTURE",
    ]);
  });
});

describe("violationIdentityKey", () => {
  const base = {
    lesson_id: 50,
    teacher_id: 1,
    class_id: 10,
    subject_id: 20,
    room_id: 30,
    class_subject_requirement_id: 40,
  };
  const keyAt = (type: string, slotId: number, extra: Partial<ConstraintViolationDetail> = {}) =>
    violationIdentityKey(violation({ ...base, type, time_slot_id: slotId, ...extra }));

  it.each(["H1_TEACHER_CONFLICT", "H2_CLASS_CONFLICT", "H3_ROOM_CONFLICT", "H4_TEACHER_AVAILABILITY"])(
    "%s includes the time slot (the slot is part of the problem)",
    (type) => {
      expect(keyAt(type, MONDAY_1)).not.toBe(keyAt(type, WEDNESDAY_1));
    },
  );

  it.each([
    "H5_TEACHER_QUALIFICATION",
    "H6_REQUIRED_TEACHER",
    "H7_WEEKLY_PERIODS",
    "H8_TEACHER_MAX_WORKLOAD",
    "H9_ROOM_TYPE",
    "H12_ACTIVE_STATUS",
  ])("%s ignores the time slot", (type) => {
    expect(keyAt(type, MONDAY_1)).toBe(keyAt(type, WEDNESDAY_1));
  });

  it.each(["H11_NON_TEACHING_PERIOD", "FIXED_TIME_SLOT_MISMATCH", "INCOMPLETE_SCHEDULE_ROW"])(
    "%s is keyed by the lesson only",
    (type) => {
      expect(keyAt(type, MONDAY_1)).toBe(keyAt(type, WEDNESDAY_1, { teacher_id: 2, room_id: null }));
      expect(keyAt(type, MONDAY_1)).not.toBe(keyAt(type, MONDAY_1, { lesson_id: 51 }));
    },
  );

  it("keys H1 by teacher + slot, not by which lessons are involved", () => {
    expect(keyAt("H1_TEACHER_CONFLICT", MONDAY_1)).toBe(
      keyAt("H1_TEACHER_CONFLICT", MONDAY_1, { lesson_id: 51, class_id: 11 }),
    );
  });

  it("keeps the type in the key", () => {
    expect(keyAt("H1_TEACHER_CONFLICT", MONDAY_1)).not.toBe(keyAt("H4_TEACHER_AVAILABILITY", MONDAY_1));
  });

  it("treats an unknown type conservatively: every id, slot included", () => {
    expect(keyAt("SOMETHING_NEW", MONDAY_1)).not.toBe(keyAt("SOMETHING_NEW", WEDNESDAY_1));
    expect(keyAt("SOMETHING_NEW", MONDAY_1)).not.toBe(keyAt("SOMETHING_NEW", MONDAY_1, { lesson_id: 51 }));
  });
});

describe("diffViolations", () => {
  const sentences = (items: { sentence: string }[]) => items.map((item) => item.sentence);

  it("a lesson moved but still off its fixed slot is unchanged and 「仍未解決」", () => {
    const diff = diffViolations(
      [fixedMismatchAt(MONDAY_1), linUnavailable],
      [fixedMismatchAt(WEDNESDAY_1), linUnavailable],
      sentenceOf,
    );

    expect(diff.added).toEqual([]);
    expect(diff.resolved).toEqual([]);
    expect(diff.unchanged.map((item) => [item.sentence, item.descriptionChanged])).toEqual([
      ["901班A的國語被固定在星期五第 8 節，但目前排在星期三第 1 節！", true],
      ["林老師在星期一第 1 節已標記為不可排課，但仍被排入該時段！", false],
    ]);
  });

  it("moving the lesson onto its fixed slot resolves the problem", () => {
    const diff = diffViolations([fixedMismatchAt(MONDAY_1), linUnavailable], [linUnavailable], sentenceOf);

    expect(diff.added).toEqual([]);
    expect(sentences(diff.resolved)).toEqual([
      "901班A的國語被固定在星期五第 8 節，但目前排在星期一第 1 節！",
    ]);
    expect(diff.unchanged.map((item) => item.descriptionChanged)).toEqual([false]);
  });

  it("moving the lesson off its fixed slot adds the problem", () => {
    const diff = diffViolations([linUnavailable], [fixedMismatchAt(MONDAY_1), linUnavailable], sentenceOf);

    expect(sentences(diff.added)).toEqual([
      "901班A的國語被固定在星期五第 8 節，但目前排在星期一第 1 節！",
    ]);
    expect(diff.resolved).toEqual([]);
  });

  it("a double booking moved as a whole to another slot is one resolved and one added", () => {
    const diff = diffViolations(
      [wangDoubleBooked(MONDAY_1, 50, 10), wangDoubleBooked(MONDAY_1, 51, 11)],
      [wangDoubleBooked(WEDNESDAY_1, 50, 10), wangDoubleBooked(WEDNESDAY_1, 51, 11)],
      sentenceOf,
    );

    expect(diff.added.map((item) => [item.sentence, item.count])).toEqual([
      ["王老師在星期三第 1 節被同時排定兩堂課！", 2],
    ]);
    expect(diff.resolved.map((item) => [item.sentence, item.count])).toEqual([
      ["王老師在星期一第 1 節被同時排定兩堂課！", 2],
    ]);
    expect(diff.unchanged).toEqual([]);
  });

  it("a lesson moved from one non-teaching period to another is unchanged (H11)", () => {
    const inNonTeaching = (slotId: number) =>
      violation({
        type: "H11_NON_TEACHING_PERIOD",
        lesson_id: 50,
        teacher_id: 1,
        class_id: 10,
        subject_id: 20,
        time_slot_id: slotId,
      });

    const diff = diffViolations([inNonTeaching(MONDAY_LUNCH)], [inNonTeaching(WEDNESDAY_LUNCH)], sentenceOf);

    expect(diff.added).toEqual([]);
    expect(diff.resolved).toEqual([]);
    expect(diff.unchanged.map((item) => [item.sentence, item.descriptionChanged])).toEqual([
      ["901班A的國語被排入非教學時段（星期三第 4 節）！", true],
    ]);
  });

  it("a reassignment that fixes one problem leaves the others as untouched", () => {
    // 901班B 英語 handed from 林老師 to someone available on Monday 1.
    const diff = diffViolations([fixedMismatchAt(MONDAY_1), linUnavailable], [fixedMismatchAt(MONDAY_1)], sentenceOf);

    expect(sentences(diff.resolved)).toEqual([
      "林老師在星期一第 1 節已標記為不可排課，但仍被排入該時段！",
    ]);
    expect(diff.unchanged.map((item) => item.descriptionChanged)).toEqual([false]);
  });
});
