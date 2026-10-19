import { describe, expect, it } from "vitest";
import { hasActiveRoomOfType, roomTypeHint, roomTypeOptions } from "./roomTypes";
import type { Room } from "../types/room";

function room(id: number, roomType: string, isActive = true, name = `教室 ${id}`): Room {
  return { id, name, room_type: roomType, capacity: null, is_active: isActive, created_at: "", updated_at: "" } as Room;
}

const ROOMS = [
  room(1, "音樂教室"),
  room(2, "自然教室"),
  room(3, "自然教室"),
  room(4, "專科教室", true, "自然教室"), // named like a type, typed otherwise
  room(5, "電腦教室", false),
  room(6, "自然教室 "),
  room(7, "Lab"),
  room(8, "lab"),
  room(9, ""),
];

describe("roomTypeOptions", () => {
  it("lists each type once, sorted, exactly as stored", () => {
    expect(roomTypeOptions(ROOMS)).toEqual(["Lab", "lab", "專科教室", "自然教室", "自然教室 ", "電腦教室", "音樂教室"]);
  });

  it("can list active rooms only", () => {
    expect(roomTypeOptions(ROOMS, { activeOnly: true })).not.toContain("電腦教室");
    expect(roomTypeOptions(ROOMS, { activeOnly: true })).toHaveLength(6);
  });

  it("is empty without rooms", () => {
    expect(roomTypeOptions([])).toEqual([]);
  });
});

describe("hasActiveRoomOfType / roomTypeHint", () => {
  it("matches an active room of exactly the type", () => {
    expect(hasActiveRoomOfType(ROOMS, "自然教室")).toBe(true);
    expect(roomTypeHint(ROOMS, "自然教室")).toBeNull();
  });

  it("never matches a room's name, another case or extra spaces", () => {
    expect(hasActiveRoomOfType([room(4, "專科教室", true, "自然教室")], "自然教室")).toBe(false);
    expect(hasActiveRoomOfType([room(7, "Lab")], "lab")).toBe(false);
    expect(hasActiveRoomOfType([room(2, "自然教室")], " 自然教室")).toBe(false);
  });

  it("only counts active rooms", () => {
    expect(hasActiveRoomOfType(ROOMS, "電腦教室")).toBe(false);
    expect(roomTypeHint(ROOMS, "電腦教室")).toBe(
      "目前沒有類型為「電腦教室」的教室，排課或放入時會找不到教室（類型必須與教室的類型完全相同）",
    );
  });

  it("has nothing to say about no type (原班上課)", () => {
    expect(hasActiveRoomOfType([], null)).toBe(true);
    expect(hasActiveRoomOfType([], "")).toBe(true);
    expect(hasActiveRoomOfType([], "   ")).toBe(true);
    expect(roomTypeHint([], null)).toBeNull();
    expect(roomTypeHint([], "")).toBeNull();
  });

  it("warns about a type no room has", () => {
    expect(roomTypeHint([], "自然教室")).toContain("「自然教室」");
  });
});
