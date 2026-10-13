import { useState, type ReactElement } from "react";
import {
  list as listUsers,
  create as createUser,
  resetPassword,
  remove as removeUser,
} from "../api/users";
import { useResource } from "../hooks/useResource";
import { useCrudList } from "../hooks/useCrudList";
import type { PasswordReset, User, UserCreate } from "../types/user";
import { getCurrentUsername, type UserRole } from "../utils/auth";
import { getPasswordRuleError } from "../utils/passwordRule";
import {
  BUTTON_DANGER_SM,
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY_SM,
  ERROR_TEXT,
  HELP_TEXT,
  INPUT,
  LOADING_TEXT,
  PAGE,
  PAGE_TITLE,
  SELECT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TH,
  TR_HOVER,
} from "../styles/ui";

const ROLE_LABELS: Record<UserRole, string> = {
  ADMIN: "管理員",
  TEACHER: "教師",
};

function UserNewRow({
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: UserCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("TEACHER");
  // Only shown once something has been typed -- an untouched, empty field
  // just keeps 確認 disabled, same as the username field.
  const passwordRuleError = password === "" ? null : getPasswordRuleError(password);

  return (
    <tr>
      <td className={TD}>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          disabled={isPending}
          aria-label="帳號名稱"
          placeholder="帳號名稱"
          className={`${INPUT} w-40`}
        />
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={isPending}
          aria-label="密碼"
          placeholder="密碼"
          autoComplete="new-password"
          className={`${INPUT} ml-2 w-40`}
        />
      </td>
      <td className={TD}>
        <select
          value={role}
          onChange={(event) => setRole(event.target.value as UserRole)}
          disabled={isPending}
          aria-label="角色"
          className={SELECT}
        >
          <option value="TEACHER">{ROLE_LABELS.TEACHER}</option>
          <option value="ADMIN">{ROLE_LABELS.ADMIN}</option>
        </select>
      </td>
      <td className={TD}>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onConfirm({ username: username.trim(), password, role })}
            disabled={
              isPending || username.trim() === "" || password === "" || passwordRuleError !== null
            }
            className={BUTTON_PRIMARY_SM}
          >
            確認
          </button>
          <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
            取消
          </button>
        </div>
        {passwordRuleError !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {passwordRuleError}
          </p>
        )}
        {errorMessage !== null && (
          <p role="alert" className={ERROR_TEXT}>
            {errorMessage}
          </p>
        )}
      </td>
    </tr>
  );
}

// Rendered only while the row is in reset-password mode, so its draft
// password is discarded (unmounted) every time the form closes, rather
// than reappearing the next time it's opened.
function PasswordResetForm({
  isPending,
  onConfirm,
  onCancel,
}: {
  isPending: boolean;
  onConfirm: (data: PasswordReset) => void;
  onCancel: () => void;
}): ReactElement {
  const [newPassword, setNewPassword] = useState("");
  const passwordRuleError = newPassword === "" ? null : getPasswordRuleError(newPassword);

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          disabled={isPending}
          aria-label="新密碼"
          placeholder="新密碼"
          autoComplete="new-password"
          className={`${INPUT} w-40`}
        />
        <button
          type="button"
          onClick={() => onConfirm({ password: newPassword })}
          disabled={isPending || newPassword === "" || passwordRuleError !== null}
          className={BUTTON_PRIMARY_SM}
        >
          確認
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_SM}>
          取消
        </button>
      </div>
      {passwordRuleError !== null && (
        <p role="alert" className={ERROR_TEXT}>
          {passwordRuleError}
        </p>
      )}
    </>
  );
}

