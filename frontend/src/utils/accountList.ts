// 帳號管理's list: the order of the accounts and the filters' state.
// Pure, no React.

import type { UserRole } from "./auth";

export interface SortableAccount {
  username: string;
  role: UserRole;
  teacher_name: string | null;
}

const ROLE_ORDER: Record<UserRole, number> = { ADMIN: 0, COORDINATOR: 1, TEACHER: 2 };

// 帳號改版: 教學組長 first, then 一般老師; within a role by the name's
// strokes -- the surname's first (zh-Hant's collation orders Chinese by
// stroke count: 丁 2, 王 4, 李 7, 陳 16) -- then by 帳號. An account
// without a name comes last in its role. A copy; the input is unchanged.
export function sortAccounts<T extends SortableAccount>(accounts: readonly T[]): T[] {
  return [...accounts].sort((a, b) => {
    const byRole = ROLE_ORDER[a.role] - ROLE_ORDER[b.role];
    if (byRole !== 0) {
      return byRole;
    }
    if ((a.teacher_name === null) !== (b.teacher_name === null)) {
      return a.teacher_name === null ? 1 : -1;
    }
    const byName =
      a.teacher_name === null || b.teacher_name === null
        ? 0
        : a.teacher_name.localeCompare(b.teacher_name, "zh-Hant-TW");
    return byName || a.username.localeCompare(b.username);
  });
}

// The 序號 of the row at `index` on page `page` (1-based, across pages).
export function serialNumber(page: number, pageSize: number, index: number): number {
  return (page - 1) * pageSize + index + 1;
}

// 系統管理員's filter (left of the search box): every account, one role's,
// or the 一般老師 with no school (無所屬學校, waiting to be assigned).
// Applied in the page to what the search returned.
export type AccountFilter = "ALL" | "COORDINATOR" | "TEACHER" | "NO_SCHOOL";

export const ACCOUNT_FILTER_OPTIONS: readonly { value: AccountFilter; label: string }[] = [
  { value: "ALL", label: "所有帳號" },
  { value: "COORDINATOR", label: "教學組長" },
  { value: "TEACHER", label: "一般老師" },
  { value: "NO_SCHOOL", label: "無所屬學校" },
];

export function accountFilterLabel(filter: AccountFilter): string {
  return ACCOUNT_FILTER_OPTIONS.find((option) => option.value === filter)?.label ?? "";
}

export function filterAccounts<T extends { role: UserRole; school_id: number | null }>(
  accounts: readonly T[],
  filter: AccountFilter,
): T[] {
  switch (filter) {
    case "ALL":
      return [...accounts];
    case "NO_SCHOOL":
      return accounts.filter((account) => account.school_id === null);
    default:
      return accounts.filter((account) => account.role === filter);
  }
}

// The line under the search box while a search or a filter is applied:
// what the table shows and how many, so it is clear the table is filtered
// (「顯示全部」 sits next to it). `group` is the filter's label, null = all.
export function searchResultText(search: string | null, group: string | null, count: number): string {
  const groupName = group ?? "";
  if (search === null) {
    return count === 0 ? `沒有${groupName}帳號` : `${groupName}：共 ${count} 個帳號`;
  }
  if (count === 0) {
    return `找不到包含「${search}」的${groupName}帳號`;
  }
  return `${group === null ? "" : `${group}中`}搜尋「${search}」：共 ${count} 個帳號`;
}
