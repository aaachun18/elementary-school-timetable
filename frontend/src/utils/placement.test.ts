import { describe, expect, it } from "vitest";
import {
  PLACE_REFUSAL_MESSAGES,
  blockSize,
  buildPlaceCandidateMarks,
  buildPlacementCards,
  canChooseNoRoom,
  cardsForView,
  describePlaceLine,
  firstPlacedSlot,
  groupCardsByClass,
  lessonCount,
  missingRoomTypeHint,
  needsTeacherChoice,
  placeCandidateCacheKey,
  placeRefusalMessage,
  placeRefusalReasonOf,
  placementChangeLines,
  roomForCard,
  teacherForCard,
} from "./placement";
import type {
  ConstraintViolationDetail,
  PlaceCandidatesResult,
  PlacementChangeDetail,
  ScheduleCheckResult,
  UnscheduledLesson,
} from "../types/scheduler";

function lesson(fields: Partial<UnscheduledLesson>): UnscheduledLesson {
  return {
    lesson_id: 1,
    class_subject_requirement_id: 10,
    class_id: 1,
    class_name: "四年甲班",
    subject_id: 100,
    subject_name: "國語",
    sequence_number: 1,
    required_teacher_id: 7,
    block_no: null,
    block_seq: null,
    lesson_pattern: null,
    fixed_time_slot_id: null,
    suggested_room_id: 50,
    eligible_teachers: [{ teacher_id: 7, name: "王老師" }],
    ...fields,
  };
}

// 自然 2+1 for 四年甲班 (lessons 21-23, nobody required), 國語 for 四年乙班.
const science = (id: number, blockNo: number, blockSeq: number, sequence: number): UnscheduledLesson =>
  lesson({
    lesson_id: id,
    class_subject_requirement_id: 20,
    subject_id: 200,
    subject_name: "自然",
    sequence_number: sequence,
    required_teacher_id: null,
    block_no: blockNo,
    block_seq: blockSeq,
    lesson_pattern: "2+1",
    suggested_room_id: null,
    eligible_teachers: [
      { teacher_id: 8, name: "陳老師" },
      { teacher_id: 9, name: "林老師" },
    ],
  });
const LESSONS: UnscheduledLesson[] = [
  lesson({ lesson_id: 1 }),
  science(21, 1, 1, 1),
  science(22, 1, 2, 2),
  science(23, 2, 1, 3),
  lesson({ lesson_id: 31, class_id: 2, class_name: "四年乙班", class_subject_requirement_id: 30 }),
];

describe("buildPlacementCards", () => {
  const cards = buildPlacementCards(LESSONS);

  it("a single lesson is one card of 1 節", () => {
    expect(cards[0]).toMatchObject({ key: "lesson:1", anchorLessonId: 1, lessonIds: [1], label: "國語 · 1 節", isPartialBlock: false });
  });

  it("merges a block into one card anchored on its first lesson", () => {
    expect(cards[1]).toMatchObject({
      key: "block:20:1",
      anchorLessonId: 21,
      lessonIds: [21, 22],
      label: "自然 · 2 節連堂",
      blockNo: 1,
      isPartialBlock: false,
    });
    // The 「1」 of 2+1 is a card of its own.
    expect(cards[2]).toMatchObject({ key: "block:20:2", lessonIds: [23], label: "自然 · 1 節" });
  });

  it("counts only the unscheduled lessons of a partly placed block, anchored on the first of them", () => {
    const [card] = buildPlacementCards([science(22, 1, 2, 2)]);

    expect(card).toMatchObject({ anchorLessonId: 22, lessonIds: [22], label: "自然 · 1 節", isPartialBlock: true });
  });

  it("orders a block's lessons by place in the block even if listed otherwise", () => {
    const [card] = buildPlacementCards([science(22, 1, 2, 2), science(21, 1, 1, 1)]);

    expect(card.lessonIds).toEqual([21, 22]);
    expect(card.anchorLessonId).toBe(21);
  });

  it("keeps the backend's order and groups by class", () => {
    expect(cards.map((card) => card.key)).toEqual(["lesson:1", "block:20:1", "block:20:2", "lesson:31"]);
    expect(groupCardsByClass(cards).map((group) => [group.className, group.cards.length])).toEqual([
      ["四年甲班", 3],
      ["四年乙班", 1],
    ]);
    expect(lessonCount(cards)).toBe(5);
  });

  it("is empty without lessons", () => {
    expect(buildPlacementCards([])).toEqual([]);
    expect(groupCardsByClass([])).toEqual([]);
  });
});

