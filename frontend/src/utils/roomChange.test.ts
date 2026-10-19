import { describe, expect, it } from "vitest";
import {
  ROOM_CHANGE_SCOPE_LABELS,
  canChangeRoom,
  describeRoomChangeLine,
  roomChangeLines,
  roomChoices,
} from "./roomChange";
import type { Room } from "../types/room";
import type { RoomChangeDetail } from "../types/scheduler";

function room(id: number, name: string, roomType: string, isActive = true): Room {
  return { id, name, room_type: roomType, capacity: null, is_active: isActive, created_at: "", updated_at: "" };
}

const ROOMS = [
  room(1, "甲班教室", "普通教室"),
  room(2, "自然教室二", "自然教室"),
  room(3, "自然教室", "專科教室"), // named like the type, typed otherwise
  room(4, "自然教室一", "自然教室"),
  room(5, "舊自然教室", "自然教室", false),
];

function change(scheduleId: number, previous: number | null, next: number | null, slot = 10): RoomChangeDetail {
  return {
    schedule_id: scheduleId,
    lesson_id: scheduleId + 100,
    teacher_id: 7,
    previous_time_slot_id: slot,
    new_time_slot_id: slot,
    previous_room_id: previous,
    new_room_id: next,
  };
}

const names = new Map(ROOMS.map((r) => [r.id, r.name]));
const roomName = (id: number | null): string | null => (id === null ? null : (names.get(id) ?? null));

describe("roomChoices", () => {
  it("puts the active rooms of exactly the requirement's type first, then the rest, each by name", () => {
    expect(roomChoices(ROOMS, "自然教室").map((c) => [c.id, c.matchesType])).toEqual([
      [4, true],
      [2, true],
      [1, false],
      [3, false],
    ]);
  });

  it("labels each room with its type", () => {
    expect(roomChoices(ROOMS, "自然教室")[3].label).toBe("自然教室（專科教室）");
  });

  it("is just the active rooms by name without a room type, and empty without rooms", () => {
    expect(roomChoices(ROOMS, null).map((c) => c.id)).toEqual([1, 3, 4, 2]);
    expect(roomChoices(ROOMS, null).every((c) => !c.matchesType)).toBe(true);
    expect(roomChoices([], "自然教室")).toEqual([]);
  });
});

describe("the preview lines", () => {
  it("says no room before as 「無」", () => {
    expect(describeRoomChangeLine("四年甲班 自然", [change(1, null, 4), change(2, null, 4)], roomName)).toBe(
      "四年甲班 自然：教室 無 → 自然教室一（2 堂）",
    );
  });

  it("names the room before, or 「多間」 for several", () => {
    expect(describeRoomChangeLine("四年甲班 自然", [change(1, 3, 4)], roomName)).toBe(
      "四年甲班 自然：教室 自然教室 → 自然教室一（1 堂）",
    );
    expect(describeRoomChangeLine("四年甲班 自然", [change(1, 3, 4), change(2, null, 4)], roomName)).toBe(
      "四年甲班 自然：教室 多間 → 自然教室一（2 堂）",
    );
  });

  it("says clearing the room as 「→ 無」", () => {
    expect(describeRoomChangeLine("四年甲班 自然", [change(1, 4, null)], roomName)).toBe(
      "四年甲班 自然：教室 自然教室一 → 無（1 堂）",
    );
  });

  it("lists each row with its slot", () => {
    expect(roomChangeLines([change(1, null, 4, 11), change(2, 3, 4, 12)], (id) => `時段 ${id}`, roomName)).toEqual([
      "時段 11：無 → 自然教室一",
      "時段 12：自然教室 → 自然教室一",
    ]);
  });
});

describe("scope labels and when the controls show", () => {
  it("has a short label per scope", () => {
    expect(ROOM_CHANGE_SCOPE_LABELS).toEqual({ lesson: "這堂課（連堂整組）", requirement: "這門課在此版本的全部節次" });
  });

  it("shows only for an ADMIN in edit mode on a DRAFT with a lesson selected", () => {
    const ok = { isAdmin: true, versionStatus: "DRAFT", isEditModeOn: true, hasSelectedLesson: true };
    expect(canChangeRoom(ok)).toBe(true);
    expect(canChangeRoom({ ...ok, isAdmin: false })).toBe(false); // a TEACHER
    expect(canChangeRoom({ ...ok, versionStatus: "PUBLISHED" })).toBe(false);
    expect(canChangeRoom({ ...ok, versionStatus: "ARCHIVED" })).toBe(false);
    expect(canChangeRoom({ ...ok, versionStatus: null })).toBe(false);
    expect(canChangeRoom({ ...ok, isEditModeOn: false })).toBe(false);
    expect(canChangeRoom({ ...ok, hasSelectedLesson: false })).toBe(false);
  });
});
