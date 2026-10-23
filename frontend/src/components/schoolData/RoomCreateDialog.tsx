import { useState, type ReactElement } from "react";
import ConfirmDialog from "../ConfirmDialog";
import { ROOM_MAX_CLASSES_OPTIONS, type RoomCreate } from "../../types/room";
import { ERROR_TEXT, INPUT, LABEL, SELECT } from "../../styles/ui";

// 學校資料 > 教室: 「新增」's dialog -- the room's name and how many classes
// may use it at the same time (1-10). Mounted only while adding, like
// NameCreateDialog.
export default function RoomCreateDialog({
  busy,
  errorMessage,
  onSave,
  onCancel,
}: {
  busy: boolean;
  errorMessage: string | null;
  onSave: (data: RoomCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [name, setName] = useState("");
  const [maxClasses, setMaxClasses] = useState(1);

  return (
    <ConfirmDialog
      open
      title="新增教室"
      confirmLabel="儲存"
      busy={busy}
      busyLabel="儲存中…"
      confirmDisabled={name.trim() === ""}
      onConfirm={() => onSave({ name: name.trim(), max_classes: maxClasses })}
      onCancel={onCancel}
    >
      <label className="flex flex-col gap-1">
        <span className={LABEL}>教室名稱</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={busy}
          aria-label="教室名稱"
          placeholder="這間教室自己的名字"
          className={`${INPUT} w-full`}
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className={LABEL}>一次最多幾個班級同時使用</span>
        <select
          value={maxClasses}
          onChange={(event) => setMaxClasses(Number(event.target.value))}
          disabled={busy}
          aria-label="一次最多幾個班級同時使用"
          className={`${SELECT} w-full`}
        >
          {ROOM_MAX_CLASSES_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option} 班
            </option>
          ))}
        </select>
      </label>
      {errorMessage !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      )}
    </ConfirmDialog>
  );
}
