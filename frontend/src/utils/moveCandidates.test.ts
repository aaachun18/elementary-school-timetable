import { describe, expect, it } from "vitest";
import type {
  ConstraintViolationDetail,
  MoveCandidatesResult,
  ScheduleCheckResult,
} from "../types/scheduler";
import type { TimeSlot } from "../types/timeSlot";
import { getViolationSentence, type NameLookups } from "./failureDiagnostics";
import {
  MAX_LISTED_REASONS,
  assessCandidate,
  buildCandidateMarks,
  candidateCacheKey,
  candidateDescription,
  candidateLabel,
  candidateStateFor,
  markForCell,
  markForSwap,
  swapMarkKey,
  type CandidateMark,
  type CandidateResult,
} from "./moveCandidates";

// Task 84: the candidate marks follow the preview dialog's rule exactly --
// diffViolations() by problem identity, "conflict" = it adds a problem.

// Demo period layout, so sentences show teaching numbers (raw 8 = 第 7 節).
const LABELS: Record<number, string> = { 0: "早自習", 5: "午餐/午休" };
function slotId(weekday: number, period: number): number {
  return 900 + (weekday - 1) * 15 + period;
}
function timeSlots(): TimeSlot[] {
  const slots: TimeSlot[] = [];
  for (let weekday = 1; weekday <= 5; weekday += 1) {
    for (let period = 0; period <= 8; period += 1) {
      const label = LABELS[period] ?? null;
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
    }
  }
  return slots;
}

const lookups: NameLookups = {
  teacherById: new Map([
    [1, { id: 1, name: "王老師", is_active: true }],
    [2, { id: 2, name: "林老師", is_active: true }],
  ] as never),
  classById: new Map([
    [10, { id: 10, name: "901班A", is_active: true }],
    [11, { id: 11, name: "901班B", is_active: true }],
  ] as never),
  subjectById: new Map([[20, { id: 20, name: "國語", is_active: true }]] as never),
  roomById: new Map(),
  timeSlotById: new Map(timeSlots().map((slot) => [slot.id, slot])),
  requirementById: new Map(),
};
const sentenceOf = (violation: ConstraintViolationDetail): string =>
  getViolationSentence(violation, lookups);

const MON_1 = slotId(1, 1);
const FRI_8 = slotId(5, 8);
const LUNCH = slotId(1, 5);

function violation(fields: Partial<ConstraintViolationDetail>): ConstraintViolationDetail {
  return {
    type: "H1_TEACHER_CONFLICT",
    severity: "ERROR",
    lesson_id: null,
    teacher_id: null,
    class_id: null,
    subject_id: null,
    time_slot_id: null,
    message: "english",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: null,
    ...fields,
  };
}

function check(...violations: ConstraintViolationDetail[]): ScheduleCheckResult {
  return {
    schedule_version_id: 1,
    is_valid: violations.length === 0,
    violation_count: violations.length,
    violations,
  };
}

// 王老師 double-booked at 星期五第 7 節 -- reported once per lesson (×2).
const teacherClash = [
  violation({ type: "H1_TEACHER_CONFLICT", teacher_id: 1, time_slot_id: FRI_8, lesson_id: 1 }),
  violation({ type: "H1_TEACHER_CONFLICT", teacher_id: 1, time_slot_id: FRI_8, lesson_id: 2 }),
];
const linUnavailable = violation({
  type: "H4_TEACHER_AVAILABILITY",
  teacher_id: 2,
  time_slot_id: MON_1,
  lesson_id: 3,
});
const classClash = violation({ type: "H2_CLASS_CONFLICT", class_id: 10, time_slot_id: MON_1, lesson_id: 4 });

describe("assessCandidate", () => {
  it("is a conflict when the change adds a problem, with the preview's sentences", () => {
    const mark = assessCandidate(check(), check(...teacherClash), sentenceOf);

    expect(mark).toEqual({
      status: "conflict",
      reasons: ["王老師在星期五第 7 節被同時排定兩堂課！ ×2"],
    });
  });

  it("is safe when the change only resolves problems", () => {
    expect(assessCandidate(check(linUnavailable), check(), sentenceOf)).toEqual({ status: "safe" });
  });

  it("is safe when an old problem simply stays", () => {
    expect(assessCandidate(check(linUnavailable), check(linUnavailable), sentenceOf)).toEqual({
      status: "safe",
    });
  });

  it("lists only the added problems when a change both solves and adds", () => {
    const mark = assessCandidate(check(linUnavailable), check(classClash), sentenceOf);

    expect(mark).toEqual({
      status: "conflict",
      reasons: ["901班A在星期一第 1 節被同時排定兩堂課！"],
    });
  });

  it("treats a problem that only moved (same identity) as not new", () => {
    // Still off its fixed slot, just in another wrong slot: same problem.
    const offFixed = (slot: number): ConstraintViolationDetail =>
      violation({ type: "FIXED_TIME_SLOT_MISMATCH", lesson_id: 7, class_id: 10, subject_id: 20, time_slot_id: slot });

    expect(assessCandidate(check(offFixed(MON_1)), check(offFixed(slotId(2, 2))), sentenceOf)).toEqual({
      status: "safe",
    });
  });
});

const response: MoveCandidatesResult = {
  schedule_version_id: 1,
  schedule_id: 50,
  current_time_slot_id: MON_1,
  baseline: check(linUnavailable),
  candidates: [
    { time_slot_id: LUNCH, available: false, unavailable_reason: "NON_TEACHING_SLOT", move: null, swaps: [] },
    { time_slot_id: MON_1, available: false, unavailable_reason: "CURRENT_SLOT", move: null, swaps: [] },
    {
      time_slot_id: FRI_8,
      available: true,
      unavailable_reason: null,
      move: check(linUnavailable, ...teacherClash),
      swaps: [
        { swap_with_schedule_id: 60, check: check() },
        { swap_with_schedule_id: 61, check: check(linUnavailable, classClash) },
      ],
    },
    {
      time_slot_id: slotId(2, 2),
      available: true,
      unavailable_reason: null,
      move: check(),
      swaps: [],
    },
  ],
};

