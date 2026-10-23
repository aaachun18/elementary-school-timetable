import { useState, type ReactElement } from "react";
import { listSameNameTeachers } from "../../api/users";
import { extractApiErrorMessage } from "../../constants/errorMessages";
import type { School } from "../../types/school";
import type { SameNameTeacher, UserCreate } from "../../types/user";
import { ROLE_LABELS, type UserRole } from "../../utils/auth";
import {
  creatableRoles,
  getMissingFieldMessage,
  getNationalIdError,
  needsSchoolChoice,
  toUserCreate,
} from "../../utils/accountForm";
import { getPasswordRuleError } from "../../utils/passwordRule";
import ConfirmDialog from "../ConfirmDialog";
import { ERROR_TEXT, INPUT, LABEL, NOTICE, SELECT } from "../../styles/ui";

// 帳號管理: 「新增」 opens this dialog in the middle of the screen. For an
// 一般老師 the school's teachers are checked for the same name (when the
// name field is left, and again on 儲存); if there is one, a 身分證字號
// field appears and must be filled in before saving. `onSave` gets the
// same-name teachers too, so the page can then ask for theirs.
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
  onSave: (data: UserCreate, sameNameTeachers: readonly SameNameTeacher[]) => void;
  onCancel: () => void;
}): ReactElement {
  const roles = creatableRoles(actorRole);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>(roles[0]);
  const [schoolId, setSchoolId] = useState<number | null>(null);
  const [teacherName, setTeacherName] = useState("");
  const [nationalId, setNationalId] = useState("");
  // null = not checked yet for the current name and school.
  const [sameNameTeachers, setSameNameTeachers] = useState<SameNameTeacher[] | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  // Set when 儲存 found a same-name teacher and the 身分證字號 is still empty.
  const [showNationalIdError, setShowNationalIdError] = useState(false);

  const draft = { username, password, role, schoolId, teacherName, nationalId };
  const passwordRuleError = password === "" ? null : getPasswordRuleError(password);
  const missingFieldMessage = getMissingFieldMessage(draft, actorRole);
  const needsNationalId = role === "TEACHER" && (sameNameTeachers?.length ?? 0) > 0;
  const nationalIdError = needsNationalId ? getNationalIdError(nationalId) : null;

  function canCheck(): boolean {
    return (
      role === "TEACHER" && teacherName.trim() !== "" && (!needsSchoolChoice(actorRole, role) || schoolId !== null)
    );
  }

  async function checkSameName(): Promise<SameNameTeacher[] | null> {
    if (!canCheck()) {
      return [];
    }
    setIsChecking(true);
    setCheckError(null);
    try {
      const found = await listSameNameTeachers(
        teacherName.trim(),
        needsSchoolChoice(actorRole, role) ? schoolId : null,
      );
      setSameNameTeachers(found);
      return found;
    } catch (caught) {
      setCheckError(extractApiErrorMessage(caught));
      return null;
    } finally {
      setIsChecking(false);
    }
  }

  async function handleSave(): Promise<void> {
    const found = sameNameTeachers ?? (await checkSameName());
    if (found === null) {
      return;
    }
    if (role === "TEACHER" && found.length > 0 && getNationalIdError(nationalId) !== null) {
      setShowNationalIdError(true);
      return;
    }
    onSave(toUserCreate(draft, actorRole), role === "TEACHER" ? found : []);
  }

  // A changed name or school has to be checked again.
  function resetCheck(): void {
    setSameNameTeachers(null);
    setShowNationalIdError(false);
  }

  return (
    <ConfirmDialog
      open
      title="新增帳號"
      confirmLabel="儲存"
      busy={busy || isChecking}
      busyLabel={isChecking ? "檢查中…" : "儲存中…"}
      confirmDisabled={missingFieldMessage !== null || passwordRuleError !== null}
      onConfirm={() => void handleSave()}
      onCancel={onCancel}
    >
      <label className="flex flex-col gap-1">
        <span className={LABEL}>帳號名稱</span>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          disabled={busy}
          className={`${INPUT} w-full`}
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className={LABEL}>密碼</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={busy}
          autoComplete="new-password"
          className={`${INPUT} w-full`}
        />
        {passwordRuleError !== null && (
          <span role="alert" className={ERROR_TEXT}>
            {passwordRuleError}
          </span>
        )}
      </label>
      <label className="flex flex-col gap-1">
        <span className={LABEL}>角色</span>
        {roles.length === 1 ? (
          <span>{ROLE_LABELS[roles[0]]}</span>
        ) : (
          <select
            value={role}
            onChange={(event) => {
              setRole(event.target.value as UserRole);
              resetCheck();
            }}
            disabled={busy}
            className={`${SELECT} w-full`}
          >
            {roles.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </select>
        )}
      </label>
      {needsSchoolChoice(actorRole, role) && (
        <label className="flex flex-col gap-1">
          <span className={LABEL}>所屬學校</span>
          <select
            value={schoolId ?? ""}
            onChange={(event) => {
              setSchoolId(event.target.value === "" ? null : Number(event.target.value));
              resetCheck();
            }}
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
      {role === "TEACHER" && (
        <label className="flex flex-col gap-1">
          <span className={LABEL}>教師姓名</span>
          <input
            value={teacherName}
            onChange={(event) => {
              setTeacherName(event.target.value);
              resetCheck();
            }}
            onBlur={() => {
              if (sameNameTeachers === null) {
                void checkSameName();
              }
            }}
            disabled={busy}
            className={`${INPUT} w-full`}
          />
        </label>
      )}
      {needsNationalId && sameNameTeachers !== null && (
        <>
          <p className={NOTICE}>
            這所學校已有 {sameNameTeachers.length} 位同名同姓的教師（
            {sameNameTeachers.map((teacher) => teacher.username ?? "沒有帳號").join("、")}
            ），請輸入這位新教師的身分證字號以供識別。
          </p>
          <label className="flex flex-col gap-1">
            <span className={LABEL}>身分證字號</span>
            <input
              value={nationalId}
              onChange={(event) => setNationalId(event.target.value)}
              disabled={busy}
              placeholder="例：A123456789"
              maxLength={10}
              autoComplete="off"
              className={`${INPUT} w-full`}
            />
            {(showNationalIdError || nationalId !== "") && nationalIdError !== null && (
              <span role="alert" className={ERROR_TEXT}>
                {nationalIdError}
              </span>
            )}
          </label>
        </>
      )}
      {checkError !== null && (
        <p role="alert" className={ERROR_TEXT}>
          無法檢查同名同姓教師：{checkError}
        </p>
      )}
      {errorMessage !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      )}
    </ConfirmDialog>
  );
}
