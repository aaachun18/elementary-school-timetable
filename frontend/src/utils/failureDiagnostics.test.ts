import { describe, expect, it } from "vitest";
import { resolveViolationPageTarget } from "../constants/violationPageMapping";
import type { ConstraintViolationDetail } from "../types/scheduler";
import type { TimeSlot } from "../types/timeSlot";
import { getViolationSentence, type NameLookups } from "./failureDiagnostics";

// Task 81: the scheduler's pre-check reasons for fixed time slots that can
// never be honored (STATIC_FIXED_SLOT_*), as the console's failure
// diagnostics shows them. Time slots use the demo layout -- raw period 0
// 早自習, 1-4, 5 午餐/午休, 6-8, 9 放學 (Monday only) -- so a fixed slot at raw
// period 8 must read "第 7 節", never the raw number.

const NON_TEACHING_LABELS: Record<number, string> = { 0: "早自習", 5: "午餐/午休", 9: "放學" };

function slotId(weekday: number, period: number): number {
  return 700 + (weekday - 1) * 15 + period;
}

function demoTimeSlots(): TimeSlot[] {
  const slots: TimeSlot[] = [];
  const add = (weekday: number, period: number): void => {
    const label = NON_TEACHING_LABELS[period] ?? null;
    slots.push({
      id: slotId(weekday, period),
      weekday,
      period,
      start_time: null,
      end_time: null,
      is_teaching_period: label === null,
      label,
      created_at: "",
      updated_at: "",
    });
  };
  for (let weekday = 1; weekday <= 5; weekday += 1) {
    for (let period = 0; period <= 8; period += 1) {
      add(weekday, period);
    }
  }
  add(1, 9);
  return slots;
}

const lookups: NameLookups = {
  teacherById: new Map([[1, { id: 1, name: "王老師", is_active: true }]] as never),
  classById: new Map([[10, { id: 10, name: "901班A", is_active: true }]] as never),
  subjectById: new Map([[20, { id: 20, name: "國語", is_active: true }]] as never),
  roomById: new Map(),
  timeSlotById: new Map(demoTimeSlots().map((slot) => [slot.id, slot])),
  requirementById: new Map(),
};

const FRIDAY_8 = slotId(5, 8);
const MONDAY_LUNCH = slotId(1, 5);

function fixedSlotViolation(
  type: string,
  fields: Partial<ConstraintViolationDetail> = {},
): ConstraintViolationDetail {
  return {
    type,
    severity: "ERROR",
    lesson_id: 50,
    teacher_id: null,
    class_id: 10,
    subject_id: 20,
    time_slot_id: FRIDAY_8,
    message: "english message",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: 5,
    ...fields,
  };
}

describe("fixed time slot pre-check sentences", () => {
  it.each([
    [
      "STATIC_FIXED_SLOT_UNKNOWN",
      { time_slot_id: 99_999 },
      "901班A的國語被固定的時段不存在（時段 ID 99999）！",
    ],
    [
      "STATIC_FIXED_SLOT_NON_TEACHING",
      { time_slot_id: MONDAY_LUNCH },
      "901班A的國語被固定在星期一午餐/午休，但這不是教學時段！",
    ],
    [
      "STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE",
      { teacher_id: 1 },
      "901班A的國語被固定在星期五第 7 節，但王老師在這個時段不可排課！",
    ],
    [
      "STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE",
      {},
      "901班A的國語被固定在星期五第 7 節，但所有可教授國語的教師在這個時段都不可排課！",
    ],
    [
      "STATIC_FIXED_SLOT_CLASS_CLASH",
      {},
      "901班A的國語被固定在星期五第 7 節，但901班A在同一時段還有其他固定的課！",
    ],
    [
      "STATIC_FIXED_SLOT_TEACHER_CLASH",
      { teacher_id: 1 },
      "901班A的國語被固定在星期五第 7 節，但只能由王老師授課，而王老師在同一時段還有其他固定的課！",
    ],
    [
      "STATIC_FIXED_SLOT_ROOM_SHORTAGE",
      {},
      "901班A的國語被固定在星期五第 7 節，但同一時段需要相同類型教室的固定課程多於教室數量！",
    ],
  ])("%s %j", (type, fields, expected) => {
    const sentence = getViolationSentence(fixedSlotViolation(type, fields), lookups);

    expect(sentence).toBe(expected);
    // Never the raw period of the afternoon slot.
    expect(sentence).not.toContain("第 8 節");
    expect(sentence).not.toContain("english message");
  });

  it("points every fixed-slot reason at the scheduler console", () => {
    for (const type of [
      "STATIC_FIXED_SLOT_UNKNOWN",
      "STATIC_FIXED_SLOT_NON_TEACHING",
      "STATIC_FIXED_SLOT_TEACHER_UNAVAILABLE",
      "STATIC_FIXED_SLOT_CLASS_CLASH",
      "STATIC_FIXED_SLOT_TEACHER_CLASH",
      "STATIC_FIXED_SLOT_ROOM_SHORTAGE",
    ]) {
      expect(resolveViolationPageTarget(fixedSlotViolation(type), lookups)).toEqual({
        kind: "link",
        label: "排課控制台（設定固定時段）",
        path: "/scheduler",
      });
    }
  });

  it("still falls back to the English message for a type it doesn't know", () => {
    expect(getViolationSentence(fixedSlotViolation("STATIC_SOMETHING_NEW"), lookups)).toBe(
      "english message",
    );
  });
});
