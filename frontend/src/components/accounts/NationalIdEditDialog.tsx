import { useEffect, useState, type ReactElement } from "react";
import { listSameNameTeachers, setTeacherNationalId } from "../../api/users";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import type { User } from "../../types/user";
import { getNationalIdError, normalizeNationalId } from "../../utils/accountForm";
import ConfirmDialog from "../ConfirmDialog";
import { BUTTON_GHOST_SM, ERROR_TEXT, HELP_TEXT, INPUT, LABEL, NOTICE } from "../../styles/ui";

// 帳號管理 > 編輯: a teacher account's 身分證字號. Any teacher may have one;
// it may stay empty (or be cleared) unless the school has another teacher
// of the same name -- looked up when the dialog opens. The backend checks
// the same rule again.
export default function NationalIdEditDialog({
  user,
  onSaved,
  onCancel,
}: {
  // A TEACHER account with its teacher (teacher_id, teacher_name set).
  user: User & { teacher_id: number; teacher_name: string; school_id: number };
  onSaved: () => void;
  onCancel: () => void;
}): ReactElement {
  const [nationalId, setNationalId] = useState("");
  // null while looking up whether the name is shared.
  const [hasSameName, setHasSameName] = useState<boolean | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formatError = nationalId === "" ? null : getNationalIdError(nationalId);

  useEffect(() => {
    let isCurrent = true;
    listSameNameTeachers(user.teacher_name, user.school_id)
      .then((teachers) => {
        if (isCurrent) {
          setHasSameName(teachers.some((teacher) => teacher.teacher_id !== user.teacher_id));
        }
      })
      .catch((caught: unknown) => {
        if (isCurrent) {
          setError(`無法檢查同名同姓教師：${extractApiErrorMessage(caught)}`);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [user.teacher_id, user.teacher_name, user.school_id]);

  async function save(value: string | null): Promise<void> {
    setIsSaving(true);
    setError(null);
    try {
      await setTeacherNationalId(user.teacher_id, value);
      onSaved();
    } catch (caught) {
      setError(extractApiErrorMessage(caught));
      setIsSaving(false);
    }
  }

  const canClear = user.national_id_masked !== null && hasSameName === false;

  return (
    <ConfirmDialog
      open
      title="編輯身分證字號"
      confirmLabel="儲存"
      cancelLabel="不儲存"
      busy={isSaving}
      busyLabel="儲存中…"
      confirmDisabled={getNationalIdError(nationalId) !== null}
      onConfirm={() => void save(normalizeNationalId(nationalId))}
      onCancel={onCancel}
    >
      <dl className="grid grid-cols-[6rem_1fr] gap-x-2 gap-y-1">
        <dt className={LABEL}>教師姓名</dt>
        <dd>{user.teacher_name}</dd>
        <dt className={LABEL}>帳號名稱</dt>
        <dd>{user.username}</dd>
        <dt className={LABEL}>目前</dt>
        <dd>{user.national_id_masked ?? "尚未填寫"}</dd>
      </dl>
      {hasSameName === true ? (
        <p className={NOTICE}>這所學校有同名同姓的教師，這位教師必須填寫身分證字號以供識別。</p>
      ) : (
        <p className={HELP_TEXT}>沒有同名同姓的教師時，身分證字號可以不填。</p>
      )}
      <label className="flex flex-col gap-1">
        <span className={LABEL}>{user.national_id_masked === null ? "身分證字號" : "新的身分證字號"}</span>
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
      {canClear && (
        <p>
          <button type="button" onClick={() => void save(null)} disabled={isSaving} className={BUTTON_GHOST_SM}>
            清除身分證字號
          </button>
        </p>
      )}
      {error !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {error}
        </p>
      )}
    </ConfirmDialog>
  );
}
