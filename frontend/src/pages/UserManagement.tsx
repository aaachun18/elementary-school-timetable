import { useState, type ReactElement } from "react";
import {
  list as listUsers,
  create as createUser,
  update as updateUser,
  resetPassword,
  remove as removeUser,
} from "../api/users";
import { list as listSchools } from "../api/schools";
import { useResource } from "../hooks/useResource";
import { useCrudList } from "../hooks/useCrudList";
import type { School } from "../types/school";
import type { PasswordReset, User, UserCreate, UserUpdate } from "../types/user";
import {
  getCurrentUserRole,
  getCurrentUsername,
  ROLE_LABELS,
  type UserRole,
} from "../utils/auth";
import {
  creatableRoles,
  getMissingFieldMessage,
  needsSchoolChoice,
  toUserCreate,
} from "../utils/accountForm";
import { getPasswordRuleError } from "../utils/passwordRule";
import {
  BADGE_NEUTRAL,
  BADGE_SUCCESS,
  BUTTON_DANGER_SM,
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY_SM,
  ERROR_TEXT,
  HELP_TEXT,
  INPUT,
  LOADING_TEXT,
  MUTED_TEXT,
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

// Task 98: one row update is either a password reset (the row's "edit"
// mode, as in Task 59) or an account change (停用 / 啟用, 綁定學校) --
// both go through useCrudList's submitUpdate so they share its pending /
// error state.
type UserRowUpdate =
  | { kind: "password"; data: PasswordReset }
  | { kind: "account"; data: UserUpdate };

function UserNewRow({
  actorRole,
  schools,
  isPending,
  errorMessage,
  onConfirm,
  onCancel,
}: {
  actorRole: UserRole | null;
  schools: School[];
  isPending: boolean;
  errorMessage: string | null;
  onConfirm: (data: UserCreate) => void;
  onCancel: () => void;
}): ReactElement {
  const roles = creatableRoles(actorRole);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>(roles[0]);
  const [schoolId, setSchoolId] = useState<number | null>(null);
  const [teacherName, setTeacherName] = useState("");
  const draft = { username, password, role, schoolId, teacherName };
  // Only shown once something has been typed -- an untouched, empty field
  // just keeps 確認 disabled, same as the username field.
  const passwordRuleError = password === "" ? null : getPasswordRuleError(password);
  const missingFieldMessage = getMissingFieldMessage(draft, actorRole);

  return (
    <tr>
      <td className={TD}>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          disabled={isPending}
          aria-label="帳號名稱"
          placeholder="帳號名稱"
          className={`${INPUT} w-36`}
        />
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={isPending}
          aria-label="密碼"
          placeholder="密碼"
          autoComplete="new-password"
          className={`${INPUT} mt-1 w-36`}
        />
      </td>
      <td className={TD}>
        {roles.length === 1 ? (
          ROLE_LABELS[roles[0]]
        ) : (
          <select
            value={role}
            onChange={(event) => setRole(event.target.value as UserRole)}
            disabled={isPending}
            aria-label="角色"
            className={`${SELECT} w-full`}
          >
            {roles.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </select>
        )}
      </td>
      <td className={TD}>
        {role === "TEACHER" ? (
          <input
            value={teacherName}
            onChange={(event) => setTeacherName(event.target.value)}
            disabled={isPending}
            aria-label="教師姓名"
            placeholder="教師姓名"
            className={`${INPUT} w-full`}
          />
        ) : (
          <span className={MUTED_TEXT}>—</span>
        )}
      </td>
      {actorRole === "ADMIN" && (
        <td className={TD}>
          {needsSchoolChoice(actorRole, role) ? (
            <select
              value={schoolId ?? ""}
              onChange={(event) =>
                setSchoolId(event.target.value === "" ? null : Number(event.target.value))
              }
              disabled={isPending}
              aria-label="所屬學校"
              className={`${SELECT} w-full`}
            >
              <option value="">請選擇學校</option>
              {schools.map((school) => (
                <option key={school.id} value={school.id}>
                  {school.name}
                </option>
              ))}
            </select>
          ) : (
            <span className={MUTED_TEXT}>不屬於任何學校</span>
          )}
        </td>
      )}
      <td className={TD}>
        <span className={BADGE_SUCCESS}>啟用</span>
      </td>
      <td className={TD}>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onConfirm(toUserCreate(draft, actorRole))}
            disabled={isPending || missingFieldMessage !== null || passwordRuleError !== null}
            title={missingFieldMessage ?? undefined}
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
  isAdminActor,
  schools,
  isSelf,
  isResettingPassword,
  isPending,
  errorMessage,
  onStartResetPassword,
  onCancelResetPassword,
  onConfirmResetPassword,
  onUpdateAccount,
  onDelete,
}: {
  user: User;
  isAdminActor: boolean;
  schools: School[];
  isSelf: boolean;
  isResettingPassword: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartResetPassword: () => void;
  onCancelResetPassword: () => void;
  onConfirmResetPassword: (data: PasswordReset) => void;
  onUpdateAccount: (data: UserUpdate) => void;
  onDelete: () => void;
}): ReactElement {
  return (
    <tr className={TR_HOVER}>
      <td className={TD}>
        {user.username}
        {isSelf && <span className="ml-2 text-xs text-gray-500">（目前登入中）</span>}
      </td>
      <td className={TD}>{ROLE_LABELS[user.role]}</td>
      <td className={TD}>{user.teacher_name ?? <span className={MUTED_TEXT}>—</span>}</td>
      {isAdminActor && (
        <td className={TD}>
          {user.role === "ADMIN" ? (
            <span className={MUTED_TEXT}>不屬於任何學校</span>
          ) : (
            // 綁定學校: changing the selection saves right away.
            <select
              value={user.school_id ?? ""}
              onChange={(event) => onUpdateAccount({ school_id: Number(event.target.value) })}
              disabled={isPending}
              aria-label={`${user.username} 的所屬學校`}
              className={`${SELECT} w-full`}
            >
              {schools.map((school) => (
                <option key={school.id} value={school.id}>
                  {school.name}
                </option>
              ))}
            </select>
          )}
        </td>
      )}
      <td className={TD}>
        <span className={user.is_active ? BADGE_SUCCESS : BADGE_NEUTRAL}>
          {user.is_active ? "啟用" : "停用"}
        </span>
      </td>
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
            {/* The backend refuses deactivating / deleting one's own
                account regardless; these just don't offer a button that
                can only ever fail. */}
            <button
              type="button"
              onClick={() => onUpdateAccount({ is_active: !user.is_active })}
              disabled={isPending || isSelf}
              title={isSelf ? "不能停用目前登入中的帳號" : undefined}
              className={BUTTON_SECONDARY_SM}
            >
              {user.is_active ? "停用" : "啟用"}
            </button>
            {isAdminActor && (
              <button
                type="button"
                onClick={onDelete}
                disabled={isPending || isSelf}
                title={isSelf ? "不能刪除目前登入中的帳號" : undefined}
                className={BUTTON_DANGER_SM}
              >
                刪除
              </button>
            )}
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

// Task 59: account management, reusing useCrudList's state machine. Task
// 98: open to the 系統管理員 (every account; picks / changes schools,
// deletes) and the 教學組長 (their own school's 一般老師 accounts only --
// the backend returns nothing else to them).
export default function UserManagement(): ReactElement {
  const actorRole = getCurrentUserRole();
  const isAdminActor = actorRole === "ADMIN";
  const usersResource = useResource(() => listUsers(), []);
  // Only the 系統管理員 sees / chooses schools.
  const schoolsResource = useResource(
    () => (isAdminActor ? listSchools() : Promise.resolve<School[]>([])),
    [isAdminActor],
  );
  const currentUsername = getCurrentUsername();

  const crud = useCrudList<User, UserCreate, UserRowUpdate>(usersResource.data, {
    create: createUser,
    // Explicit types: this adapter reads `crud.items` (at click time, long
    // after `crud` exists), which TypeScript can't infer through on its own.
    update: async (id: number, change: UserRowUpdate): Promise<User> => {
      if (change.kind === "account") {
        return updateUser(id, change.data);
      }
      // The reset endpoint returns 204 with no body: a password reset
      // never changes anything this table displays.
      await resetPassword(id, change.data);
      const user: User | undefined = crud.items.find((item: User) => item.id === id);
      if (user === undefined) {
        throw new Error(`User ${id} is not in the current list`);
      }
      return user;
    },
    remove: removeUser,
  });

  if (usersResource.isLoading || schoolsResource.isLoading) {
    return (
      <div className={PAGE}>
        <p className={LOADING_TEXT}>載入中…</p>
      </div>
    );
  }
  const loadError = usersResource.errorMessage ?? schoolsResource.errorMessage;
  if (loadError !== null) {
    return (
      <div className={PAGE}>
        <p role="alert" className={ERROR_TEXT}>
          {loadError}
        </p>
      </div>
    );
  }
  const schools = schoolsResource.data ?? [];

  function handleDelete(user: User): void {
    if (window.confirm(`確定要刪除帳號「${user.username}」嗎？此操作無法復原。`)) {
      void crud.submitDelete(user.id);
    }
  }

  return (
    <div className={PAGE}>
      <h1 className={PAGE_TITLE}>帳號管理</h1>
      <p className={HELP_TEXT}>
        {isAdminActor
          ? "系統管理員可以建立教學組長與一般老師帳號，並指定所屬學校。"
          : "教學組長可以建立與停用自己學校的一般老師帳號。"}
        建立一般老師帳號時會一併建立教師資料；停用帳號後，該帳號無法登入，教師也不會出現在新的排課名單中。重設密碼後，該帳號原本已登入的連線在登入效期到期前仍然有效。
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
              <th className={TH}>教師姓名</th>
              {isAdminActor && <th className={TH}>所屬學校</th>}
              <th className={TH}>狀態</th>
              <th className={TH}>操作</th>
            </tr>
          </thead>
          <tbody>
            {crud.isAdding && (
              <UserNewRow
                actorRole={actorRole}
                schools={schools}
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
                isAdminActor={isAdminActor}
                schools={schools}
                isSelf={user.username === currentUsername}
                isResettingPassword={crud.editingId === user.id}
                isPending={crud.pendingKey === user.id}
                errorMessage={crud.rowErrors.get(user.id)}
                onStartResetPassword={() => crud.startEditing(user.id)}
                onCancelResetPassword={crud.cancelEditing}
                onConfirmResetPassword={(data) =>
                  void crud.submitUpdate(user.id, { kind: "password", data })
                }
                onUpdateAccount={(data) => void crud.submitUpdate(user.id, { kind: "account", data })}
                onDelete={() => handleDelete(user)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
