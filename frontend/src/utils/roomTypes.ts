// Task 94: a requirement's 指定教室類型 is matched against Room.room_type as
// the EXACT same string (backend H9, RoomTypeConstraint and the room
// pre-checks) -- 「自然教室」 and 「自然教室 」 or 「專科教室」 are different
// types, and a room's NAME never counts. These pure functions back the
// forms' suggestion lists and the 「找不到教室」 hints, by that same rule.

import type { Room } from "../types/room";

// Every distinct type among `rooms` (only active ones when asked), sorted
// by code point so the order never depends on the browser's locale. Types
// are kept exactly as stored -- no trimming, no case folding -- since that
// is how they are matched. Empty strings are left out.
export function roomTypeOptions(rooms: readonly Room[], { activeOnly = false } = {}): string[] {
  const types = new Set<string>();
  for (const room of rooms) {
    if ((!activeOnly || room.is_active) && room.room_type !== "") {
      types.add(room.room_type);
    }
  }
  return [...types].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

// Whether a requirement with this room type can get a room: an active room
// of exactly this type exists. No type (null / blank: 原班上課) has nothing
// to match, so it is never a problem.
export function hasActiveRoomOfType(rooms: readonly Room[], roomType: string | null): boolean {
  if (roomType === null || roomType.trim() === "") {
    return true;
  }
  return rooms.some((room) => room.is_active && room.room_type === roomType);
}

// The amber hint under the requirement form's input, or null when the
// type is blank or matches an active room.
export function roomTypeHint(rooms: readonly Room[], roomType: string | null): string | null {
  if (hasActiveRoomOfType(rooms, roomType)) {
    return null;
  }
  return `目前沒有類型為「${roomType}」的教室，排課或放入時會找不到教室（類型必須與教室的類型完全相同）`;
}
