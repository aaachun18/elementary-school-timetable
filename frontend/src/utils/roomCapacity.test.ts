import { describe, expect, it } from "vitest";
import { roomOverflowMessage, roomOverflows } from "./roomCapacity";

describe("roomOverflows", () => {
  it("lists only the time slots used by more classes than the room holds", () => {
    const rows = [{ timeSlotId: 5 }, { timeSlotId: 5 }, { timeSlotId: 5 }, { timeSlotId: 2 }, { timeSlotId: 2 }];

    expect(roomOverflows(rows, 2)).toEqual([{ timeSlotId: 5, count: 3 }]);
    expect(roomOverflows(rows, 1)).toEqual([
      { timeSlotId: 2, count: 2 },
      { timeSlotId: 5, count: 3 },
    ]);
  });

  it("ignores rows without a time slot", () => {
    expect(roomOverflows([{ timeSlotId: null }, { timeSlotId: null }], 1)).toEqual([]);
  });
});

describe("roomOverflowMessage", () => {
  it("names the room, the slot and both numbers", () => {
    expect(roomOverflowMessage("自然教室", "週一第 3 節", 3, 2)).toBe(
      "「自然教室」週一第 3 節有 3 個班級同時上課，超過這間教室最多 2 班同時使用的上限",
    );
  });
});
