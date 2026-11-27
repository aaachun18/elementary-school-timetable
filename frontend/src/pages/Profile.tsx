import { useState, type FormEvent, type ReactElement } from "react";
import { changePassword, getProfile, updateName } from "../api/me";
import ConfirmDialog from "../components/ConfirmDialog";
import { extractApiErrorMessage } from "../constants/errorMessages";
import { useFlashMessage } from "../hooks/useFlashMessage";
import { useResource } from "../hooks/useResource";
import type { Profile as ProfileData } from "../types/me";
import { getPasswordChangeError, hasEditableName, isUnassignedTeacher } from "../utils/profile";
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CARD,
  ERROR_TEXT,
  FIELD_PAGE,
  INPUT,
  LABEL,
  LOADING_TEXT,
  NOTICE,
  PAGE_CENTERED,
  PAGE_HEADER_TITLE,
  SUCCESS_TEXT,
} from "../styles/ui";

// One read-only line of the card: a label and its value.
function InfoRow({ label, value }: { label: string; value: string }): ReactElement {
  return (
    <div className="flex flex-col gap-1">
      <span className={LABEL}>{label}</span>
      <span className="text-gray-900">{value}</span>
    </div>
  );
}

// 名字: edited in place and saved with 儲存 (what timetables show).
function NameForm({ profile, onSaved }: { profile: ProfileData; onSaved: (next: ProfileData) => void }): ReactElement {
  const [name, setName] = useState(profile.name ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const saved = useFlashMessage(3000);
  const isUnchanged = name.trim() === (profile.name ?? "");

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const next = await updateName(name.trim());
      onSaved(next);
      setName(next.name ?? "");
      saved.showFlash("名字已儲存");
    } catch (caught) {
      setErrorMessage(extractApiErrorMessage(caught));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-1">
      <label htmlFor="profile-name" className={LABEL}>
        名字
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <input
          id="profile-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={isSaving}
          maxLength={100}
          className={`${INPUT} ${FIELD_PAGE}`}
        />
        <button type="submit" disabled={isSaving || name.trim() === "" || isUnchanged} className={BUTTON_PRIMARY}>
          {isSaving ? "儲存中…" : "儲存"}
        </button>
      </div>
      {saved.message !== null && (
        <p role="status" className={SUCCESS_TEXT}>
          {saved.message}
        </p>
      )}
      {errorMessage !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {errorMessage}
        </p>
      )}
    </form>
  );
}

// 重設密碼: the current password, then the new one twice.
function PasswordChangeDialog({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }): ReactElement {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const draftError = getPasswordChangeError({ currentPassword, newPassword, confirmPassword });
  // Only say what is wrong once the new password has been typed.
  const shownDraftError = newPassword === "" && confirmPassword === "" ? null : draftError;

  async function handleConfirm(): Promise<void> {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      onDone();
    } catch (caught) {
      setErrorMessage(extractApiErrorMessage(caught));
      setIsSaving(false);
    }
  }

  const fields: { id: string; label: string; value: string; onChange: (value: string) => void; autoComplete: string }[] =
    [
      {
        id: "current-password",
        label: "目前密碼",
        value: currentPassword,
        onChange: setCurrentPassword,
        autoComplete: "current-password",
      },
      { id: "new-password", label: "新密碼", value: newPassword, onChange: setNewPassword, autoComplete: "new-password" },
      {
        id: "confirm-password",
        label: "再輸入一次新密碼",
        value: confirmPassword,
        onChange: setConfirmPassword,
        autoComplete: "new-password",
      },
    ];

  return (
    <ConfirmDialog
      open
      title="重設密碼"
      confirmLabel="儲存新密碼"
      tone="primary"
      busy={isSaving}
      busyLabel="儲存中…"
      confirmDisabled={draftError !== null}
      onConfirm={() => void handleConfirm()}
      onCancel={onCancel}
    >
      {fields.map((field) => (
        <label key={field.id} htmlFor={field.id} className="flex flex-col gap-1">
          <span className={LABEL}>{field.label}</span>
          <input
            id={field.id}
            type="password"
            value={field.value}
            onChange={(event) => field.onChange(event.target.value)}
            disabled={isSaving}
            autoComplete={field.autoComplete}
            className={`${INPUT} w-full`}
          />
        </label>
      ))}
      {shownDraftError !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {shownDraftError}
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

// 帳號改版: 個人資料維護, for every role.
// - 系統管理員: 帳號名稱 and 重設密碼.
// - 教學組長 / 一般老師: 名字 (editable), Email (the account, read-only)
//   and 重設密碼. An 一般老師 with no school sees their name read-only.
export default function Profile(): ReactElement {
  const profileResource = useResource(() => getProfile(), []);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const passwordSaved = useFlashMessage(4000);
  const shown = profile ?? profileResource.data;

  if (profileResource.isLoading && shown === null) {
    return (
      <div className={PAGE_CENTERED}>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  if (profileResource.errorMessage !== null || shown === null) {
    return (
      <div className={PAGE_CENTERED}>
        <p role="alert" className={ERROR_TEXT}>
          {profileResource.errorMessage ?? "無法載入個人資料"}
        </p>
      </div>
    );
  }

  const isAdmin = shown.role === "ADMIN";

  return (
    // 第十九輪: the title and the card in the middle of the screen.
    <div className={PAGE_CENTERED}>
      <div className="w-full max-w-md pb-[10vh]">
        <h1 className={`${PAGE_HEADER_TITLE} mb-4 text-center`}>個人資料</h1>
        <div className={`${CARD} flex flex-col gap-4`}>
          {isAdmin ? (
            <InfoRow label="帳號名稱" value={shown.username} />
          ) : (
            <>
              {hasEditableName(shown) ? (
                <NameForm profile={shown} onSaved={setProfile} />
              ) : (
                <InfoRow label="名字" value={shown.name ?? "—"} />
              )}
              <InfoRow label="Email（登入帳號）" value={shown.username} />
            </>
          )}
          {isUnassignedTeacher(shown) && <p className={NOTICE}>目前無所屬學校，請聯絡系統管理員。</p>}
          <div>
            <button type="button" onClick={() => setIsChangingPassword(true)} className={BUTTON_SECONDARY}>
              重設密碼
            </button>
            {passwordSaved.message !== null && (
              <p role="status" className={`${SUCCESS_TEXT} mt-2`}>
                {passwordSaved.message}
              </p>
            )}
          </div>
        </div>
      </div>
      {isChangingPassword && (
        <PasswordChangeDialog
          onDone={() => {
            setIsChangingPassword(false);
            passwordSaved.showFlash("密碼已更新，下次請用新密碼登入");
          }}
          onCancel={() => setIsChangingPassword(false)}
        />
      )}
    </div>
  );
}
