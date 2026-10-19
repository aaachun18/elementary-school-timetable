import { useState, type ReactElement } from "react";
import { ROOM_CHANGE_SCOPE_LABELS, roomChoices } from "../utils/roomChange";
import type { EnrichedSchedule } from "../hooks/useTimetableData";
import type { Room } from "../types/room";
import type { RoomChangeScope } from "../types/scheduler";
import { BUTTON_SECONDARY_SM } from "../styles/ui";

const SELECT_SM = "rounded border border-blue-300 bg-white px-1 py-0.5 text-sm";

// Task 95: 「更改教室」 in the selection bar of a selected, scheduled
// lesson: its current room, a room picker (active rooms, those of the
// requirement's type first, plus 「不指定教室」), the scope and 「預覽」.
// Mounted per lesson (keyed by the page), so the choices start over for
// every selection.
export default function RoomChangeControls({
  lesson,
  rooms,
  requiredRoomType,
  disabled,
  onPreview,
}: {
  lesson: EnrichedSchedule;
  // null while the rooms are loading.
  rooms: readonly Room[] | null;
  requiredRoomType: string | null;
  disabled: boolean;
  onPreview: (roomId: number | null, scope: RoomChangeScope) => void;
}): ReactElement {
  const [roomValue, setRoomValue] = useState(lesson.roomId === null ? "" : String(lesson.roomId));
  const [scope, setScope] = useState<RoomChangeScope>("lesson");
  const choices = roomChoices(rooms ?? [], requiredRoomType);
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span>目前教室：{lesson.roomName ?? "未指定教室"}</span>
      <label className="inline-flex items-center gap-1">
        <span>更改教室</span>
        <select
          aria-label="更改教室"
          value={roomValue}
          onChange={(event) => setRoomValue(event.target.value)}
          disabled={disabled}
          className={SELECT_SM}
        >
          <option value="">不指定教室</option>
          {choices.map((choice) => (
            <option key={choice.id} value={choice.id}>
              {choice.matchesType ? `★ ${choice.label}` : choice.label}
            </option>
          ))}
        </select>
      </label>
      <select
        aria-label="更改範圍"
        value={scope}
        onChange={(event) => setScope(event.target.value as RoomChangeScope)}
        disabled={disabled}
        className={SELECT_SM}
      >
        {(Object.keys(ROOM_CHANGE_SCOPE_LABELS) as RoomChangeScope[]).map((key) => (
          <option key={key} value={key}>
            {ROOM_CHANGE_SCOPE_LABELS[key]}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => onPreview(roomValue === "" ? null : Number(roomValue), scope)}
        disabled={disabled}
        className={BUTTON_SECONDARY_SM}
      >
        預覽
      </button>
      {rooms !== null && choices.length === 0 && (
        <span className="text-amber-800">目前沒有可用的教室，請先到基礎資料新增教室</span>
      )}
    </span>
  );
}
