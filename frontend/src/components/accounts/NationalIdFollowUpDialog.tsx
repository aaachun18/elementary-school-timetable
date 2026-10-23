import { useState, type ReactElement } from "react";
import { setTeacherNationalId } from "../../api/users";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import type { School } from "../../types/school";
import type { SameNameTeacher } from "../../types/user";
import { getNationalIdError, normalizeNationalId } from "../../utils/accountForm";
import ConfirmDialog from "../ConfirmDialog";
import { ERROR_TEXT, HELP_TEXT, INPUT, LABEL } from "../../styles/ui";

// 帳號管理, right after a teacher account was saved with a 身分證字號
// because the name was taken: the earlier teacher of that name (one at a
// time, if several) is shown in a dialog of its own, asking for their
// 身分證字號 too. The parent mounts it with a `key` per teacher, so every
// teacher starts with an empty field.
export default function NationalIdFollowUpDialog({
  teacher,
  schools,
  remainingCount,
  onDone,
  onSkip,
}: {
  teacher: SameNameTeacher;
  schools: readonly School[];
  // Teachers still to ask after this one.
  remainingCount: number;
  onDone: () => void;
  onSkip: () => void;
}): ReactElement {
  const [nationalId, setNationalId] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formatError = nationalId === "" ? null : getNationalIdError(nationalId);
  const schoolName = schools.find((school) => school.id === teacher.school_id)?.name;

  async function handleSave(): Promise<void> {
    setIsSaving(true);
    setError(null);
    try {
      await setTeacherNationalId(teacher.teacher_id, normalizeNationalId(nationalId));
      onDone();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ConfirmDialog
      open
      title="補填同名同姓教師的身分證字號"
      confirmLabel={remainingCount > 0 ? "儲存並繼續" : "儲存"}
      cancelLabel="稍後再填"
      busy={isSaving}
      busyLabel="儲存中…"
      confirmDisabled={getNationalIdError(nationalId) !== null}
      onConfirm={() => void handleSave()}
      onCancel={onSkip}
    >
      <p className={HELP_TEXT}>新帳號已建立。為了區分同名同姓的教師，請輸入前一位同名同姓教師的身分證字號。</p>
      <dl className="grid grid-cols-[6rem_1fr] gap-x-2 gap-y-1">
        <dt className={LABEL}>教師姓名</dt>
        <dd>{teacher.teacher_name}</dd>
        <dt className={LABEL}>帳號名稱</dt>
        <dd>{teacher.username ?? "（沒有帳號）"}</dd>
        {schoolName !== undefined && (
          <>
            <dt className={LABEL}>所屬學校</dt>
            <dd>{schoolName}</dd>
          </>
        )}
      </dl>
      <label className="flex flex-col gap-1">
        <span className={LABEL}>身分證字號</span>
        <input
          value={nationalId}
          onChange={(event) => setNationalId(event.target.value)}
          disabled={isSaving}
          placeholder="例：A123456789"
          maxLength={10}
          autoComplete="off"
          className={`${INPUT} w-full`}
        />
        {formatError !== null && (
          <span role="alert" className={ERROR_TEXT}>
            {formatError}
          </span>
        )}
      </label>
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
    </ConfirmDialog>
  );
}
