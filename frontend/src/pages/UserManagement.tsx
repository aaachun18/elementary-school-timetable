import { useState, type FormEvent, type ReactElement } from "react";
import {
  list as listUsers,
  createAccount,
  update as updateUser,
  resetPassword,
  leaveSchool,
  deactivationImpact as userDeactivationImpact,
} from "../api/users";
import { list as listSchools } from "../api/schools";
import { useResource } from "../hooks/useResource";
import { useCrudList } from "../hooks/useCrudList";
import { useConfirm } from "../hooks/useConfirm";
import { usePagination } from "../hooks/usePagination";
import Pagination from "../components/Pagination";
import ConfirmDialog from "../components/ConfirmDialog";
import DeactivateConfirmDialog from "../components/DeactivateConfirmDialog";
import { CANCEL_LABEL } from "../utils/confirmText";
import type { School } from "../types/school";
import type { AccountCreate, AccountCreated, PasswordReset, User, UserUpdate } from "../types/user";
import { getCurrentUserRole, ROLE_LABELS } from "../utils/auth";
import { getPasswordRuleError } from "../utils/passwordRule";
import AccountCreateDialog from "../components/accounts/AccountCreateDialog";
import { RowErrorText } from "../components/DeleteStepsHint";
import StatusBadge from "../components/StatusBadge";
import PageHeader from "../components/PageHeader";
import { SearchIcon, XIcon } from "../components/icons";
import {
  ACCOUNT_FILTER_OPTIONS,
  accountFilterLabel,
  filterAccounts,
  searchResultText,
  serialNumber,
  sortAccounts,
  type AccountFilter,
} from "../utils/accountList";
import { PAGE_SIZE } from "../utils/pagination";
import {
  BUTTON_PRIMARY,
  BUTTON_PRIMARY_ROW,
  BUTTON_SECONDARY_ROW,
  BUTTON_GHOST_SM,
  ERROR_TEXT,
  ROW_ACTIONS_END,
  INPUT,
  LOADING_TEXT,
  MUTED_TEXT,
  NOTICE,
  PAGE,
  SELECT,
  TABLE,
  TABLE_HEAD_ROW,
  TABLE_WRAPPER,
  TD,
  TD_ACTIONS,
  TD_NOWRAP,
  TH,
  TH_ACTIONS,
  TR_HOVER,
} from "../styles/ui";

// One row update: a password reset (the row's "edit" mode), an account
// change by the 系統管理員 (停用 / 啟用, 所屬學校) or a 教學組長's 離校 --
// all through useCrudList's submitUpdate so they share its pending / error
// state.
type UserRowUpdate =
  | { kind: "password"; data: PasswordReset }
  | { kind: "account"; data: UserUpdate }
  | { kind: "leave" };

// Rendered only while the row is in reset-password mode, so its draft
// password is discarded (unmounted) every time the form closes.
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
      <div className={ROW_ACTIONS_END}>
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
          className={BUTTON_PRIMARY_ROW}
        >
          確認
        </button>
        <button type="button" onClick={onCancel} disabled={isPending} className={BUTTON_SECONDARY_ROW}>
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

// 系統管理員's 所屬學校 cell: changing the selection asks first, then saves.
// An 一般老師 with no school shows 「無所屬學校」 until one is picked.
function SchoolSelect({
  user,
  schools,
  isPending,
  onChange,
}: {
  user: User;
  schools: readonly School[];
  isPending: boolean;
  onChange: (schoolId: number) => void;
}): ReactElement {
  return (
    <select
      value={user.school_id ?? ""}
      onChange={(event) => {
        if (event.target.value !== "") {
          onChange(Number(event.target.value));
        }
      }}
      disabled={isPending}
      aria-label={`${user.username} 的所屬學校`}
      className={`${SELECT} w-full`}
    >
      {user.school_id === null && <option value="">無所屬學校（請選擇）</option>}
      {schools.map((school) => (
        <option key={school.id} value={school.id}>
          {school.name}
        </option>
      ))}
    </select>
  );
}

