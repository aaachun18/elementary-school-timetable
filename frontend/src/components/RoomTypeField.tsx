import type { ReactElement } from "react";
import { roomTypeHint } from "../utils/roomTypes";
import type { Room } from "../types/room";
import { FIELD_HINT_WARNING, SELECT } from "../styles/ui";

// The id of the page's one <datalist> of active room types (rendered by
// RequirementsOverview), shared by every row's input.
export const REQUIREMENT_ROOM_TYPE_LIST_ID = "requirement-room-type-options";

// Task 94: the requirement form's 指定教室類型 -- a free text input with
// the active rooms' types as suggestions, and an amber line under it when
// no active room has exactly this type. Never blocks saving: the room may
// be created later.
export default function RoomTypeField({
  value,
  onChange,
  disabled,
  rooms,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  // null while the rooms haven't loaded: no hint yet.
  rooms: readonly Room[] | null;
}): ReactElement {
  const hint = rooms === null ? null : roomTypeHint(rooms, value);
  return (
    <>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        aria-label="指定教室類型"
        placeholder="留空＝原班教室"
        list={REQUIREMENT_ROOM_TYPE_LIST_ID}
        className={`${SELECT} w-32`}
      />
      {hint !== null && (
        <p className={FIELD_HINT_WARNING} role="status">
          {hint}
        </p>
      )}
    </>
  );
}
