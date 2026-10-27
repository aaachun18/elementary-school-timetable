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
import { deleteConfirmOptions, useConfirm } from "../hooks/useConfirm";
import type { School } from "../types/school";
import type { PasswordReset, SameNameTeacher, User, UserCreate, UserUpdate } from "../types/user";
import { getCurrentUserRole, getCurrentUsername, ROLE_LABELS } from "../utils/auth";
import { getPasswordRuleError } from "../utils/passwordRule";
import AccountCreateDialog from "../components/accounts/AccountCreateDialog";
import NationalIdEditDialog from "../components/accounts/NationalIdEditDialog";
import NationalIdFollowUpDialog from "../components/accounts/NationalIdFollowUpDialog";
import { RowErrorText } from "../components/DeleteStepsHint";
import StatusBadge from "../components/StatusBadge";
import {
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_SM,
  BUTTON_SECONDARY_SM,
  ERROR_TEXT,
  ROW_ACTIONS,
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
  deleteSteps,
  onStartResetPassword,
  onCancelResetPassword,
  onConfirmResetPassword,
  onToggleActive,
  onChangeSchool,
  onEditNationalId,
  onDelete,
}: {
  user: User;
  isAdminActor: boolean;
  schools: School[];
  isSelf: boolean;
  isResettingPassword: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  deleteSteps: readonly string[] | undefined;
  onStartResetPassword: () => void;
  onCancelResetPassword: () => void;
  onConfirmResetPassword: (data: PasswordReset) => void;
  onToggleActive: () => void;
  onChangeSchool: (schoolId: number) => void;
  // Only for an account with a teacher (一般老師).
  onEditNationalId: (() => void) | null;
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
        {user.teacher_name ?? <span className={MUTED_TEXT}>—</span>}
        {user.national_id_missing && <NationalIdMissingWarning />}
      </td>
      <td className={TD}>{user.national_id_masked ?? <span className={MUTED_TEXT}>—</span>}</td>
      {isAdminActor && (
        <td className={TD}>
          {user.role === "ADMIN" ? (
            <span className={MUTED_TEXT}>不屬於任何學校</span>
          ) : (
            // 綁定學校: changing the selection saves right away.
            <select
              value={user.school_id ?? ""}
              onChange={(event) => onChangeSchool(Number(event.target.value))}
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
        <StatusBadge tone={user.is_active ? "success" : "neutral"}>{user.is_active ? "啟用" : "停用"}</StatusBadge>
      </td>
      <td className={TD}>
        {isResettingPassword ? (
          <PasswordResetForm
            isPending={isPending}
            onConfirm={onConfirmResetPassword}
            onCancel={onCancelResetPassword}
          />
        ) : (
          <div className={ROW_ACTIONS}>
            <button
              type="button"
              onClick={onStartResetPassword}
              disabled={isPending}
              className={BUTTON_SECONDARY_SM}
            >
              重設密碼
            </button>
            {onEditNationalId !== null && (
              <button type="button" onClick={onEditNationalId} disabled={isPending} className={BUTTON_SECONDARY_SM}>
                編輯
              </button>
            )}
            {/* The backend refuses deactivating / deleting one's own
                account regardless; these just don't offer a button that
                can only ever fail. */}
            <button
              type="button"
              onClick={onToggleActive}
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
                className={BUTTON_SECONDARY_SM}
              >
                刪除
              </button>
            )}
          </div>
        )}
        {errorMessage !== undefined && <RowErrorText message={errorMessage} deleteSteps={deleteSteps} />}
      </td>
    </tr>
  );
}

// Next to a teacher's name: the school has another teacher of this name
// and this one's 身分證字號 is still missing.
function NationalIdMissingWarning(): ReactElement {
  return (
    <span
      title="有同名同姓的教師，請按「編輯」填寫身分證字號以供識別"
      className="ml-2 inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.5 align-middle text-xs font-medium text-amber-800"
    >
      <svg aria-hidden="true" viewBox="0 0 20 20" className="h-3.5 w-3.5 fill-amber-500">
        <path d="M10 2 19 18H1L10 2Zm-1 6v4h2V8H9Zm0 6v2h2v-2H9Z" />
      </svg>
      同名同姓，未填身分證字號
    </span>
  );
}

function isEditableTeacher(
  user: User,
): user is User & { teacher_id: number; teacher_name: string; school_id: number } {
  return user.teacher_id !== null && user.teacher_name !== null && user.school_id !== null;
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
  const { confirm, dialog: confirmDialog } = useConfirm();
  // After saving a teacher whose name was taken: the earlier same-name
  // teachers still without a 身分證字號, asked for one at a time.
  const [nationalIdQueue, setNationalIdQueue] = useState<SameNameTeacher[]>([]);
  // 編輯: the account whose 身分證字號 is being edited.
  const [nationalIdUser, setNationalIdUser] = useState<User | null>(null);

  // Only the first load: a reload (after 新增 / 編輯) keeps the table and
  // any open dialog on screen.
  if ((usersResource.isLoading && usersResource.data === null) || schoolsResource.isLoading) {
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

  async function handleCreate(data: UserCreate, sameNameTeachers: readonly SameNameTeacher[]): Promise<void> {
    if (await crud.submitCreate(data)) {
      setNationalIdQueue(sameNameTeachers.filter((teacher) => !teacher.has_national_id));
      // The new row's 身分證字號 column and warnings come from the backend.
      usersResource.reload();
    }
  }

  // 儲存 and 稍後再填 both move on; the list then shows who still lacks one.
  function nextNationalId(): void {
    setNationalIdQueue((queue) => queue.slice(1));
    usersResource.reload();
  }

  function skipNationalIds(): void {
    setNationalIdQueue([]);
    usersResource.reload();
  }

  async function handleStartResetPassword(user: User): Promise<void> {
    const confirmed = await confirm({
      title: "重設密碼",
      message: `確定要重設帳號「${user.username}」的密碼嗎？`,
      confirmLabel: "確定重設",
      cancelLabel: "取消",
      tone: "danger",
    });
    if (confirmed) {
      crud.startEditing(user.id);
    }
  }

  // 停用 asks first; 啟用 doesn't.
  async function handleToggleActive(user: User): Promise<void> {
    if (user.is_active) {
      const confirmed = await confirm({
        title: "停用帳號",
        message: `確定要停用帳號「${user.username}」嗎？停用後該帳號無法登入，教師也不會出現在新的排課名單中。`,
        confirmLabel: "確定停用",
        cancelLabel: "取消",
        tone: "danger",
      });
      if (!confirmed) {
        return;
      }
    }
    void crud.submitUpdate(user.id, { kind: "account", data: { is_active: !user.is_active } });
  }

  async function handleDelete(user: User): Promise<void> {
    const options = { ...deleteConfirmOptions(`帳號 ${user.username}`), confirmLabel: "確定刪除", cancelLabel: "取消" };
    if (await confirm(options)) {
      void crud.submitDelete(user.id);
    }
  }

  return (
    <div className={PAGE}>
      {confirmDialog}
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
              <th className={TH}>身分證字號</th>
              {isAdminActor && <th className={TH}>所屬學校</th>}
              <th className={TH}>狀態</th>
              <th className={TH}>操作</th>
            </tr>
          </thead>
          <tbody>
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
                deleteSteps={crud.rowDeleteSteps.get(user.id)}
                onStartResetPassword={() => void handleStartResetPassword(user)}
                onCancelResetPassword={crud.cancelEditing}
                onConfirmResetPassword={(data) =>
                  void crud.submitUpdate(user.id, { kind: "password", data })
                }
                onToggleActive={() => void handleToggleActive(user)}
                onChangeSchool={(schoolId) =>
                  void crud.submitUpdate(user.id, { kind: "account", data: { school_id: schoolId } })
                }
                onEditNationalId={user.teacher_id !== null ? () => setNationalIdUser(user) : null}
                onDelete={() => void handleDelete(user)}
              />
            ))}
          </tbody>
        </table>
      </div>
      {crud.isAdding && (
        <AccountCreateDialog
          actorRole={actorRole}
          schools={schools}
          busy={crud.pendingKey === "new"}
          errorMessage={crud.rowErrors.get("new") ?? null}
          onSave={(data, sameNameTeachers) => void handleCreate(data, sameNameTeachers)}
          onCancel={crud.cancelAdding}
        />
      )}
      {nationalIdQueue[0] !== undefined && (
        <NationalIdFollowUpDialog
          key={nationalIdQueue[0].teacher_id}
          teacher={nationalIdQueue[0]}
          schools={schools}
          remainingCount={nationalIdQueue.length - 1}
          onDone={nextNationalId}
          onSkip={skipNationalIds}
        />
      )}
      {nationalIdUser !== null && isEditableTeacher(nationalIdUser) && (
        <NationalIdEditDialog
          key={nationalIdUser.id}
          user={nationalIdUser}
          onSaved={() => {
            setNationalIdUser(null);
            usersResource.reload();
          }}
          onCancel={() => setNationalIdUser(null)}
        />
      )}
    </div>
  );
}
