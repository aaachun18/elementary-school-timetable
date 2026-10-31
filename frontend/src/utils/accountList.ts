// 帳號管理's list: the order of the accounts and the search box's state.
// Pure, no React.

import type { UserRole } from "./auth";

export interface SortableAccount {
  username: string;
  role: UserRole;
  teacher_name: string | null;
}

const ROLE_ORDER: Record<UserRole, number> = { ADMIN: 0, COORDINATOR: 1, TEACHER: 2 };

// Teachers by their name's strokes -- the surname's first (zh-Hant's
// collation orders Chinese by stroke count: 丁 2, 王 4, 李 7, 陳 16) --
// then by 帳號名稱. Accounts without a teacher (系統管理員 / 教學組長)
// come first, by role and 帳號名稱. A copy; the input is unchanged.
export function sortAccounts<T extends SortableAccount>(accounts: readonly T[]): T[] {
  return [...accounts].sort((a, b) => {
    if ((a.teacher_name === null) !== (b.teacher_name === null)) {
      return a.teacher_name === null ? -1 : 1;
    }
    if (a.teacher_name === null || b.teacher_name === null) {
      return ROLE_ORDER[a.role] - ROLE_ORDER[b.role] || a.username.localeCompare(b.username);
    }
    return a.teacher_name.localeCompare(b.teacher_name, "zh-Hant-TW") || a.username.localeCompare(b.username);
  });
}

// The 序號 of the row at `index` on page `page` (1-based, across pages).
export function serialNumber(page: number, pageSize: number, index: number): number {
  return (page - 1) * pageSize + index + 1;
}

// 系統管理員's role filter (left of the search box): every account, or
// one role's. Applied in the page to what the search returned.
export type RoleFilter = "ALL" | UserRole;

export const ROLE_FILTER_OPTIONS: readonly { value: RoleFilter; label: string }[] = [
  { value: "ALL", label: "所有角色" },
  { value: "TEACHER", label: "教師" },
  { value: "ADMIN", label: "系統管理員" },
  { value: "COORDINATOR", label: "教學組長" },
];

export function roleFilterLabel(filter: RoleFilter): string {
  return ROLE_FILTER_OPTIONS.find((option) => option.value === filter)?.label ?? "";
}

export function filterByRole<T extends { role: UserRole }>(accounts: readonly T[], filter: RoleFilter): T[] {
  return filter === "ALL" ? [...accounts] : accounts.filter((account) => account.role === filter);
}

// The line under the search box while a search or a role is applied: what
// the table shows and how many, so it is clear the table is filtered
// (「顯示全部」 sits next to it). `role` is the role's label, null = every role.
export function searchResultText(search: string | null, role: string | null, count: number): string {
  const roleName = role ?? "";
  if (search === null) {
    return count === 0 ? `沒有${roleName}帳號` : `${roleName}：共 ${count} 個帳號`;
  }
  if (count === 0) {
    return `找不到包含「${search}」的${roleName}帳號`;
  }
  return `${role === null ? "" : `${role}中`}搜尋「${search}」：共 ${count} 個帳號`;
}
