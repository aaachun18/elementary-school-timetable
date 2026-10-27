import { useState, type ReactElement } from "react";
import ConfirmDialog from "../ConfirmDialog";
import type { SchoolCreate } from "../../types/school";
import { SCHOOL_TYPES, SCHOOL_TYPE_LABELS, type SchoolType } from "../../utils/schoolStructure";
import { ERROR_TEXT, INPUT, LABEL, SELECT } from "../../styles/ui";

// 學校管理: 「新增」 opens this dialog in the middle of the screen. Mounted
// only while adding, so every opening starts empty; it stays open with the
// error inside if saving fails.
export default function SchoolCreateDialog({
  busy,
  errorMessage,
  onSave,
  onCancel,
}: {
  busy: boolean;
  errorMessage: string | null;
  onSave: (data: SchoolCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [name, setName] = useState("");
  const [schoolType, setSchoolType] = useState<SchoolType>("ELEMENTARY");

  return (
    <ConfirmDialog
      open
      title="新增學校"
      confirmLabel="儲存"
      cancelLabel="不儲存"
      busy={busy}
      busyLabel="儲存中…"
      confirmDisabled={name.trim() === ""}
      onConfirm={() => onSave({ name: name.trim(), school_type: schoolType })}
      onCancel={onCancel}
    >
      <label className="flex flex-col gap-1">
        <span className={LABEL}>學校名稱</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={busy}
          className={`${INPUT} w-full`}
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className={LABEL}>學校類型</span>
        <select
          value={schoolType}
          onChange={(event) => setSchoolType(event.target.value as SchoolType)}
          disabled={busy}
          className={`${SELECT} w-full`}
        >
          {SCHOOL_TYPES.map((type) => (
            <option key={type} value={type}>
              {SCHOOL_TYPE_LABELS[type]}
            </option>
          ))}
        </select>
        {/* The school's grades and time slots are built from it, so it
            can't be changed later. */}
        <span className="text-xs text-gray-500">學校類型決定年級與時段，建立後無法修改。</span>
      </label>
      {errorMessage !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      )}
    </ConfirmDialog>
  );
}
