import { useState, type ReactElement } from "react";
import ConfirmDialog from "../ConfirmDialog";
import { ERROR_TEXT, INPUT, LABEL } from "../../styles/ui";

// 學校資料 > 科目 / 教室: 「新增」 opens this dialog in the middle of the
// screen -- just the name -- and 儲存 adds the row to the list. Mounted only
// while adding, so every opening starts with an empty name; it stays open
// with the error inside if saving fails.
export default function NameCreateDialog({
  title,
  label,
  placeholder,
  busy,
  errorMessage,
  onSave,
  onCancel,
}: {
  title: string;
  label: string;
  placeholder?: string;
  busy: boolean;
  errorMessage: string | null;
  onSave: (name: string) => void;
  onCancel: () => void;
}): ReactElement {
  const [name, setName] = useState("");

  return (
    <ConfirmDialog
      open
      title={title}
      confirmLabel="儲存"
      busy={busy}
      busyLabel="儲存中…"
      confirmDisabled={name.trim() === ""}
      onConfirm={() => onSave(name.trim())}
      onCancel={onCancel}
    >
      <label className="flex flex-col gap-1">
        <span className={LABEL}>{label}</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={busy}
          aria-label={label}
          placeholder={placeholder}
          className={INPUT}
        />
      </label>
      {errorMessage !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      )}
    </ConfirmDialog>
  );
}