function UserRow({
  user,
  isSelf,
  isResettingPassword,
  isPending,
  errorMessage,
  onStartResetPassword,
  onCancelResetPassword,
  onConfirmResetPassword,
  onDelete,
}: {
  user: User;
  isSelf: boolean;
  isResettingPassword: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartResetPassword: () => void;
  onCancelResetPassword: () => void;
  onConfirmResetPassword: (data: PasswordReset) => void;
  onDelete: () => void;
}): ReactElement {
  return (
    <tr className={TR_HOVER}>
      <td className={TD}>
        {user.username}
        {isSelf && <span className="ml-2 text-xs text-gray-500">（目前登入中）</span>}
      </td>
      <td className={TD}>{ROLE_LABELS[user.role]}</td>
      <td className={TD}>
        {isResettingPassword ? (
          <PasswordResetForm
            isPending={isPending}
            onConfirm={onConfirmResetPassword}
            onCancel={onCancelResetPassword}
          />
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onStartResetPassword}
              disabled={isPending}
              className={BUTTON_SECONDARY_SM}
            >
              重設密碼
            </button>
            {/* The backend refuses self-deletion regardless (409); this
                just doesn't offer a button that can only ever fail. */}
            <button
              type="button"
              onClick={onDelete}
              disabled={isPending || isSelf}
              title={isSelf ? "不能刪除目前登入中的帳號" : undefined}
              className={BUTTON_DANGER_SM}
            >
              刪除
            </button>
          </div>
        )}
        {errorMessage !== undefined && (
          <p role="alert" className={ERROR_TEXT}>
            {errorMessage}
          </p>
        )}
      </td>
    </tr>
  );
}

// Task 59: ADMIN-only account management. Reuses useCrudList's state
// machine as-is: its "edit" mode is this page's "reset password" mode
// (TUpdate = PasswordReset). The reset endpoint returns 204 with no body,
// so the update adapter hands back the row unchanged -- a password reset
// never changes anything this table displays.
export default function UserManagement(): ReactElement {
  const usersResource = useResource(() => listUsers(), []);
  const currentUsername = getCurrentUsername();

  const crud = useCrudList<User, UserCreate, PasswordReset>(usersResource.data, {
    create: createUser,
    // Explicit types: this adapter reads `crud.items` (at click time, long
    // after `crud` exists), which TypeScript can't infer through on its own.
    update: async (id: number, data: PasswordReset): Promise<User> => {
      await resetPassword(id, data);
      const user: User | undefined = crud.items.find((item: User) => item.id === id);
      if (user === undefined) {
        throw new Error(`User ${id} is not in the current list`);
      }
      return user;
    },
    remove: removeUser,
  });

  if (usersResource.isLoading) {
    return (
      <div className={PAGE}>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  if (usersResource.errorMessage !== null) {
    return (
      <div className={PAGE}>
        <p role="alert" className={ERROR_TEXT}>
          {usersResource.errorMessage}
        </p>
      </div>
    );
  }

  function handleDelete(user: User): void {
    if (window.confirm(`確定要刪除帳號「${user.username}」嗎？此操作無法復原。`)) {
      void crud.submitDelete(user.id);
    }
  }

  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>帳號管理</h1>
      <p className={HELP_TEXT}>
        重設密碼後，該帳號原本已登入的連線在登入效期到期前仍然有效；刪除帳號則會立即讓該帳號無法再使用系統。
      </p>
      <p className="mb-3">
        <button
          type="button"
          onClick={crud.startAdding}
          disabled={crud.isAdding || crud.pendingKey !== null}
          className={BUTTON_PRIMARY}
        >
          新增
        </button>
      </p>
      <div className={TABLE_WRAPPER}>
        <table className={TABLE}>
          <thead>
            <tr className={TABLE_HEAD_ROW}>
              <th className={TH}>帳號名稱</th>
              <th className={TH}>角色</th>
              <th className={TH}>操作</th>
            </tr>
          </thead>
          <tbody>
            {crud.isAdding && (
              <UserNewRow
                isPending={crud.pendingKey === "new"}
                errorMessage={crud.rowErrors.get("new") ?? null}
                onConfirm={(data) => void crud.submitCreate(data)}
                onCancel={crud.cancelAdding}
              />
            )}
            {crud.items.map((user) => (
              <UserRow
                key={user.id}
                user={user}
                isSelf={user.username === currentUsername}
                isResettingPassword={crud.editingId === user.id}
                isPending={crud.pendingKey === user.id}
                errorMessage={crud.rowErrors.get(user.id)}
                onStartResetPassword={() => crud.startEditing(user.id)}
                onCancelResetPassword={crud.cancelEditing}
                onConfirmResetPassword={(data) => void crud.submitUpdate(user.id, data)}
                onDelete={() => handleDelete(user)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
