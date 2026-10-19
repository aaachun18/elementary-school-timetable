import { describe, expect, it } from "vitest";
import { resolveViolationPageTarget } from "../constants/violationPageMapping";
import type { ConstraintViolationDetail } from "../types/scheduler";
import type { TimeSlot } from "../types/timeSlot";
import {
  getGroupedLessonFailureSentence,
  getViolationSentence,
  type NameLookups,
} from "./failureDiagnostics";

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

// --- Task 90: lesson blocks (連堂) and the minimum workload warning ---

describe("Task 90: lesson block sentences", () => {
  it.each([
    [
      "BLOCK_NOT_CONSECUTIVE",
      { block_no: 1, time_slot_id: FRIDAY_8 },
      "901班A的國語第 1 組連堂沒有排在同一天相鄰的節次！",
    ],
    ["BLOCK_NOT_CONSECUTIVE", { time_slot_id: FRIDAY_8 }, "901班A的國語連堂沒有排在同一天相鄰的節次！"],
    ["BLOCK_SAME_DAY", { block_no: 2, time_slot_id: FRIDAY_8 }, "901班A的國語有不同組的連堂排在同一天（星期五）！"],
    [
      "TEACHER_MIN_WORKLOAD",
      { teacher_id: 1, class_id: null, subject_id: null, lesson_id: null, time_slot_id: null },
      "王老師的排課總節數低於每週最低授課節數！",
    ],
    ["BLOCK_NO_WINDOW", { time_slot_id: null }, "901班A的國語的連堂找不到同一天足夠的連續教學節次！"],
    [
      "STATIC_BLOCK_TOO_LONG",
      { time_slot_id: null },
      "901班A的國語的連堂樣式中，有一組的節數超過任何一天可連續上課的節數！",
    ],
    ["STATIC_BLOCK_TOO_MANY_DAYS", { time_slot_id: null }, "901班A的國語的連堂組數多於一週的上課天數！"],
    [
      "STATIC_BLOCK_NOT_ENOUGH_DAYS",
      { time_slot_id: null },
      "901班A的國語的各組連堂要排在不同天，但有足夠連續節次的天數不夠！",
    ],
    [
      "STATIC_BLOCK_FIXED_CONFLICT",
      { time_slot_id: null },
      "901班A的國語同一組連堂的固定時段，無法排成同一天依序相鄰的節次！",
    ],
    ["STATIC_BLOCK_FIXED_SAME_DAY", { time_slot_id: null }, "901班A的國語有不同組的連堂被固定在同一天！"],
    [
      "STATIC_BLOCK_TEACHER_UNAVAILABLE",
      { teacher_id: 1, time_slot_id: null },
      "901班A的國語的連堂排不進去：王老師在每一段可用的連續節次中都有不可排課的時段！",
    ],
    [
      "STATIC_BLOCK_TEACHER_UNAVAILABLE",
      { time_slot_id: null },
      "901班A的國語的連堂排不進去：所有可教授國語的教師在每一段可用的連續節次中都有不可排課的時段！",
    ],
  ])("%s %j", (type, fields, expected) => {
    const sentence = getViolationSentence(fixedSlotViolation(type, fields), lookups);

    expect(sentence).toBe(expected);
    expect(sentence).not.toContain("english message");
  });

  it("points every block pre-check at the page that fixes it", () => {
    const pathOf = (type: string): string | null => {
      const target = resolveViolationPageTarget(fixedSlotViolation(type), lookups);
      return target.kind === "link" ? target.path : null;
    };
    expect(pathOf("STATIC_BLOCK_TOO_LONG")).toBe("/requirements");
    expect(pathOf("STATIC_BLOCK_TOO_MANY_DAYS")).toBe("/requirements");
    expect(pathOf("STATIC_BLOCK_NOT_ENOUGH_DAYS")).toBe("/requirements");
    expect(pathOf("BLOCK_NO_WINDOW")).toBe("/requirements");
    expect(pathOf("STATIC_BLOCK_FIXED_CONFLICT")).toBe("/scheduler");
    expect(pathOf("STATIC_BLOCK_FIXED_SAME_DAY")).toBe("/scheduler");
    expect(pathOf("STATIC_BLOCK_TEACHER_UNAVAILABLE")).toBe("/data?tab=teachers");
    expect(pathOf("TEACHER_MIN_WORKLOAD")).toBe("/data?tab=teachers");
  });

  it("explains a block lesson failure in the grouped sentence", () => {
    const sentence = getGroupedLessonFailureSentence(
      {
        key: "k",
        classSubjectRequirementId: 5,
        lessonIds: [50, 51],
        representative: fixedSlotViolation("BLOCK_NO_WINDOW", { time_slot_id: null }),
      },
      { ...lookups, requirementById: new Map([[5, { id: 5, class_id: 10, subject_id: 20 }]] as never) },
    );
    expect(sentence).toBe("901班A的國語（共 2 堂課）：連堂找不到同一天足夠的連續教學節次，這些課無法排定！");
  });
});

// Task 93: the room pre-checks of backend Task 92B.
describe("room pre-check sentences and pages", () => {
  const roomLookups: NameLookups = {
    ...lookups,
    roomById: new Map([[60, { id: 60, name: "901班A教室", room_type: "普通教室", is_active: false }]] as never),
    requirementById: new Map([[5, { id: 5, class_id: 10, subject_id: 20, required_room_type: "自然教室 " }]] as never),
  };
  const pathOf = (violation: ConstraintViolationDetail): string | null => {
    const target = resolveViolationPageTarget(violation, roomLookups);
    return target.kind === "link" ? target.path : null;
  };

  it.each([
    [
      "STATIC_ROOM_TYPE_NOT_FOUND",
      { lesson_id: null, time_slot_id: null },
      "901班A的國語指定的教室類型「自然教室 」找不到任何可用的教室！",
      "/requirements",
    ],
    [
      "STATIC_HOMEROOM_OVERBOOKED",
      { lesson_id: null, time_slot_id: null, class_id: null, subject_id: null, class_subject_requirement_id: null, room_id: 60 },
      "導師教室901班A教室要上的課多於一週的教學時段，共用這間教室的班級排不下！",
      "/data?tab=classes",
    ],
    [
      "STATIC_FIXED_SLOT_HOMEROOM_CLASH",
      { room_id: 60 },
      "901班A的國語被固定在星期五第 7 節，但共用導師教室901班A教室的另一班同一時段也有固定的課！",
      "/scheduler",
    ],
  ])("%s", (type, fields, sentence, path) => {
    const violation = fixedSlotViolation(type, fields as Partial<ConstraintViolationDetail>);

    expect(getViolationSentence(violation, roomLookups)).toBe(sentence);
    expect(pathOf(violation)).toBe(path);
  });

  it("points an inactive homeroom at the rooms tab", () => {
    const violation = fixedSlotViolation("STATIC_INACTIVE_ENTITY_CONFLICT", {
      lesson_id: null,
      class_id: null,
      subject_id: null,
      time_slot_id: null,
      room_id: 60,
    });

    expect(getViolationSentence(violation, roomLookups)).toContain("教室 901班A教室");
    expect(pathOf(violation)).toBe("/data?tab=rooms");
  });
});
