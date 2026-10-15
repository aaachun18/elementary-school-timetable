import { describe, expect, it } from "vitest";
import type { NameLookups } from "./failureDiagnostics";
import { resolveLocateTarget } from "./violationLocate";
import type { ConstraintViolationDetail } from "../types/scheduler";

function violation(fields: Partial<ConstraintViolationDetail>): ConstraintViolationDetail {
  return {
    type: "",
    severity: "ERROR",
    lesson_id: null,
    teacher_id: null,
    class_id: null,
    subject_id: null,
    time_slot_id: null,
    message: "m",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: null,
    ...fields,
  };
}

const TEACHER = 1;
const INACTIVE_TEACHER = 2;
const CLASS = 10;
const INACTIVE_CLASS = 11;
const SUBJECT = 20;
const INACTIVE_SUBJECT = 21;
const ROOM = 30;
const INACTIVE_ROOM = 31;
const REQUIREMENT = 40;
const REQUIREMENT_CLASS = 12;

const lookups: NameLookups = {
  teacherById: new Map([
    [TEACHER, { id: TEACHER, name: "王老師", is_active: true }],
    [INACTIVE_TEACHER, { id: INACTIVE_TEACHER, name: "林老師", is_active: false }],
  ] as never),
  classById: new Map([
    [CLASS, { id: CLASS, name: "901班A", is_active: true }],
    [INACTIVE_CLASS, { id: INACTIVE_CLASS, name: "901班B", is_active: false }],
  ] as never),
  subjectById: new Map([
    [SUBJECT, { id: SUBJECT, name: "國語", is_active: true }],
    [INACTIVE_SUBJECT, { id: INACTIVE_SUBJECT, name: "英語", is_active: false }],
  ] as never),
  roomById: new Map([
    [ROOM, { id: ROOM, name: "音樂教室", is_active: true }],
    [INACTIVE_ROOM, { id: INACTIVE_ROOM, name: "舊教室", is_active: false }],
  ] as never),
  timeSlotById: new Map(),
  requirementById: new Map([
    [REQUIREMENT, { id: REQUIREMENT, class_id: REQUIREMENT_CLASS, subject_id: SUBJECT }],
  ] as never),
};

// Every id filled, as the backend does for per-lesson violations.
const full = { lesson_id: 50, teacher_id: TEACHER, class_id: CLASS, subject_id: SUBJECT, room_id: ROOM, time_slot_id: 501 };

describe("resolveLocateTarget: view chosen by type", () => {
  it.each([
    ["H1_TEACHER_CONFLICT", "teacher", TEACHER],
    ["H4_TEACHER_AVAILABILITY", "teacher", TEACHER],
    ["H5_TEACHER_QUALIFICATION", "teacher", TEACHER],
    ["H6_REQUIRED_TEACHER", "teacher", TEACHER],
    ["H8_TEACHER_MAX_WORKLOAD", "teacher", TEACHER],
    ["H2_CLASS_CONFLICT", "class", CLASS],
    ["H11_NON_TEACHING_PERIOD", "class", CLASS],
    ["H3_ROOM_CONFLICT", "room", ROOM],
    ["H9_ROOM_TYPE", "room", ROOM],
  ])("%s -> %s view", (type, viewMode, targetId) => {
    expect(resolveLocateTarget(violation({ ...full, type }), lookups)).toEqual({ viewMode, targetId });
  });

  it.each(["FIXED_TIME_SLOT_MISMATCH", "INCOMPLETE_SCHEDULE_ROW", "SOMETHING_NEW"])(
    "%s uses the field rule (class first)",
    (type) => {
      expect(resolveLocateTarget(violation({ ...full, type }), lookups)).toEqual({
        viewMode: "class",
        targetId: CLASS,
      });
    },
  );
});

describe("resolveLocateTarget: H12 follows which entity is inactive", () => {
  it.each([
    ["teacher", { teacher_id: INACTIVE_TEACHER }, "teacher", INACTIVE_TEACHER],
    ["class", { class_id: INACTIVE_CLASS }, "class", INACTIVE_CLASS],
    ["subject (shown in the class's view)", { subject_id: INACTIVE_SUBJECT }, "class", CLASS],
    ["room", { room_id: INACTIVE_ROOM }, "room", INACTIVE_ROOM],
  ] as const)("inactive %s", (_label, inactive, viewMode, targetId) => {
    const item = violation({ ...full, ...inactive, type: "H12_ACTIVE_STATUS" });
    expect(resolveLocateTarget(item, lookups)).toEqual({ viewMode, targetId });
  });

  it("falls back to the field rule when nothing is actually inactive", () => {
    const item = violation({ ...full, type: "H12_ACTIVE_STATUS" });
    expect(resolveLocateTarget(item, lookups)).toEqual({ viewMode: "class", targetId: CLASS });
  });
});

describe("resolveLocateTarget: field fallback", () => {
  it("H3 without a room falls back to the class", () => {
    const item = violation({ ...full, type: "H3_ROOM_CONFLICT", room_id: null });
    expect(resolveLocateTarget(item, lookups)).toEqual({ viewMode: "class", targetId: CLASS });
  });

  it("H7 (requirement only) shows the requirement's class", () => {
    const item = violation({ type: "H7_WEEKLY_PERIODS", class_subject_requirement_id: REQUIREMENT });
    expect(resolveLocateTarget(item, lookups)).toEqual({ viewMode: "class", targetId: REQUIREMENT_CLASS });
  });

  it("H8 (teacher only) shows the teacher", () => {
    const item = violation({ type: "H8_TEACHER_MAX_WORKLOAD", teacher_id: TEACHER });
    expect(resolveLocateTarget(item, lookups)).toEqual({ viewMode: "teacher", targetId: TEACHER });
  });

  it("an unknown type with only a room shows the room", () => {
    const item = violation({ type: "SOMETHING_NEW", room_id: ROOM });
    expect(resolveLocateTarget(item, lookups)).toEqual({ viewMode: "room", targetId: ROOM });
  });

  it("returns null when there is nothing to show", () => {
    expect(resolveLocateTarget(violation({ type: "SOMETHING_NEW" }), lookups)).toBeNull();
  });

  it("an unknown requirement id is nothing to show", () => {
    const item = violation({ type: "H7_WEEKLY_PERIODS", class_subject_requirement_id: 999 });
    expect(resolveLocateTarget(item, lookups)).toBeNull();
  });
});