describe("blockSize", () => {
  it("reads the block's size from the pattern", () => {
    expect(blockSize("2+1", 1)).toBe(2);
    expect(blockSize("2+1", 2)).toBe(1);
    expect(blockSize("2+1", 3)).toBeNull();
    expect(blockSize(null, 1)).toBeNull();
    expect(blockSize("2", null)).toBeNull();
  });
});

describe("cardsForView", () => {
  const cards = buildPlacementCards(LESSONS);

  it("shows only the chosen class in the class view", () => {
    expect(cardsForView(cards, "class", 2, false).map((card) => card.key)).toEqual(["lesson:31"]);
  });

  it("shows every class when asked, with no class chosen, or in the teacher / room views", () => {
    expect(cardsForView(cards, "class", 2, true)).toHaveLength(4);
    expect(cardsForView(cards, "class", null, false)).toHaveLength(4);
    expect(cardsForView(cards, "teacher", 7, false)).toHaveLength(4);
    expect(cardsForView(cards, "room", 50, false)).toHaveLength(4);
  });
});

describe("teacher and room", () => {
  const [single, block] = buildPlacementCards(LESSONS);

  it("uses the required teacher without asking", () => {
    expect(needsTeacherChoice(single)).toBe(false);
    expect(teacherForCard(single, new Map([[single.key, 99]]))).toBe(7);
  });

  it("needs a teacher picked when none is required", () => {
    expect(needsTeacherChoice(block)).toBe(true);
    expect(teacherForCard(block, new Map())).toBeNull();
    expect(teacherForCard(block, new Map([[block.key, 9]]))).toBe(9);
  });

  it("starts from the suggested room, then the one picked (none included)", () => {
    expect(roomForCard(single, new Map())).toBe(50);
    expect(roomForCard(single, new Map([[single.key, 60]]))).toBe(60);
    expect(roomForCard(single, new Map([[single.key, null]]))).toBeNull();
    expect(roomForCard(block, new Map())).toBeNull(); // no suggested room: none, not blocking
  });

  // Task 94: the backend says what its default is (default_room_id); the
  // same three cases as before, now read from the card.
  it("offers 「不指定教室」 only where the backend's default is no room", () => {
    const [withHomeroom] = buildPlacementCards([lesson({ default_room_id: 50 })]); // 原班上課 with a homeroom
    const [noHomeroom] = buildPlacementCards([lesson({ default_room_id: null, suggested_room_id: null })]);
    const [typed] = buildPlacementCards([lesson({ room_type: "自然教室", default_room_id: null, has_matching_room: true })]);
    expect(canChooseNoRoom(withHomeroom)).toBe(false);
    expect(canChooseNoRoom(noHomeroom)).toBe(true);
    expect(canChooseNoRoom(typed)).toBe(true);
  });

  it("reads the room fields, missing ones as null (an older backend)", () => {
    const [card] = buildPlacementCards([lesson({ room_type: "自然教室", default_room_id: null, has_matching_room: false })]);
    expect([card.roomType, card.defaultRoomId, card.hasMatchingRoom]).toEqual(["自然教室", null, false]);
    const [older] = buildPlacementCards([lesson({})]);
    expect([older.roomType, older.defaultRoomId, older.hasMatchingRoom]).toEqual([null, null, null]);
  });

  it("warns on selection when no room has the required type", () => {
    const [missing] = buildPlacementCards([lesson({ room_type: "自然教室", has_matching_room: false })]);
    const [found] = buildPlacementCards([lesson({ room_type: "自然教室", has_matching_room: true })]);
    const [untyped] = buildPlacementCards([lesson({ room_type: null, has_matching_room: null })]);
    expect(missingRoomTypeHint(missing)).toBe("找不到類型「自然教室」的教室，放入後這堂課沒有教室");
    expect(missingRoomTypeHint(found)).toBeNull();
    expect(missingRoomTypeHint(untyped)).toBeNull();
  });
});

