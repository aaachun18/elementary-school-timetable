// Task 95: changing the room of a scheduled lesson from the timetable's
// edit mode (backend change-room, decision 32) -- the room choices, the
// scope labels and the preview's lines. Pure functions, no React.

import type { Room } from "../types/room";
import type { RoomChangeDetail, RoomChangeScope } from "../types/scheduler";

export const ROOM_CHANGE_SCOPE_LABELS: Record<RoomChangeScope, string> = {
  lesson: "這堂課（連堂整組）",
  requirement: "這門課在此版本的全部節次",
};

export interface RoomChoice {
  id: number;
  label: string;
  // Task 98: the requirement's own special room.
  isRequired: boolean;
}

function byName(a: Room, b: Room): number {
  return a.name < b.name ? -1 : a.name > b.name ? 1 : a.id - b.id;
}

// Active rooms only, the requirement's own special room first, then the
// rest by name (Task 98: rooms have no types any more).
export function roomChoices(rooms: readonly Room[], requiredRoomId: number | null): RoomChoice[] {
  const active = rooms.filter((room) => room.is_active);
  const isRequired = (room: Room): boolean => room.id === requiredRoomId;
  return [...active.filter(isRequired), ...active.filter((room) => !isRequired(room)).sort(byName)].map(
    (room) => ({ id: room.id, label: room.name, isRequired: isRequired(room) }),
  );
}

// 「四年甲班 自然：教室 無 → 自然教室一（2 堂）」. Several different rooms
// before the change read 「多間」.
export function describeRoomChangeLine(
  courseName: string,
  changes: readonly RoomChangeDetail[],
  roomName: (roomId: number | null) => string | null,
): string {
  const previous = new Set(changes.map((change) => change.previous_room_id));
  const from = previous.size > 1 ? "多間" : (roomName([...previous][0] ?? null) ?? "無");
  const to = roomName(changes[0]?.new_room_id ?? null) ?? "無";
  return `${courseName}：教室 ${from} → ${to}（${changes.length} 堂）`;
}

// One line per changed row: 「星期一第 2 節：無 → 自然教室一」.
export function roomChangeLines(
  changes: readonly RoomChangeDetail[],
  slotLabel: (timeSlotId: number | null) => string,
  roomName: (roomId: number | null) => string | null,
): string[] {
  return changes.map(
    (change) =>
      `${slotLabel(change.new_time_slot_id)}：${roomName(change.previous_room_id) ?? "無"} → ${
        roomName(change.new_room_id) ?? "無"
      }`,
  );
}

// The 「更改教室」 controls: an ADMIN, in edit mode, on a DRAFT, with a
// scheduled lesson selected.
export function canChangeRoom(state: {
  isAdmin: boolean;
  versionStatus: string | null;
  isEditModeOn: boolean;
  hasSelectedLesson: boolean;
}): boolean {
  return state.isAdmin && state.versionStatus === "DRAFT" && state.isEditModeOn && state.hasSelectedLesson;
}
