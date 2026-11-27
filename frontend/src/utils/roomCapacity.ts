// 依教室檢視: a room may hold several classes at once (Room.max_classes; a
// class's own classroom holds one). The cells of the room's grid where more
// classes use it than that -- shown as an error above the timetable. Pure,
// no React.

export interface RoomUseRow {
  timeSlotId: number | null;
}

export interface RoomOverflow {
  timeSlotId: number;
  // How many lessons use the room in this time slot (a 共同排課 lesson is
  // one row in the room view, so it counts once -- as the backend's H3).
  count: number;
}

// `rows`: the room view's rows of this one room. In time slot id order.
export function roomOverflows(rows: readonly RoomUseRow[], maxClasses: number): RoomOverflow[] {
  const counts = new Map<number, number>();
  for (const row of rows) {
    if (row.timeSlotId !== null) {
      counts.set(row.timeSlotId, (counts.get(row.timeSlotId) ?? 0) + 1);
    }
  }
  return [...counts]
    .filter(([, count]) => count > maxClasses)
    .sort(([a], [b]) => a - b)
    .map(([timeSlotId, count]) => ({ timeSlotId, count }));
}

export function roomOverflowMessage(roomName: string, slotLabel: string, count: number, maxClasses: number): string {
  return `「${roomName}」${slotLabel}有 ${count} 個班級同時上課，超過這間教室最多 ${maxClasses} 班同時使用的上限`;
}