describe("markForCell (dropping on the empty part of a cell: move)", () => {
  it("assesses the move of an available slot", () => {
    expect(markForCell(response, FRI_8, sentenceOf).status).toBe("conflict");
    expect(markForCell(response, slotId(2, 2), sentenceOf)).toEqual({ status: "safe" });
  });

  it("marks non-teaching and current slots unavailable", () => {
    expect(markForCell(response, LUNCH, sentenceOf)).toEqual({ status: "unavailable" });
    expect(markForCell(response, MON_1, sentenceOf)).toEqual({ status: "unavailable" });
  });

  it("gives no hint for a slot the response doesn't list", () => {
    expect(markForCell(response, 12345, sentenceOf)).toEqual({ status: "none" });
  });
});

describe("markForSwap (dropping on a lesson: swap)", () => {
  it("uses the swap entry of that lesson", () => {
    expect(markForSwap(response, FRI_8, 60, sentenceOf)).toEqual({ status: "safe" });
    expect(markForSwap(response, FRI_8, 61, sentenceOf)).toEqual({
      status: "conflict",
      reasons: ["901班A在星期一第 1 節被同時排定兩堂課！"],
    });
  });

  it("gives no hint when the lesson or the slot isn't listed", () => {
    expect(markForSwap(response, FRI_8, 99, sentenceOf)).toEqual({ status: "none" });
    expect(markForSwap(response, 12345, 60, sentenceOf)).toEqual({ status: "none" });
  });
});

describe("buildCandidateMarks", () => {
  it("precomputes every cell and swap mark of one response", () => {
    const marks = buildCandidateMarks(response, sentenceOf);

    expect(marks.cells.get(FRI_8)?.status).toBe("conflict");
    expect(marks.cells.get(LUNCH)).toEqual({ status: "unavailable" });
    expect(marks.cells.get(slotId(2, 2))).toEqual({ status: "safe" });
    expect(marks.swaps.get(swapMarkKey(FRI_8, 60))).toEqual({ status: "safe" });
    expect(marks.swaps.get(swapMarkKey(FRI_8, 61))?.status).toBe("conflict");
    expect(marks.swaps.size).toBe(2);
  });
});

describe("labels and descriptions (never colour alone)", () => {
  const conflict = (count: number): CandidateMark => ({
    status: "conflict",
    reasons: Array.from({ length: count }, (_, i) => `原因${i + 1}`),
  });

  it("labels move and swap targets", () => {
    expect(candidateLabel({ status: "safe" }, "move")).toBe("可放");
    expect(candidateLabel({ status: "safe" }, "swap")).toBe("可對調");
    expect(candidateLabel(conflict(1), "move")).toBe("衝突");
    expect(candidateLabel({ status: "unavailable" }, "move")).toBeNull();
    expect(candidateLabel({ status: "none" }, "swap")).toBeNull();
  });

  it("describes what the drop would do", () => {
    expect(candidateDescription({ status: "safe" }, "move")).toBe("移到這裡不會新增問題");
    expect(candidateDescription({ status: "safe" }, "swap")).toBe("與這堂課對調不會新增問題");
    expect(candidateDescription(conflict(2), "move")).toBe("移到這裡會新增問題：原因1；原因2");
    expect(candidateDescription({ status: "unavailable" }, "move")).toBeNull();
  });

  it(`lists at most ${MAX_LISTED_REASONS} reasons, then 「…等 N 項」`, () => {
    expect(candidateDescription(conflict(3), "move")).toBe("移到這裡會新增問題：原因1；原因2；原因3");
    expect(candidateDescription(conflict(5), "swap")).toBe(
      "與這堂課對調會新增問題：原因1；原因2；原因3…等 5 項",
    );
  });
});

describe("candidateCacheKey", () => {
  it("is null when there is no version or lesson", () => {
    expect(candidateCacheKey(null, 5, 0)).toBeNull();
    expect(candidateCacheKey(1, null, 0)).toBeNull();
  });

  it("differs per version, lesson and edit revision", () => {
    const key = candidateCacheKey(1, 5, 0);
    expect(key).toBe(candidateCacheKey(1, 5, 0));
    expect(new Set([key, candidateCacheKey(2, 5, 0), candidateCacheKey(1, 6, 0), candidateCacheKey(1, 5, 1)]).size).toBe(4);
  });
});

describe("candidateStateFor (stale responses)", () => {
  const ok: CandidateResult = { ok: true, data: response };

  it("is idle without a key, loading until its own result arrives", () => {
    expect(candidateStateFor(new Map(), null)).toEqual({ status: "idle" });
    expect(candidateStateFor(new Map(), "1:5:0")).toEqual({ status: "loading" });
  });

  it("shows only the current key's result", () => {
    // A late response for another lesson (or an older revision) is stored
    // under its own key and never shown for the current one.
    const results = new Map<string, CandidateResult>([["1:6:0", ok], ["1:5:0", { ok: false }]]);

    expect(candidateStateFor(results, "1:5:0")).toEqual({ status: "failed" });
    expect(candidateStateFor(results, "1:6:0")).toEqual({ status: "ready", data: response });
    expect(candidateStateFor(results, "1:5:1")).toEqual({ status: "loading" });
  });
});