function UserRow({
  serial,
  user,
  isAdminActor,
  schools,
  isResettingPassword,
  isPending,
  errorMessage,
  onStartResetPassword,
  onCancelResetPassword,
  onConfirmResetPassword,
  onToggleActive,
  onChangeSchool,
  onLeaveSchool,
}: {
  // 序號: the row's place in the (sorted, searched) list, across pages.
  serial: number;
  user: User;
  isAdminActor: boolean;
  schools: readonly School[];
  isResettingPassword: boolean;
  isPending: boolean;
  errorMessage: string | undefined;
  onStartResetPassword: () => void;
  onCancelResetPassword: () => void;
  onConfirmResetPassword: (data: PasswordReset) => void;
  onToggleActive: () => void;
  onChangeSchool: (schoolId: number) => void;
  onLeaveSchool: () => void;
}): ReactElement {
  return (
    <tr className={TR_HOVER}>
      <td className={`${TD_NOWRAP} text-right text-gray-500`}>{serial}</td>
      <td className={TD}>{user.username}</td>
      {isAdminActor && <td className={TD}>{ROLE_LABELS[user.role]}</td>}
      <td className={TD}>{user.teacher_name ?? <span className={MUTED_TEXT}>—</span>}</td>
      {isAdminActor && (
        <td className={TD}>
          <SchoolSelect user={user} schools={schools} isPending={isPending} onChange={onChangeSchool} />
        </td>
      )}
      <td className={TD_NOWRAP}>
        <StatusBadge tone={user.is_active ? "success" : "neutral"}>{user.is_active ? "啟用" : "停用"}</StatusBadge>
      </td>
      <td className={TD_ACTIONS}>
        {isResettingPassword ? (
          <PasswordResetForm
            isPending={isPending}
            onConfirm={onConfirmResetPassword}
            onCancel={onCancelResetPassword}
          />
        ) : (
          <div className={ROW_ACTIONS_END}>
            <button type="button" onClick={onStartResetPassword} disabled={isPending} className={BUTTON_SECONDARY_ROW}>
              重設密碼
            </button>
            {/* 帳號改版: 停用 / 啟用 is the 系統管理員's; a 教學組長 has 離校
                instead. No account is ever deleted. */}
            {isAdminActor ? (
              <button type="button" onClick={onToggleActive} disabled={isPending} className={BUTTON_SECONDARY_ROW}>
                {user.is_active ? "停用" : "啟用"}
              </button>
            ) : (
              <button type="button" onClick={onLeaveSchool} disabled={isPending} className={BUTTON_SECONDARY_ROW}>
                離校
              </button>
            )}
          </div>
        )}
        {errorMessage !== undefined && <RowErrorText message={errorMessage} />}
      </td>
    </tr>
  );
}

// After 新增帳號: the mail went out, or (mail failed) the password to pass on.
function AccountCreatedDialog({ created, onClose }: { created: AccountCreated; onClose: () => void }): ReactElement {
  return (
    <ConfirmDialog
      open
      title={created.email_sent ? "帳號已建立，已寄出通知信" : "帳號已建立，但通知信寄送失敗"}
      showConfirm={false}
      cancelLabel="完成"
      onConfirm={onClose}
      onCancel={onClose}
    >
      <p>帳號：{created.user.username}</p>
      {created.email_sent ? (
        <p>帳號與系統產生的密碼已寄到這個 Email，對方可以登入後到「個人資料」修改密碼。</p>
      ) : (
        <>
          <p>密碼：{created.initial_password}</p>
          <p className={NOTICE}>這個密碼只會顯示這一次，請自行告知對方，並提醒登入後到「個人資料」修改密碼。</p>
        </>
      )}
    </ConfirmDialog>
  );
}