describe("placeCandidateCacheKey", () => {
  it("differs by lesson, teacher, room and revision", () => {
    const key = placeCandidateCacheKey(2, 21, 8, null, 0);
    expect(key).toBe("place:2:21:0:t8:rnone");
    expect(placeCandidateCacheKey(2, 21, 9, null, 0)).not.toBe(key);
    expect(placeCandidateCacheKey(2, 21, 8, 60, 0)).not.toBe(key);
    expect(placeCandidateCacheKey(2, 22, 8, null, 0)).not.toBe(key);
    expect(placeCandidateCacheKey(2, 21, 8, null, 1)).not.toBe(key);
  });

  it("is null when there is nothing to fetch (no version, lesson or teacher)", () => {
    expect(placeCandidateCacheKey(null, 21, 8, null, 0)).toBeNull();
    expect(placeCandidateCacheKey(2, null, 8, null, 0)).toBeNull();
    expect(placeCandidateCacheKey(2, 21, null, null, 0)).toBeNull();
  });
});

describe("refusal reasons", () => {
  it("has a Chinese message for every reason the backend sends", () => {
    for (const reason of ["NON_TEACHING_SLOT", "BLOCK_OUT_OF_RANGE", "BLOCK_TARGET_OCCUPIED", "BLOCK_PARTIAL_MISMATCH", "TEACHER_REQUIRED"]) {
      expect(placeRefusalMessage(reason)).toBe(PLACE_REFUSAL_MESSAGES[reason]);
      expect(placeRefusalMessage(reason)).not.toMatch(/[A-Z_]{4,}/);
    }
    expect(placeRefusalMessage("TEACHER_REQUIRED")).toBe("請先選擇教師");
    expect(placeRefusalMessage("SOMETHING_ELSE")).toBeNull();
    expect(placeRefusalMessage(null)).toBeNull();
  });

  it("reads the reason of a 409 only", () => {
    const conflict = { response: { status: 409, data: { detail: "…", reason: "BLOCK_PARTIAL_MISMATCH" } } };
    expect(placeRefusalReasonOf(conflict)).toBe("BLOCK_PARTIAL_MISMATCH");
    expect(placeRefusalReasonOf({ response: { status: 409, data: { detail: "此課程不屬於該課表的學期" } } })).toBeNull();
    expect(placeRefusalReasonOf({ response: { status: 404, data: { reason: "BLOCK_OUT_OF_RANGE" } } })).toBeNull();
    expect(placeRefusalReasonOf({ response: { status: 409, data: { reason: "UNKNOWN" } } })).toBeNull();
    expect(placeRefusalReasonOf(new Error("network"))).toBeNull();
    expect(placeRefusalReasonOf(null)).toBeNull();
  });
});

function violation(fields: Partial<ConstraintViolationDetail>): ConstraintViolationDetail {
  return {
    type: "H1_TEACHER_CONFLICT",
    severity: "ERROR",
    lesson_id: null,
    teacher_id: null,
    class_id: null,
    subject_id: null,
    time_slot_id: null,
    message: "",
    suggested_action: null,
    room_id: null,
    class_subject_requirement_id: null,
    ...fields,
  };
}

function check(violations: ConstraintViolationDetail[]): ScheduleCheckResult {
  return { schedule_version_id: 2, is_valid: violations.length === 0, violation_count: violations.length, violations };
}

