import { describe, expect, it } from "vitest";
import { copyRoomsResultText, planRequiredRoomCopy } from "./requiredRoomCopy";

const SCIENCE = 1;
const ART = 2;

function requirement(id: number, classId: number, subjectId: number, roomId: number | null, isLocked = false) {
  return { id, class_id: classId, subject_id: subjectId, required_room_id: roomId, is_locked: isLocked };
}

describe("planRequiredRoomCopy", () => {
  it("gives every other class of the grade the source's room, subject by subject", () => {
    const plan = planRequiredRoomCopy({
      sourceClassId: 10,
      gradeClassIds: [10, 11, 12],
      requirements: [
        requirement(1, 10, SCIENCE, 50),
        requirement(2, 10, ART, null),
        requirement(3, 11, SCIENCE, null),
        requirement(4, 11, ART, 60),
        requirement(5, 12, SCIENCE, 60),
      ],
      activeRoomIds: new Set([50, 60]),
    });

    expect(plan.items).toEqual([
      { id: 3, required_room_id: 50 },
      { id: 5, required_room_id: 50 },
      // 原班教室 is copied too.
      { id: 4, required_room_id: null },
    ]);
    expect(plan.copiedClassIds.sort()).toEqual([11, 12]);
    // Class 12 has no 美勞.
    expect(plan.skippedCount).toBe(1);
  });

  it("skips locked targets and a source room that is 停用", () => {
    const plan = planRequiredRoomCopy({
      sourceClassId: 10,
      gradeClassIds: [10, 11],
      requirements: [
        requirement(1, 10, SCIENCE, 50),
        requirement(2, 10, ART, 70),
        requirement(3, 11, SCIENCE, null, true),
        requirement(4, 11, ART, null),
      ],
      activeRoomIds: new Set([50]),
    });

    expect(plan.items).toEqual([]);
    expect(plan.skippedCount).toBe(2);
  });
});

describe("copyRoomsResultText", () => {
  it("says how many classes got it and how many were skipped", () => {
    expect(copyRoomsResultText(2, 0)).toBe("已複製到 2 個班級");
    expect(copyRoomsResultText(2, 1)).toBe("已複製到 2 個班級，略過 1 項（無此科目或教室已停用）");
  });
});