// Account management, reusing useCrudList's state machine. Open to the
// 系統管理員 (every 教學組長 / 一般老師 account, never 系統管理員 ones;
// creates 教學組長, 停用 / 啟用, 所屬學校) and the 教學組長 (their own
// school's 一般老師 accounts only; creates them, 離校). Both may 重設密碼.
export default function UserManagement(): ReactElement {
  const actorRole = getCurrentUserRole();
  const isAdminActor = actorRole === "ADMIN";
  // 搜尋帳號: what is typed, and the search the list shows (null = every
  // account). Only the magnifier (or Enter) applies what was typed;
  // ✕ / 「顯示全部」 -- or searching for nothing -- shows every account again.
  const [searchText, setSearchText] = useState("");
  const [appliedSearch, setAppliedSearch] = useState<string | null>(null);
  const usersResource = useResource(() => listUsers(appliedSearch), [appliedSearch]);
  // 系統管理員 only: one group's accounts, shown as soon as it is picked.
  const [accountFilter, setAccountFilter] = useState<AccountFilter>("ALL");
  // Only the 系統管理員 sees / chooses schools.
  const schoolsResource = useResource(
    () => (isAdminActor ? listSchools() : Promise.resolve<School[]>([])),
    [isAdminActor],
  );
  // What the last 新增帳號 returned (mail sent, or the password to pass on).
  const [created, setCreated] = useState<AccountCreated | null>(null);

  const crud = useCrudList<User, AccountCreate, UserRowUpdate>(usersResource.data, {
    create: async (data: AccountCreate): Promise<User> => {
      const result = await createAccount(data);
      setCreated(result);
      return result.user;
    },
    // Explicit types: this adapter reads `crud.items` (at click time, long
    // after `crud` exists), which TypeScript can't infer through on its own.
    update: async (id: number, change: UserRowUpdate): Promise<User> => {
      if (change.kind === "account") {
        const updated = await updateUser(id, change.data);
        if (change.data.school_id !== undefined) {
          // A move changes the account's teacher row (teacher_id).
          usersResource.reload();
        }
        return updated;
      }
      if (change.kind === "leave") {
        const left = await leaveSchool(id);
        // The account is no longer this school's: it leaves the list.
        usersResource.reload();
        return left;
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
    remove: () => Promise.reject(new Error("帳號不能刪除")),
  });
  const shownFilter: AccountFilter = isAdminActor ? accountFilter : "ALL";
  const sortedUsers = sortAccounts(filterAccounts(crud.items, shownFilter));
  const isFiltered = appliedSearch !== null || shownFilter !== "ALL";
  const pagination = usePagination(sortedUsers);
  const { confirm, dialog: confirmDialog } = useConfirm();
  const [deactivating, setDeactivating] = useState<User | null>(null);

  // Only the first load: a reload keeps the table and any open dialog.
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

  function applySearch(next: string | null): void {
    const trimmed = next?.trim() ?? "";
    setAppliedSearch(trimmed === "" ? null : trimmed);
    pagination.setPage(1);
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    applySearch(searchText);
  }

  function clearSearch(): void {
    setSearchText("");
    applySearch(null);
  }

  function handleFilterChange(next: AccountFilter): void {
    setAccountFilter(next);
    pagination.setPage(1);
  }

  // 「顯示全部」: no search and every account.
  function showAll(): void {
    clearSearch();
    setAccountFilter("ALL");
  }

  async function handleCreate(data: AccountCreate): Promise<void> {
    if (await crud.submitCreate(data)) {
      usersResource.reload();
    }
  }

  async function handleStartResetPassword(user: User): Promise<void> {
    const confirmed = await confirm({
      title: `重設「${user.username}」的密碼？`,
      message: "接著會請你輸入新密碼；儲存後，這個帳號要用新密碼登入。",
      confirmLabel: "重設密碼",
      cancelLabel: CANCEL_LABEL,
      tone: "danger",
    });
    if (confirmed) {
      crud.startEditing(user.id);
    }
  }

  // 停用 asks first (DeactivateConfirmDialog, with what it touches); 啟用
  // doesn't.
  function handleToggleActive(user: User): void {
    if (user.is_active) {
      setDeactivating(user);
      return;
    }
    void crud.submitUpdate(user.id, { kind: "account", data: { is_active: true } });
  }

  // Assigning an 一般老師 with no school just saves; moving an account
  // that has a school asks first.
  async function handleChangeSchool(user: User, schoolId: number): Promise<void> {
    if (user.school_id !== null) {
      const schoolName = schools.find((school) => school.id === schoolId)?.name ?? "";
      const confirmed = await confirm({
        title: `把「${user.username}」改到「${schoolName}」？`,
        message: "原學校的教師資料會保留在舊課表中，但不會再出現在原學校的新排課名單。",
        confirmLabel: "變更學校",
        cancelLabel: CANCEL_LABEL,
        tone: "primary",
      });
      if (!confirmed) {
        return;
      }
    }
    await crud.submitUpdate(user.id, { kind: "account", data: { school_id: schoolId } });
  }

  // 離校: the 一般老師 becomes 無所屬學校 and leaves this list.
  async function handleLeaveSchool(user: User): Promise<void> {
    const confirmed = await confirm({
      title: `「${user.teacher_name ?? user.username}」要離校嗎？`,
      message:
        "離校後，已排好的課表仍會保留這位老師，但不會再出現在本校的新排課名單中。",
      confirmLabel: "離校",
      cancelLabel: CANCEL_LABEL,
      tone: "danger",
    });
    if (confirmed) {
      await crud.submitUpdate(user.id, { kind: "leave" });
    }
  }

  return (
    <div className={PAGE}>
      {confirmDialog}
      {deactivating !== null && (
        <DeactivateConfirmDialog
          kind="account"
          name={deactivating.username}
          loadImpact={() => userDeactivationImpact(deactivating.id)}
          onConfirm={() => {
            const user = deactivating;
            setDeactivating(null);
            void crud.submitUpdate(user.id, { kind: "account", data: { is_active: false } });
          }}
          onCancel={() => setDeactivating(null)}
        />
      )}
      {created !== null && <AccountCreatedDialog created={created} onClose={() => setCreated(null)} />}
      <PageHeader
        title="帳號管理"
        info={
          isAdminActor ? (
            <p>
              系統管理員可以建立教學組長帳號（填寫所屬學校與 Email），系統會產生 8
              碼密碼並寄送通知信。也可以停用或啟用帳號、重設密碼，以及變更所屬學校——「無所屬學校」的老師是被教學組長設為離校、等待分配的老師。
            </p>
          ) : (
            <p>
              教學組長可以建立自己學校的一般老師帳號（填寫 Email 與教師姓名），系統會產生 8
              碼密碼並寄送通知信。老師離開本校時請按「離校」，該老師會交由系統管理員分配；已排好的課表不受影響。重設密碼後，該帳號原本已登入的連線在登入效期到期前仍然有效。
            </p>
          )
        }
        actions={
          <button
            type="button"
            onClick={crud.startAdding}
            disabled={crud.isAdding || crud.pendingKey !== null}
            className={BUTTON_PRIMARY}
          >
            新增帳號
          </button>
        }
      />
      <form role="search" onSubmit={handleSearchSubmit} className="mb-2 flex flex-wrap items-center gap-2">
        {isAdminActor && (
          <select
            value={accountFilter}
            onChange={(event) => handleFilterChange(event.target.value as AccountFilter)}
            aria-label="篩選帳號"
            className={SELECT}
          >
            {ACCOUNT_FILTER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
        <div className="relative w-72 max-w-full">
          <input
            type="search"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            aria-label="搜尋帳號"
            placeholder="搜尋 Email 或姓名"
            className={`${INPUT} w-full pr-16 [&::-webkit-search-cancel-button]:hidden`}
          />
          {(searchText !== "" || appliedSearch !== null) && (
            <button
              type="button"
              onClick={clearSearch}
              aria-label="清除搜尋"
              title="清除搜尋，顯示全部帳號"
              className="absolute right-8 top-1/2 -translate-y-1/2 rounded p-0.5 text-gray-400 hover:text-gray-700"
            >
              <XIcon size={16} />
            </button>
          )}
          <button
            type="submit"
            aria-label="搜尋"
            title="搜尋"
            className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-primary"
          >
            <SearchIcon size={18} />
          </button>
        </div>
        {usersResource.isLoading && <span className={MUTED_TEXT}>搜尋中…</span>}
      </form>
      {isFiltered && (
        <p className="mb-3 flex flex-wrap items-center gap-2 text-sm text-gray-700" role="status">
          {searchResultText(
            appliedSearch,
            shownFilter === "ALL" ? null : accountFilterLabel(shownFilter),
            sortedUsers.length,
          )}
          <button type="button" onClick={showAll} className={BUTTON_GHOST_SM}>
            顯示全部
          </button>
        </p>
      )}
      <div className={TABLE_WRAPPER}>
        <table className={TABLE}>
          <thead>
            <tr className={TABLE_HEAD_ROW}>
              <th className={`${TH} w-14 text-right`}>序號</th>
              <th className={TH}>帳號（Email）</th>
              {isAdminActor && <th className={TH}>角色</th>}
              <th className={TH}>姓名</th>
              {isAdminActor && <th className={TH}>所屬學校</th>}
              <th className={TH}>狀態</th>
              <th className={TH_ACTIONS}>操作</th>
            </tr>
          </thead>
          <tbody>
            {pagination.pageItems.map((user, index) => (
              <UserRow
                key={user.id}
                serial={serialNumber(pagination.page, PAGE_SIZE, index)}
                user={user}
                isAdminActor={isAdminActor}
                schools={schools}
                isResettingPassword={crud.editingId === user.id}
                isPending={crud.pendingKey === user.id}
                errorMessage={crud.rowErrors.get(user.id)}
                onStartResetPassword={() => void handleStartResetPassword(user)}
                onCancelResetPassword={crud.cancelEditing}
                onConfirmResetPassword={(data) => void crud.submitUpdate(user.id, { kind: "password", data })}
                onToggleActive={() => handleToggleActive(user)}
                onChangeSchool={(schoolId) => void handleChangeSchool(user, schoolId)}
                onLeaveSchool={() => void handleLeaveSchool(user)}
              />
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={pagination.page} totalItems={pagination.totalItems} onPageChange={pagination.setPage} />
      {crud.isAdding && (
        <AccountCreateDialog
          actorRole={actorRole}
          schools={schools}
          busy={crud.pendingKey === "new"}
          errorMessage={crud.rowErrors.get("new") ?? null}
          onSave={(data) => void handleCreate(data)}
          onCancel={crud.cancelAdding}
        />
      )}
    </div>
  );
}
