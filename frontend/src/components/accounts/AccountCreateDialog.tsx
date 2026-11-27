import { useState, type ReactElement } from "react";
import type { School } from "../../types/school";
import type { AccountCreate } from "../../types/user";
import { ROLE_LABELS, type UserRole } from "../../utils/auth";
import {
  getMissingFieldMessage,
  isValidEmail,
  needsSchoolChoice,
  needsTeacherName,
  newAccountRole,
  toAccountCreate,
} from "../../utils/accountForm";
import { USERNAME_TAKEN_MESSAGE, useUsernameTaken } from "../../hooks/useUsernameTaken";
import ConfirmDialog from "../ConfirmDialog";
import { ERROR_TEXT, INPUT, LABEL, MUTED_TEXT, SELECT } from "../../styles/ui";

// 帳號管理's 「新增帳號」 (帳號改版): the 系統管理員 creates a 教學組長
// (所屬學校 + Email), a 教學組長 an 一般老師 of their school (Email +
// 教師姓名). The account is the email; the system generates a password
// and mails both to it.
export default function AccountCreateDialog({
  actorRole,
  schools,
  busy,
  errorMessage,
  onSave,
  onCancel,
}: {
  actorRole: UserRole | null;
  schools: readonly School[];
  busy: boolean;
  errorMessage: string | null;
  onSave: (data: AccountCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [email, setEmail] = useState("");
  const [schoolId, setSchoolId] = useState<number | null>(null);
  const [teacherName, setTeacherName] = useState("");

  // Checked while typed: an email that already has an account is said
  // right under the field.
  const isEmailTaken = useUsernameTaken(isValidEmail(email) ? email.trim().toLowerCase() : "") === true;
  const draft = { email, schoolId, teacherName };
  const missingFieldMessage = getMissingFieldMessage(draft, actorRole);
  const showEmailFormatError = email.trim() !== "" && !isValidEmail(email);

  return (
    <ConfirmDialog
      open
      title={`新增${ROLE_LABELS[newAccountRole(actorRole)]}帳號`}
      confirmLabel="儲存並寄出通知信"
      busy={busy}
      busyLabel="儲存中…"
      confirmDisabled={missingFieldMessage !== null || isEmailTaken}
      onConfirm={() => onSave(toAccountCreate(draft, actorRole))}
      onCancel={onCancel}
    >
      {needsSchoolChoice(actorRole) && (
        <label className="flex flex-col gap-1">
          <span className={LABEL}>所屬學校</span>
          <select
            value={schoolId ?? ""}
            onChange={(event) => setSchoolId(event.target.value === "" ? null : Number(event.target.value))}
            disabled={busy}
            className={`${SELECT} w-full`}
          >
            <option value="">請選擇學校</option>
            {schools.map((school) => (
              <option key={school.id} value={school.id}>
                {school.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="flex flex-col gap-1">
        <span className={LABEL}>Email</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={busy}
          autoComplete="off"
          placeholder="name@example.com"
          aria-invalid={isEmailTaken || showEmailFormatError}
          className={`${INPUT} w-full`}
        />
        {showEmailFormatError && (
          <span role="alert" className={ERROR_TEXT}>
            Email 格式不正確
          </span>
        )}
        {isEmailTaken && (
          <span role="alert" className={ERROR_TEXT}>
            {USERNAME_TAKEN_MESSAGE}
          </span>
        )}
      </label>
      {needsTeacherName(actorRole) && (
        <label className="flex flex-col gap-1">
          <span className={LABEL}>教師姓名</span>
          <input
            value={teacherName}
            onChange={(event) => setTeacherName(event.target.value)}
            disabled={busy}
            className={`${INPUT} w-full`}
          />
        </label>
      )}
      <p className={MUTED_TEXT}>
        儲存後，系統會以這個 Email 作為帳號、產生 8 碼密碼，並寄送通知信到這個 Email。
      </p>
      {errorMessage !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      )}
    </ConfirmDialog>
  );
}