describe("buildPlaceCandidateMarks", () => {
  const weekly = violation({ type: "H7_WEEKLY_PERIODS", class_subject_requirement_id: 20, message: "自然的每週節數不符" });
  const clash = violation({ type: "H1_TEACHER_CONFLICT", teacher_id: 8, time_slot_id: 3, lesson_id: 21, message: "陳老師衝堂" });
  const warning = violation({
    type: "TEACHER_MIN_WORKLOAD",
    severity: "WARNING",
    teacher_id: 9,
    identity_key: "TEACHER_MIN_WORKLOAD:9",
    message: "林老師節數太少",
  });
  const data: PlaceCandidatesResult = {
    schedule_version_id: 2,
    lesson_id: 21,
    teacher_id: 8,
    room_id: null,
    baseline: check([weekly]),
    candidates: [
      { time_slot_id: 1, available: true, unavailable_reason: null, check: check([]), block_members: [{ lesson_id: 21, to_time_slot_id: 1 }, { lesson_id: 22, to_time_slot_id: 2 }] },
      { time_slot_id: 3, available: true, unavailable_reason: null, check: check([clash]), block_members: null },
      { time_slot_id: 4, available: false, unavailable_reason: "NON_TEACHING_SLOT", check: null, block_members: null },
      { time_slot_id: 5, available: false, unavailable_reason: "BLOCK_OUT_OF_RANGE", check: null, block_members: null },
      { time_slot_id: 6, available: false, unavailable_reason: "BLOCK_TARGET_OCCUPIED", check: null },
      { time_slot_id: 7, available: false, unavailable_reason: "BLOCK_PARTIAL_MISMATCH", check: null },
      { time_slot_id: 8, available: true, unavailable_reason: null, check: check([weekly, warning]) },
    ],
  };
  const marks = buildPlaceCandidateMarks(data, (v) => v.message);

  it("is safe when nothing new is wrong (a resolved H7 included), a conflict otherwise", () => {
    expect(marks.cells.get(1)).toEqual({ status: "safe" });
    expect(marks.cells.get(3)).toEqual({ status: "conflict", reasons: ["陳老師衝堂"] });
  });

  it("stays safe with only a new warning (ERROR-only rule)", () => {
    expect(marks.cells.get(8)).toEqual({ status: "safe" });
  });

  it("marks the refused slots blocked with the Chinese reason; a non-teaching one is no target", () => {
    expect(marks.cells.get(4)).toEqual({ status: "unavailable" });
    expect(marks.cells.get(5)).toEqual({ status: "blocked", reason: PLACE_REFUSAL_MESSAGES.BLOCK_OUT_OF_RANGE });
    expect(marks.cells.get(6)).toEqual({ status: "blocked", reason: PLACE_REFUSAL_MESSAGES.BLOCK_TARGET_OCCUPIED });
    expect(marks.cells.get(7)).toEqual({ status: "blocked", reason: PLACE_REFUSAL_MESSAGES.BLOCK_PARTIAL_MISMATCH });
  });

  it("knows where a block lands, and has no swaps", () => {
    expect(marks.cellRanges.get(1)).toEqual([1, 2]);
    expect(marks.cellRanges.has(3)).toBe(false);
    expect(marks.swaps.size).toBe(0);
    expect(marks.swapRanges.size).toBe(0);
  });
});

describe("the preview", () => {
  const changes: PlacementChangeDetail[] = [
    { schedule_id: null, lesson_id: 22, teacher_id: 8, previous_time_slot_id: null, new_time_slot_id: 12, previous_room_id: null, new_room_id: null },
    { schedule_id: null, lesson_id: 21, teacher_id: 8, previous_time_slot_id: null, new_time_slot_id: 11, previous_room_id: null, new_room_id: null },
  ];
  const label = (id: number): string => `時段 ${id}`;

  it("says what is placed, and that a block goes as a whole", () => {
    expect(describePlaceLine("四年甲班 國語", "星期一第 2 節", 1)).toBe("四年甲班 國語：放入 星期一第 2 節");
    expect(describePlaceLine("四年甲班 自然", "星期一第 1 節", 2)).toBe("四年甲班 自然：放入 星期一第 1 節（整組 2 節一起放入）");
  });

  it("lists the new rows in block order, matched by lesson_id (no schedule_id yet)", () => {
    expect(placementChangeLines(changes, [21, 22], label)).toEqual(["第 1 節：時段 11", "第 2 節：時段 12"]);
    expect(firstPlacedSlot(changes, [21, 22])).toBe(11);
  });

  it("falls back to the response's own order for a lesson it doesn't know", () => {
    expect(placementChangeLines(changes, [], label)).toEqual(["第 1 節：時段 12", "第 2 節：時段 11"]);
    expect(firstPlacedSlot(changes, [99])).toBe(12);
    expect(firstPlacedSlot([], [21])).toBeNull();
  });
});
